#!/usr/bin/env python3
"""
Aggregate metrics from evaluation results.

This script:
1. Collects all metadata.json files from eval_results
2. Compares metrics between with_skills and without_skills conditions,
   across one or more models
3. Generates summary reports: evaluation_results.json and evaluation_summary.md

Directory layouts supported:

  New (with model dimension):
    eval_results/{model}/{condition}/{query_id}/metadata.json

  Legacy (no model dimension — treated as model="default"):
    eval_results/{condition}/{query_id}/metadata.json
"""

import argparse
import json
from pathlib import Path

CONDITIONS = ("with_skills", "without_skills")


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

    Both directory layouts are supported:
      - New:    eval_results/{model}/{condition}/{query_id}/metadata.json
      - Legacy: eval_results/{condition}/{query_id}/metadata.json
    """
    metrics: dict[str, dict[str, dict[str, dict]]] = {}

    for entry in eval_results_dir.iterdir():
        if not entry.is_dir():
            continue

        if entry.name in CONDITIONS:
            # Legacy layout: condition at depth-1
            model = "default"
            condition = entry.name
            for query_dir in entry.iterdir():
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
                model_metrics = metrics.setdefault(query_id, {}).setdefault(model, {})
                model_metrics[condition] = _extract_metrics(metadata)
        else:
            # New layout: model at depth-1, condition at depth-2
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


def _fmt_bool(val: bool | None) -> str:
    if val is None:
        return "—"
    return "✓" if val else "✗"


def _fmt_float(val: float | None, decimals: int = 2, suffix: str = "") -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}{suffix}"


def _fmt_int(val: int | None) -> str:
    if val is None:
        return "—"
    return f"{val:,}"


def _fmt_metric_rate(agg: dict, key: str) -> str:
    if key not in agg:
        return "—"
    return f"{agg[key]:.1%}"


def _fmt_metric_delta(agg: dict, key: str, decimals: int = 0, suffix: str = "") -> str:
    if key not in agg:
        return "—"
    return f"{agg[key]:+,.{decimals}f}{suffix}"


def _render_table(header: str, separator: str, rows: list[str]) -> str:
    return "\n".join([header, separator, *rows])


def _render_single_model_query_section(model_data: dict, model: str) -> str:
    ws = model_data.get(model, {}).get("with_skills", {})
    wos = model_data.get(model, {}).get("without_skills", {})

    if not ws or not wos:
        return "_No data._"

    rows = [
        (
            "Code Generated",
            _fmt_bool(ws.get("has_code")),
            _fmt_bool(wos.get("has_code")),
        ),
        (
            "Response Time",
            _fmt_float(ws.get("execution_time"), suffix="s"),
            _fmt_float(wos.get("execution_time"), suffix="s"),
        ),
        (
            "Tokens (output)",
            _fmt_int(ws.get("tokens_output")),
            _fmt_int(wos.get("tokens_output")),
        ),
        (
            "Tokens (input)",
            _fmt_int(ws.get("tokens_input")),
            _fmt_int(wos.get("tokens_input")),
        ),
        (
            "Tokens (cached)",
            _fmt_int(ws.get("tokens_cached")),
            _fmt_int(wos.get("tokens_cached")),
        ),
    ]

    if ws.get("execution_success") is not None or wos.get("execution_success") is not None:
        rows.append(
            (
                "Execution Success",
                _fmt_bool(ws.get("execution_success")),
                _fmt_bool(wos.get("execution_success")),
            )
        )

    table = _render_table(
        "| Metric | With Skills | Without Skills |",
        "|--------|-------------|----------------|",
        [f"| {label} | {left} | {right} |" for label, left, right in rows],
    )

    notes = []
    comp = model_data.get(model, {}).get("comparison", {})
    if comp.get("execution_improvement"):
        notes.append("**IMPROVED:** Code executes successfully with skills")
    elif comp.get("execution_regression"):
        notes.append("**REGRESSION:** Code fails with skills")

    return "\n\n".join([table, *notes]) if notes else table


def _render_multi_model_query_section(model_data: dict, model_cols: list[str]) -> str:
    metrics_rows = [
        ("Code Generated", "has_code", _fmt_bool),
        ("Response Time (s)", "execution_time", lambda v: _fmt_float(v, suffix="s")),
        ("Tokens (output)", "tokens_output", _fmt_int),
        ("Tokens (input)", "tokens_input", _fmt_int),
        ("Tokens (cached)", "tokens_cached", _fmt_int),
        ("Execution Success", "execution_success", _fmt_bool),
    ]

    header = "| Metric |" + "".join(f" `{m}` w/ skills | `{m}` w/o skills |" for m in model_cols)
    separator = "|--------|" + "".join(" --- | --- |" for _ in model_cols)

    rows = []
    for label, key, fmt in metrics_rows:
        cells = []
        for model in model_cols:
            ws = model_data[model].get("with_skills", {})
            wos = model_data[model].get("without_skills", {})
            cells.extend([fmt(ws.get(key)), fmt(wos.get(key))])
        rows.append("| " + label + " | " + " | ".join(cells) + " |")

    notes = []
    for model in model_cols:
        comp = model_data[model].get("comparison", {})
        if comp.get("execution_improvement"):
            notes.append(f"**`{model}` IMPROVED:** " "Code executes successfully with skills")
        elif comp.get("execution_regression"):
            notes.append(f"**`{model}` REGRESSION:** " "Code fails with skills")

    section = _render_table(header, separator, rows)
    return "\n\n".join([section, *notes]) if notes else section


def _render_query_section(query_id: str, data: dict, all_models: list[str]) -> str:
    model_data = data.get("models", {})

    if not model_data:
        body = "_No data._"
    elif len(all_models) == 1:
        body = _render_single_model_query_section(model_data, all_models[0])
    else:
        model_cols = [model for model in all_models if model in model_data]
        body = _render_multi_model_query_section(model_data, model_cols)

    return f"### `{query_id}`\n\n{body}"


def save_markdown_report(summary: dict, output_file: Path):
    """Save a human-readable summary as a Markdown file."""
    all_models: list[str] = summary.get("models", ["default"])
    sections = [
        "# Evaluation Summary",
        f"**Total Queries:** {summary['total_queries']}  ",
        f"**Models evaluated:** {', '.join(f'`{m}`' for m in all_models)}",
    ]

    # ── Aggregate section ──────────────────────────────────────────────────
    if summary.get("aggregate"):
        sections.append("## Aggregate Statistics")
        table_header = (
            "| Model | With Skills | Without Skills |\n" "|-------|-------------|----------------|"
        )

        # Code generation rate
        code_rows = []
        for model, agg in summary["aggregate"].items():
            code_rows.append(
                f"| `{model}` | "
                f"{_fmt_metric_rate(agg, 'code_generation_rate_with')} | "
                f"{_fmt_metric_rate(agg, 'code_generation_rate_without')} |"
            )
        sections.append(_render_table("### Code Generation Rate", table_header, code_rows))

        # Execution success rate (only if data exists)
        aggregate_values = summary["aggregate"].values()
        has_exec = any("execution_success_rate_with" in agg for agg in aggregate_values)
        if has_exec:
            exec_rows = []
            for model, agg in summary["aggregate"].items():
                exec_rows.append(
                    f"| `{model}` | "
                    f"{_fmt_metric_rate(agg, 'execution_success_rate_with')} | "
                    f"{_fmt_metric_rate(agg, 'execution_success_rate_without')} |"
                )
            sections.append(_render_table("### Execution Success Rate", table_header, exec_rows))

        # Token and time deltas
        resource_rows = []
        for model, agg in summary["aggregate"].items():
            token_delta = _fmt_metric_delta(agg, "avg_token_difference")
            time_delta = _fmt_metric_delta(
                agg,
                "avg_time_difference",
                decimals=2,
                suffix="s",
            )
            resource_rows.append(f"| `{model}` | {token_delta} | {time_delta} |")
        resource_header = (
            "| Model | Avg Token Δ (output) | Avg Response Time Δ |\n"
            "|-------|---------------------|---------------------|"
        )
        sections.append(
            _render_table(
                "### Resource Usage (With Skills vs Without Skills)",
                resource_header,
                resource_rows,
            )
        )

    # ── Per-query section ──────────────────────────────────────────────────
    sections.append("## Per-Query Results")
    sections.extend(
        _render_query_section(query_id, data, all_models)
        for query_id, data in summary["queries"].items()
    )

    output_file.write_text("\n\n".join(sections) + "\n")


def aggregate_metrics(
    eval_results_dir: Path,
    output_dir: Path | None = None,
    query_filter: list[str] | None = None,
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

    md_file = output_dir / "evaluation_summary.md"
    save_markdown_report(summary, md_file)

    model_count = len(summary.get("models", []))
    print(
        f"Metrics aggregated for {len(metrics)} quer(ies) "
        f"× {model_count} model(s) → {md_file.name}"
    )


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

    args = parser.parse_args()

    if not args.eval_results.exists():
        print(f"Error: Evaluation results directory not found: {args.eval_results}")
        return 1

    aggregate_metrics(
        eval_results_dir=args.eval_results,
        output_dir=args.output,
        query_filter=args.queries,
    )

    return 0


if __name__ == "__main__":
    exit(main())
