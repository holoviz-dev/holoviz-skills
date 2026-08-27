#!/usr/bin/env python3
"""
HoloViz skills evaluation runner.

Runs Kilo Code queries with and without skills enabled, optionally executes
the generated code and aggregates metrics — all in a single command.

Usage:
  # Full pipeline (generate + execute + report)
  python eval.py

  # Generate only
  python eval.py --skip-execution --skip-aggregation

  # Specific queries, with-skills condition only
  python eval.py --queries hvplot_earthquake_plot --skills with

  # Re-run execution and reporting without re-querying Kilo
  python eval.py --skip-generation

  # Full pipeline, longer execution timeout, no screenshots
  python eval.py --timeout 60 --skip-screenshots

  # Run with specific models
  python eval.py --models kilo/kilo-auto/free

  # Compare two models, with-skills condition only
  python eval.py --models kilo/kilo-auto/frontier kilo/kilo-auto/free --skills with
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import yaml
from toggle_skills import disable_skills, enable_skills

# Appended to every query prompt so the model always wraps code in a fenced
# block, giving the extractor a stable target regardless of prose formatting.
CODE_OUTPUT_INSTRUCTION = (
    "\n\nRespond with a single self-contained ```python``` code block and nothing else outside it."
)

# Sentinel used when no --model flag is passed (Kilo picks its default).
DEFAULT_MODEL = "default"
DEFAULT_MODEL_LABEL = "Default (Kilo)"

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent


def _parse_kilo_events(raw_output: str) -> list[dict]:
    """Parse the JSON event stream emitted by `kilo run --format json`.

    Non-JSON lines (e.g. first-run database migration notices) are skipped.
    """
    events = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _extract_text_from_events(events: list[dict]) -> str:
    """Reconstruct the assistant's visible text from `text` events.

    A part may be streamed across several events carrying its accumulated
    text, so keep only the latest text per part id.
    """
    texts: dict[str, str] = {}
    order: list[str] = []
    for event in events:
        part = event.get("part") or {}
        if event.get("type") != "text" or not part.get("text"):
            continue
        part_id = part.get("id") or f"part-{len(order)}"
        if part_id not in texts:
            order.append(part_id)
        texts[part_id] = part["text"]
    return "\n".join(texts[part_id] for part_id in order)


def _extract_usage_from_events(events: list[dict]) -> tuple[dict[str, int], float, list[str]]:
    """Sum token usage, cost, and routed models across `step_finish` events."""
    tokens = {"input": 0, "output": 0, "cached": 0, "reasoning": 0}
    cost = 0.0
    resolved_models: list[str] = []
    for event in events:
        if event.get("type") != "step_finish":
            continue
        part = event.get("part") or {}
        step_tokens = part.get("tokens") or {}
        tokens["input"] += step_tokens.get("input", 0)
        tokens["output"] += step_tokens.get("output", 0)
        tokens["reasoning"] += step_tokens.get("reasoning", 0)
        tokens["cached"] += (step_tokens.get("cache") or {}).get("read", 0)
        cost += part.get("cost", 0)
        model_id = (part.get("model") or {}).get("modelID")
        if model_id and model_id not in resolved_models:
            resolved_models.append(model_id)
    return tokens, cost, resolved_models


class KiloResponse:
    """Parsed response from the Kilo Code CLI."""

    def __init__(
        self,
        raw_output: str,
        query: str,
        execution_time: float,
        model: str,
        events: list[dict] | None = None,
    ):
        self.raw_output = raw_output
        self.query = query
        self.execution_time = execution_time
        self.model = model
        self.events = events or []
        self.code_blocks = self._extract_code_blocks()
        self.tokens, self.cost, self.resolved_models = _extract_usage_from_events(self.events)

    def _extract_code_blocks(self) -> list[str]:
        """Extract Python code blocks from the response (fenced ``` blocks only)."""
        pattern = r"```(?:python)?\s*\n(.*?)```"
        return re.findall(pattern, self.raw_output, re.DOTALL)

    def get_primary_code(self) -> str | None:
        return self.code_blocks[0] if self.code_blocks else None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "model": self.model,
            "execution_time": self.execution_time,
            "tokens": self.tokens,
            "cost": self.cost,
            "resolved_models": self.resolved_models,
            "code_blocks_count": len(self.code_blocks),
            "has_code": len(self.code_blocks) > 0,
        }


def load_queries(yaml_path: Path) -> list[dict]:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return data.get("queries", [])


def model_to_slug(model: str | None) -> str:
    """Convert a model name to a filesystem-safe slug.

    None / empty string maps to DEFAULT_MODEL so old results stay under
    eval_results/default/ and are still valid.
    """
    if not model:
        return DEFAULT_MODEL
    return re.sub(r"[^a-zA-Z0-9_\-.]", "_", model)


def run_kilo_query(
    query: str, model: str | None = None, timeout: int = 180
) -> tuple[str, float, list[dict]]:
    """Run one query through the Kilo Code CLI in autonomous mode.

    Returns the reconstructed assistant text, wall-clock time, and the
    parsed JSON events (token/cost usage comes from the events, not text).
    """
    start_time = time.time()
    try:
        cmd = ["kilo", "run", "--auto", "--format", "json"]
        if model:
            cmd += ["-m", model]
        cmd += [query]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
        )
        execution_time = time.time() - start_time
        events = _parse_kilo_events(result.stdout)
        output = _extract_text_from_events(events)
        if result.stderr:
            output += f"\n\n[STDERR]\n{result.stderr}"
        return output, execution_time, events
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT after {timeout}s]", time.time() - start_time, []
    except Exception as e:
        return f"[ERROR: {str(e)}]", time.time() - start_time, []


def save_results(
    query_id: str,
    response: KiloResponse,
    output_dir: Path,
    skills_enabled: bool,
):
    model_slug = model_to_slug(response.model if response.model != DEFAULT_MODEL_LABEL else None)
    condition = "with_skills" if skills_enabled else "without_skills"
    query_dir = output_dir / model_slug / condition / query_id
    query_dir.mkdir(parents=True, exist_ok=True)

    (query_dir / "response.txt").write_text(response.raw_output)

    metadata = response.to_dict()
    metadata["skills_enabled"] = skills_enabled
    with open(query_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    primary_code = response.get_primary_code()
    if primary_code:
        (query_dir / "generated_code.py").write_text(primary_code)
        print(f"  Saved code ({len(primary_code)} chars)")
    else:
        print("  No code block found in response")

    if len(response.code_blocks) > 1:
        for i, code in enumerate(response.code_blocks):
            (query_dir / f"code_block_{i}.py").write_text(code)


def run_generation(
    queries: list[dict],
    output_dir: Path,
    models: list[str | None],
    skip_without_skills: bool = False,
    skip_with_skills: bool = False,
):
    for model in models:
        model_label = model or DEFAULT_MODEL
        if len(models) > 1:
            print(f"\n{'═' * 60}")
            print(f"Model: {model_label}")
            print(f"{'═' * 60}")

        for i, query in enumerate(queries, 1):
            query_id = query["id"]
            prompt = query["prompt"].rstrip() + CODE_OUTPUT_INSTRUCTION
            timeout = query.get("timeout", 180)

            print(f"[{i}/{len(queries)}] {query_id}")

            if not skip_without_skills:
                print("  Running WITHOUT skills...")
                disable_skills(REPO_ROOT)
                try:
                    raw_output, exec_time, events = run_kilo_query(
                        prompt, model=model, timeout=timeout
                    )
                    response = KiloResponse(
                        raw_output, prompt, exec_time, model=model_label, events=events
                    )
                    tok = response.tokens
                    print(
                        f"  Completed in {exec_time:.2f}s | "
                        f"Tokens: ↑{tok['input']} ↓{tok['output']}"
                        + (f" ({tok['cached']} cached)" if tok["cached"] else "")
                    )
                    save_results(query_id, response, output_dir, skills_enabled=False)
                finally:
                    enable_skills(REPO_ROOT)

            if not skip_with_skills:
                print("  Running WITH skills...")
                raw_output, exec_time, events = run_kilo_query(prompt, model=model, timeout=timeout)
                response = KiloResponse(
                    raw_output, prompt, exec_time, model=model_label, events=events
                )
                tok = response.tokens
                print(
                    f"  Completed in {exec_time:.2f}s | "
                    f"Tokens: ↑{tok['input']} ↓{tok['output']}"
                    + (f" ({tok['cached']} cached)" if tok["cached"] else "")
                )
                save_results(query_id, response, output_dir, skills_enabled=True)

            print(f"{'─' * 60}")


def run_execution(
    output_dir: Path,
    query_ids: list[str] | None,
    timeout: int,
    skip_screenshots: bool,
):
    # Import here so execute_generated.py remains independently runnable
    sys.path.insert(0, str(SCRIPTS_DIR))
    from execute_generated import execute_all_code

    execute_all_code(
        eval_results_dir=output_dir,
        timeout=timeout,
        query_ids=query_ids,
        skip_screenshots=skip_screenshots,
    )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "run"


def _safe_git_short_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
    except Exception:
        return None
    sha = result.stdout.strip()
    return sha or None


def _default_run_id(run_trigger: str, models_requested: list[str], query_count: int) -> str:
    """Return a short readable run ID that is distinct from created_at."""
    model_tag = _slugify(models_requested[0]) if len(models_requested) == 1 else "multi-model"
    sha = _safe_git_short_sha() or "local"
    nonce = uuid4().hex[:4]
    return f"{_slugify(run_trigger)}-{model_tag}-q{query_count}-{sha}-{nonce}"


def run_aggregation(
    output_dir: Path,
    query_ids: list[str] | None,
    run_id: str,
    run_metadata: dict,
):
    sys.path.insert(0, str(SCRIPTS_DIR))
    from aggregate_metrics import aggregate_metrics

    aggregate_metrics(
        eval_results_dir=output_dir,
        query_filter=query_ids,
        run_id=run_id,
        run_metadata=run_metadata,
    )


def main():
    parser = argparse.ArgumentParser(
        description="HoloViz skills evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python eval.py

  # Specific queries only
  python eval.py --queries hvplot_earthquake_plot hvplot_interactive_scatter

  # With-skills condition only
  python eval.py --skills with

  # Re-run execution + report without re-querying Kilo
  python eval.py --skip-generation

  # Generate only
  python eval.py --skip-execution --skip-aggregation

  # Full pipeline, longer timeout, no screenshots
  python eval.py --timeout 60 --skip-screenshots

  # Run with specific models
  python eval.py --models kilo/kilo-auto/free

  # Compare two models, with-skills only
  python eval.py --models kilo/kilo-auto/frontier kilo/kilo-auto/free --skills with
        """,
    )

    parser.add_argument(
        "--queries-file",
        type=Path,
        default=SCRIPTS_DIR / "eval_queries.yaml",
        help="Path to queries YAML file (default: eval_queries.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "eval_results",
        help="Output directory (default: ../eval_results)",
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        help="Specific query IDs to run (default: all)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        metavar="MODEL",
        help=(
            "Model(s) to evaluate in provider/model format (e.g. kilo/kilo-auto/free). "
            f"Defaults to {DEFAULT_MODEL_LABEL}."
        ),
    )
    parser.add_argument(
        "--skills",
        choices=["both", "with", "without"],
        default="both",
        help="Which condition(s) to evaluate (default: both)",
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Skip Kilo query step (use existing generated_code.py files)",
    )
    parser.add_argument(
        "--skip-execution",
        action="store_true",
        help="Skip code execution step",
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Skip screenshot capture during execution (faster)",
    )
    parser.add_argument(
        "--skip-aggregation",
        action="store_true",
        help="Skip metrics aggregation step",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Code execution timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Unique run identifier (default: readable slug)",
    )
    parser.add_argument(
        "--run-trigger",
        choices=["manual", "ci_comment", "ci_dispatch", "ci_schedule"],
        default="manual",
        help="Source that triggered this run (default: manual)",
    )
    parser.add_argument(
        "--publish-target",
        default="local",
        help="Publish target hint recorded in run metadata (default: local)",
    )

    args = parser.parse_args()

    if not args.queries_file.exists():
        print(f"Error: Queries file not found: {args.queries_file}")
        return 1

    queries = load_queries(args.queries_file)
    if args.queries:
        queries = [q for q in queries if q["id"] in args.queries]
    if not queries:
        print("No queries matched.")
        return 1

    # None in the list means "use Kilo's default model" (no --model flag)
    models: list[str | None] = args.models if args.models else [None]
    models_requested = [model or DEFAULT_MODEL for model in models]
    run_id = args.run_id or _default_run_id(
        run_trigger=args.run_trigger,
        models_requested=models_requested,
        query_count=len(queries),
    )

    run_metadata = {
        "run_trigger": args.run_trigger,
        "publish_target": args.publish_target,
        "models_requested": models_requested,
        "query_ids": [q["id"] for q in queries],
        "skip_generation": args.skip_generation,
        "skip_execution": args.skip_execution,
        "skip_aggregation": args.skip_aggregation,
    }

    print(f"Running {len(queries)} quer(ies) × {len(models)} model(s)\n")
    print(f"Run ID: {run_id}")

    # Step 1: Generate
    if not args.skip_generation:
        run_generation(
            queries=queries,
            output_dir=args.output,
            models=models,
            skip_without_skills=args.skills == "with",
            skip_with_skills=args.skills == "without",
        )
        print("\nGeneration complete.")

    # Step 2: Execute
    if not args.skip_execution:
        print("\n→ Executing generated code...")
        run_execution(
            output_dir=args.output,
            query_ids=args.queries,
            timeout=args.timeout,
            skip_screenshots=args.skip_screenshots,
        )

    # Step 3: Aggregate
    if not args.skip_aggregation:
        print("\n→ Aggregating metrics...")
        run_aggregation(
            output_dir=args.output,
            query_ids=args.queries,
            run_id=run_id,
            run_metadata=run_metadata,
        )

    print(f"\nDone. Results saved to: {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
