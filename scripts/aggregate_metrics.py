#!/usr/bin/env python3
"""
Aggregate metrics from evaluation results.

This script:
1. Collects all metadata.json files from eval_results
2. Compares metrics between with_skills and without_skills conditions,
   across one or more models
3. Generates summary reports: evaluation_results.json and run history snapshots

Directory layout supported:

   eval_results/{model}/{condition}/{query_id}/metadata.json
"""

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

CONDITIONS = ("with_skills", "without_skills")
RUNS_REGISTRY_FILE = "runs.json"
HISTORY_SUMMARY_FILE = "history_summary.json"
HISTORY_SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _flatten_history_rows(summary: dict, run_id: str, created_at: str) -> list[dict]:
    rows: list[dict] = []
    for query_id, query_data in summary.get("queries", {}).items():
        models = query_data.get("models", {})
        for model, model_data in models.items():
            for condition in CONDITIONS:
                metrics = model_data.get(condition, {})
                if not metrics:
                    continue
                rows.append(
                    {
                        "run_id": run_id,
                        "created_at": created_at,
                        "query_id": query_id,
                        "model": model,
                        "condition": condition,
                        "tokens_output": metrics.get("tokens_output"),
                        "tokens_input": metrics.get("tokens_input"),
                        "tokens_cached": metrics.get("tokens_cached"),
                        "execution_time": metrics.get("execution_time"),
                        "execution_success": metrics.get("execution_success"),
                        "has_code": metrics.get("has_code"),
                    }
                )
    return rows


def _update_history_summary(eval_results_dir: Path, new_rows: list[dict]):
    path = eval_results_dir / HISTORY_SUMMARY_FILE
    payload = _load_json(path, {"schema_version": HISTORY_SCHEMA_VERSION, "rows": []})
    existing_rows = payload.get("rows", [])
    by_key = {
        (r.get("run_id"), r.get("query_id"), r.get("model"), r.get("condition")): r
        for r in existing_rows
    }
    for row in new_rows:
        key = (row["run_id"], row["query_id"], row["model"], row["condition"])
        by_key[key] = row

    merged_rows = sorted(
        by_key.values(),
        key=lambda r: (r.get("created_at") or "", r.get("run_id") or ""),
    )
    payload = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "row_count": len(merged_rows),
        "rows": merged_rows,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _update_runs_registry(eval_results_dir: Path, run_record: dict):
    path = eval_results_dir / RUNS_REGISTRY_FILE
    payload = _load_json(path, {"schema_version": HISTORY_SCHEMA_VERSION, "runs": []})
    runs = payload.get("runs", [])

    runs_by_id = {r.get("run_id"): r for r in runs if r.get("run_id")}
    runs_by_id[run_record["run_id"]] = run_record

    merged_runs = sorted(
        runs_by_id.values(),
        key=lambda r: (r.get("created_at") or "", r.get("run_id") or ""),
        reverse=True,
    )

    payload = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "run_count": len(merged_runs),
        "runs": merged_runs,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _build_run_record(
    run_id: str,
    created_at: str,
    summary: dict,
    run_metadata: dict,
    snapshot_dir: Path,
) -> dict:
    metadata = run_metadata or {}
    return {
        "run_id": run_id,
        "created_at": created_at,
        "status": "success",
        "results_relpath": str(snapshot_dir.relative_to(snapshot_dir.parent.parent)),
        "total_queries": summary.get("total_queries", 0),
        "models": summary.get("models", []),
        "run_trigger": metadata.get("run_trigger", "manual"),
        "publish_target": metadata.get("publish_target", "local"),
        "models_requested": metadata.get("models_requested", []),
        "query_ids": metadata.get("query_ids", []),
        "skip_generation": bool(metadata.get("skip_generation", False)),
        "skip_execution": bool(metadata.get("skip_execution", False)),
        "skip_aggregation": bool(metadata.get("skip_aggregation", False)),
        "git_commit": _safe_git_value("rev-parse", "HEAD"),
        "git_branch": _safe_git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def _persist_run_snapshot(
    eval_results_dir: Path,
    summary: dict,
    run_id: str,
    run_metadata: dict | None,
):
    created_at = _utc_now_iso()
    runs_dir = eval_results_dir / "runs"
    snapshot_dir = runs_dir / run_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshot_json = snapshot_dir / "evaluation_results.json"
    snapshot_json.write_text(json.dumps(summary, indent=2) + "\n")

    run_record = _build_run_record(
        run_id=run_id,
        created_at=created_at,
        summary=summary,
        run_metadata=run_metadata or {},
        snapshot_dir=snapshot_dir,
    )
    (snapshot_dir / "run_metadata.json").write_text(json.dumps(run_record, indent=2) + "\n")

    _update_runs_registry(eval_results_dir, run_record)
    _update_history_summary(eval_results_dir, _flatten_history_rows(summary, run_id, created_at))


def _extract_metrics(metadata: dict) -> dict:
    """Pull the key metrics fields out of a metadata.json dict."""
    return {
        "has_code": metadata.get("has_code", False),
        "code_blocks_count": metadata.get("code_blocks_count", 0),
        "execution_time": metadata.get("execution_time", 0),
        "tokens_input": metadata.get("tokens", {}).get("input", 0),
        "tokens_output": metadata.get("tokens", {}).get("output", 0),
        "tokens_total": (
            metadata.get("tokens", {}).get("input", 0) + metadata.get("tokens", {}).get("output", 0)
        ),
        "tokens_cached": metadata.get("tokens", {}).get("cached", 0),
        "tokens_reasoning": metadata.get("tokens", {}).get("reasoning", 0),
        "execution_success": metadata.get("execution", {}).get("success", None),
        "execution_duration": metadata.get("execution", {}).get("execution_time", None),
    }


def collect_metrics(
    eval_results_dir: Path,
    query_filter: list[str] | None = None,
) -> dict:
    """
    Collect all metrics from evaluation results.

    Returns a nested dict:
        metrics[query_id][model][condition] = { metric_key: value, ... }

    Expected layout:
      - eval_results/{model}/{condition}/{query_id}/metadata.json
    """
    metrics: dict[str, dict[str, dict[str, dict]]] = {}

    for entry in eval_results_dir.iterdir():
        if not entry.is_dir():
            continue

        model = entry.name
        for condition_dir in entry.iterdir():
            if not condition_dir.is_dir() or condition_dir.name not in CONDITIONS:
                continue
            condition = condition_dir.name
            for query_dir in condition_dir.iterdir():
                if not query_dir.is_dir():
                    continue
                query_id = query_dir.name
                if query_filter and query_id not in query_filter:
                    continue
                metadata_file = query_dir / "metadata.json"
                if not metadata_file.exists():
                    continue
                with open(metadata_file) as f:
                    metadata = json.load(f)
                query_metrics = metrics.setdefault(query_id, {})
                model_metrics = query_metrics.setdefault(model, {})
                model_metrics[condition] = _extract_metrics(metadata)

    return metrics


def _condition_comparison(with_skills: dict, without_skills: dict) -> dict:
    """Compare with_skills vs without_skills metrics for a single model."""
    comp: dict = {
        "both_have_code": (with_skills.get("has_code") and without_skills.get("has_code")),
    }

    if with_skills and without_skills:
        comp["token_difference"] = with_skills["tokens_output"] - without_skills["tokens_output"]
        comp["time_difference"] = with_skills["execution_time"] - without_skills["execution_time"]

    ws_exec = with_skills.get("execution_success")
    wos_exec = without_skills.get("execution_success")
    comp["both_executed"] = ws_exec is not None and wos_exec is not None
    if comp["both_executed"]:
        comp["execution_improvement"] = ws_exec and not wos_exec
        comp["execution_regression"] = not ws_exec and wos_exec

    return comp


def generate_comparison_summary(metrics: dict) -> dict:
    """
    Generate a multi-model summary.

    Structure:
      summary["queries"][query_id]["models"][model]["with_skills"]    = metrics
      summary["queries"][query_id]["models"][model]["without_skills"] = metrics
      summary["queries"][query_id]["models"][model]["comparison"]     = diffs
      summary["aggregate"]                                            = aggregate stats
    """
    all_models: list[str] = sorted({m for q in metrics.values() for m in q})
    summary = {
        "total_queries": len(metrics),
        "models": all_models,
        "queries": {},
    }

    for query_id, model_data in metrics.items():
        query_summary: dict = {"models": {}}

        for model, conditions in model_data.items():
            ws = conditions.get("with_skills", {})
            wos = conditions.get("without_skills", {})
            entry: dict = {"with_skills": ws, "without_skills": wos, "comparison": {}}

            if ws and wos:
                entry["comparison"] = _condition_comparison(ws, wos)

            query_summary["models"][model] = entry

        summary["queries"][query_id] = query_summary

    # Aggregate statistics per model
    agg_by_model: dict[str, dict] = {}
    for model in all_models:
        model_entries = [
            q["models"][model] for q in summary["queries"].values() if model in q["models"]
        ]

        ws_list = [e["with_skills"] for e in model_entries if e["with_skills"]]
        wos_list = [e["without_skills"] for e in model_entries if e["without_skills"]]
        comparisons = [e["comparison"] for e in model_entries if e.get("comparison")]

        agg: dict = {}
        if ws_list:
            agg["code_generation_rate_with"] = sum(1 for e in ws_list if e.get("has_code")) / len(
                ws_list
            )
        if wos_list:
            agg["code_generation_rate_without"] = sum(
                1 for e in wos_list if e.get("has_code")
            ) / len(wos_list)

        if comparisons:
            agg["avg_token_difference"] = sum(
                c.get("token_difference", 0) for c in comparisons
            ) / len(comparisons)
            agg["avg_time_difference"] = sum(
                c.get("time_difference", 0) for c in comparisons
            ) / len(comparisons)

        ws_executed = [e for e in ws_list if e.get("execution_success") is not None]
        wos_executed = [e for e in wos_list if e.get("execution_success") is not None]
        if ws_executed:
            agg["execution_success_rate_with"] = sum(
                1 for e in ws_executed if e["execution_success"]
            ) / len(ws_executed)
        if wos_executed:
            agg["execution_success_rate_without"] = sum(
                1 for e in wos_executed if e["execution_success"]
            ) / len(wos_executed)

        agg_by_model[model] = agg

    summary["aggregate"] = agg_by_model
    return summary


def aggregate_metrics(
    eval_results_dir: Path,
    output_dir: Path | None = None,
    query_filter: list[str] | None = None,
    run_id: str | None = None,
    run_metadata: dict | None = None,
):
    """
    Main aggregation function.

    Args:
        eval_results_dir: Directory containing evaluation results
        output_dir: Where to save reports (defaults to eval_results_dir)
        query_filter: Optional list of query IDs to include (None = all queries)
    """
    if output_dir is None:
        output_dir = eval_results_dir

    metrics = collect_metrics(eval_results_dir, query_filter)

    if not metrics:
        print("No metrics found!")
        return

    summary = generate_comparison_summary(metrics)

    json_file = output_dir / "evaluation_results.json"
    with open(json_file, "w") as f:
        json.dump(summary, f, indent=2)

    if run_id:
        _persist_run_snapshot(
            eval_results_dir=eval_results_dir,
            summary=summary,
            run_id=run_id,
            run_metadata=run_metadata,
        )

    model_count = len(summary.get("models", []))
    print(f"Metrics aggregated for {len(metrics)} quer(ies) × {model_count} model(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate evaluation metrics and generate reports"
    )

    parser.add_argument(
        "--eval-results",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Evaluation results directory (default: ../eval_results)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for reports (default: same as eval-results)",
    )

    parser.add_argument(
        "--queries",
        nargs="+",
        help="Only aggregate metrics for specific queries (default: all queries)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run ID for creating historical snapshots",
    )
    parser.add_argument(
        "--run-trigger",
        default="manual",
        help="Run trigger metadata saved with snapshots",
    )
    parser.add_argument(
        "--publish-target",
        default="local",
        help="Publish target metadata saved with snapshots",
    )

    args = parser.parse_args()

    if not args.eval_results.exists():
        print(f"Error: Evaluation results directory not found: {args.eval_results}")
        return 1

    aggregate_metrics(
        eval_results_dir=args.eval_results,
        output_dir=args.output,
        query_filter=args.queries,
        run_id=args.run_id,
        run_metadata={
            "run_trigger": args.run_trigger,
            "publish_target": args.publish_target,
        },
    )

    return 0


if __name__ == "__main__":
    exit(main())
