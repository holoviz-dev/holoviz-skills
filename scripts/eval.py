#!/usr/bin/env python3
"""
HoloViz skills evaluation runner.

Runs Copilot queries with and without skills enabled, optionally executes
the generated code and aggregates metrics — all in a single command.

Usage:
  # Full pipeline (generate + execute + report)
  python eval.py

  # Generate only
  python eval.py --skip-execution --skip-aggregation

  # Specific queries, with-skills condition only
  python eval.py --queries earthquake_plot --skills with

  # Re-run execution and reporting without re-querying Copilot
  python eval.py --skip-generation

  # Full pipeline, longer execution timeout, no screenshots
  python eval.py --timeout 60 --skip-screenshots

  # Run with specific models
  python eval.py --models claude-sonnet-4.6 gpt-5.4-mini

  # Compare two models, with-skills condition only
  python eval.py --models claude-sonnet-4.6 gpt-5.4-mini --skills with
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml
from toggle_skills import disable_skills, enable_skills

# Appended to every query prompt so the model always wraps code in a fenced
# block, giving the extractor a stable target regardless of prose formatting.
CODE_OUTPUT_INSTRUCTION = (
    "\n\nRespond with a single self-contained ```python``` code block and nothing else outside it."
)

# Sentinel used when no --model flag is passed (Copilot picks its default).
DEFAULT_MODEL = "default"

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent


def _parse_token_value(val: str) -> int:
    """Convert a token value string like '13.0k' or '170' to an integer."""
    val = val.strip()
    if "k" in val.lower():
        return int(float(val.lower().replace("k", "")) * 1000)
    return int(val)


class CopilotResponse:
    """Parsed response from Copilot CLI."""

    def __init__(self, raw_output: str, query: str, execution_time: float, model: str):
        self.raw_output = raw_output
        self.query = query
        self.execution_time = execution_time
        self.model = model
        self.code_blocks = self._extract_code_blocks()
        self.tokens = self._extract_token_usage()

    def _extract_code_blocks(self) -> list[str]:
        """Extract Python code blocks from the response (fenced ``` blocks only)."""
        pattern = r"```(?:python)?\s*\n(.*?)```"
        return re.findall(pattern, self.raw_output, re.DOTALL)

    def _extract_token_usage(self) -> dict[str, int]:
        """Extract token usage from the response footer.

        The Copilot CLI footer looks like (fields are optional):
          Tokens     ↑ 13.0k (6.8k cached) • ↓ 170 (128 reasoning)
          Tokens     ↑ 14.3k • ↓ 18 (10 reasoning)
          Tokens     ↑ 13.0k • ↓ 42
        """
        tokens = {"input": 0, "output": 0, "cached": 0, "reasoning": 0}

        # Match the Tokens line; all parenthetical sub-fields are optional.
        token_line_pattern = r"Tokens\s+↑\s*([\d.k]+)"
        match = re.search(token_line_pattern, self.raw_output)
        if not match:
            return tokens

        # Start of line (for sub-field extraction)
        line_start = match.start()
        line = self.raw_output[line_start : self.raw_output.find("\n", line_start)]

        tokens["input"] = _parse_token_value(match.group(1))

        # Optional: (N cached) after the input value
        cached_match = re.search(r"\(([\d.k]+)\s+cached\)", line)
        if cached_match:
            tokens["cached"] = _parse_token_value(cached_match.group(1))

        # Output tokens: after the • ↓
        output_match = re.search(r"•\s*↓\s*([\d.k]+)", line)
        if output_match:
            tokens["output"] = _parse_token_value(output_match.group(1))

        # Optional: (N reasoning) after the output value
        reasoning_match = re.search(r"\(([\d.k]+)\s+reasoning\)", line)
        if reasoning_match:
            tokens["reasoning"] = _parse_token_value(reasoning_match.group(1))

        return tokens

    def get_primary_code(self) -> str | None:
        return self.code_blocks[0] if self.code_blocks else None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "model": self.model,
            "execution_time": self.execution_time,
            "tokens": self.tokens,
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


def run_copilot_query(
    query: str, model: str | None = None, timeout: int = 180
) -> tuple[str, float]:
    start_time = time.time()
    try:
        cmd = ["copilot", "--allow-all"]
        if model:
            cmd += ["--model", model]
        cmd += ["-p", query]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
        )
        execution_time = time.time() - start_time
        output = result.stdout
        if result.stderr:
            output += f"\n\n[STDERR]\n{result.stderr}"
        return output, execution_time
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT after {timeout}s]", time.time() - start_time
    except Exception as e:
        return f"[ERROR: {str(e)}]", time.time() - start_time


def save_results(
    query_id: str,
    response: CopilotResponse,
    output_dir: Path,
    skills_enabled: bool,
):
    model_slug = model_to_slug(response.model if response.model != DEFAULT_MODEL else None)
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
                    raw_output, exec_time = run_copilot_query(prompt, model=model, timeout=timeout)
                    response = CopilotResponse(raw_output, prompt, exec_time, model=model_label)
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
                raw_output, exec_time = run_copilot_query(prompt, model=model, timeout=timeout)
                response = CopilotResponse(raw_output, prompt, exec_time, model=model_label)
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


def run_aggregation(output_dir: Path, query_ids: list[str] | None):
    sys.path.insert(0, str(SCRIPTS_DIR))
    from aggregate_metrics import aggregate_metrics

    aggregate_metrics(eval_results_dir=output_dir, query_filter=query_ids)


def main():
    parser = argparse.ArgumentParser(
        description="HoloViz skills evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python eval.py

  # Specific queries only
  python eval.py --queries earthquake_plot hvplot_basic_line

  # With-skills condition only
  python eval.py --skills with

  # Re-run execution + report without re-querying Copilot
  python eval.py --skip-generation

  # Generate only
  python eval.py --skip-execution --skip-aggregation

  # Full pipeline, longer timeout, no screenshots
  python eval.py --timeout 60 --skip-screenshots

  # Run with specific models
  python eval.py --models claude-sonnet-4.6 gpt-5.4-mini

  # Compare two models, with-skills only
  python eval.py --models claude-sonnet-4.6 gpt-5.4-mini --skills with
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
            "Model(s) to evaluate (e.g. claude-sonnet-4.6 gpt-5.4-mini). "
            "Defaults to Copilot's default model."
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
        help="Skip Copilot query step (use existing generated_code.py files)",
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

    # None in the list means "use Copilot's default model" (no --model flag)
    models: list[str | None] = args.models if args.models else [None]

    print(f"Running {len(queries)} quer(ies) × {len(models)} model(s)\n")

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
        run_aggregation(output_dir=args.output, query_ids=args.queries)

    print(f"\nDone. Results saved to: {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
