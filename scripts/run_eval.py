#!/usr/bin/env python3
"""
Main evaluation runner for HoloViz skills evaluation.

This script:
1. Loads test queries from eval_queries.yaml
2. Runs Copilot CLI with and without SKILL.md files enabled
3. Captures responses, token usage, and timing
4. Extracts generated code blocks
5. Saves results for comparison
"""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import yaml
from toggle_skills import disable_skills, enable_skills

# Appended to every query prompt so the model always wraps code in a fenced
# block, giving the extractor a stable target regardless of prose formatting.
CODE_OUTPUT_INSTRUCTION = (
    "\n\nRespond with a single self-contained ```python``` code block and nothing else outside it."
)


class CopilotResponse:
    """Parsed response from Copilot CLI."""

    def __init__(self, raw_output: str, query: str, execution_time: float):
        self.raw_output = raw_output
        self.query = query
        self.execution_time = execution_time
        self.code_blocks = self._extract_code_blocks()
        self.tokens = self._extract_token_usage()

    def _extract_code_blocks(self) -> list[str]:
        """Extract Python code blocks from the response (fenced ``` blocks only)."""
        pattern = r"```(?:python)?\s*\n(.*?)```"
        return re.findall(pattern, self.raw_output, re.DOTALL)

    def _extract_token_usage(self) -> dict[str, int]:
        """Extract token usage from the response footer."""
        # Pattern: Tokens ↑ 34.3k • ↓ 408 • 0 (cached) • 128 (reasoning)
        tokens = {"input": 0, "output": 0, "cached": 0, "reasoning": 0}

        # Try to find token line
        token_pattern = (
            r"Tokens\s+↑\s*([\d.k]+)\s*•\s*↓\s*([\d.k]+)\s*"
            r"•\s*([\d.k]+)\s*\(cached\)\s*•\s*([\d.k]+)\s*\(reasoning\)"
        )
        match = re.search(token_pattern, self.raw_output)

        if match:

            def parse_token_value(val: str) -> int:
                """Convert '34.3k' to 34300, or '408' to 408."""
                val = val.strip()
                if "k" in val.lower():
                    return int(float(val.lower().replace("k", "")) * 1000)
                return int(val)

            tokens["input"] = parse_token_value(match.group(1))
            tokens["output"] = parse_token_value(match.group(2))
            tokens["cached"] = parse_token_value(match.group(3))
            tokens["reasoning"] = parse_token_value(match.group(4))

        return tokens

    def get_primary_code(self) -> str | None:
        """Get the first/primary code block (usually the main answer)."""
        return self.code_blocks[0] if self.code_blocks else None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "execution_time": self.execution_time,
            "tokens": self.tokens,
            "code_blocks_count": len(self.code_blocks),
            "has_code": len(self.code_blocks) > 0,
        }


def load_queries(yaml_path: Path) -> list[dict]:
    """Load test queries from YAML file."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return data.get("queries", [])


def run_copilot_query(query: str, timeout: int = 180) -> tuple[str, float]:
    """
    Run a Copilot CLI query and capture output.

    Args:
        query: The prompt/question to ask Copilot
        timeout: Maximum execution time in seconds (default: 180s = 3 minutes)

    Returns:
        Tuple of (raw_output, execution_time_seconds)
    """
    start_time = time.time()

    try:
        # Run copilot CLI with the query
        result = subprocess.run(
            ["copilot", "--allow-all", "-p", query],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent,  # Run from repo root
        )

        execution_time = time.time() - start_time

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += f"\n\n[STDERR]\n{result.stderr}"

        return output, execution_time

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        return f"[TIMEOUT after {timeout}s]", execution_time

    except Exception as e:
        execution_time = time.time() - start_time
        return f"[ERROR: {str(e)}]", execution_time


def save_results(query_id: str, response: CopilotResponse, output_dir: Path, skills_enabled: bool):
    """
    Save evaluation results to disk.

    Args:
        query_id: Unique identifier for the query
        response: Parsed Copilot response
        output_dir: Base output directory
        skills_enabled: Whether skills were enabled for this run
    """
    # Determine subdirectory
    subdir = "with_skills" if skills_enabled else "without_skills"
    query_dir = output_dir / subdir / query_id
    query_dir.mkdir(parents=True, exist_ok=True)

    # Save raw response
    with open(query_dir / "response.txt", "w") as f:
        f.write(response.raw_output)

    # Save metadata
    metadata = response.to_dict()
    metadata["skills_enabled"] = skills_enabled
    with open(query_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Save primary code block if available
    primary_code = response.get_primary_code()
    if primary_code:
        with open(query_dir / "generated_code.py", "w") as f:
            f.write(primary_code)
        print(f"  Saved code ({len(primary_code)} chars)")
    else:
        print("  No code block found in response")

    # Save all code blocks if multiple
    if len(response.code_blocks) > 1:
        for i, code in enumerate(response.code_blocks):
            with open(query_dir / f"code_block_{i}.py", "w") as f:
                f.write(code)


def run_evaluation(
    queries_file: Path,
    output_dir: Path,
    query_ids: list[str] | None = None,
    skip_without_skills: bool = False,
    skip_with_skills: bool = False,
):
    """
    Run the full evaluation pipeline.

    Args:
        queries_file: Path to eval_queries.yaml
        output_dir: Output directory for results
        query_ids: Optional list of specific query IDs to run (default: all)
        skip_without_skills: Skip the without-skills evaluation
        skip_with_skills: Skip the with-skills evaluation
    """
    # Load queries
    queries = load_queries(queries_file)

    # Filter queries if specific IDs requested
    if query_ids:
        queries = [q for q in queries if q["id"] in query_ids]

    if not queries:
        print("No queries to evaluate!")
        return

    print(f"Running {len(queries)} quer(ies)\n")

    repo_root = Path(__file__).parent.parent

    # Run evaluation for each query
    for i, query in enumerate(queries, 1):
        query_id = query["id"]
        prompt = query["prompt"].rstrip() + CODE_OUTPUT_INSTRUCTION
        timeout = query.get("timeout", 180)

        print(f"[{i}/{len(queries)}] {query_id}")

        # Evaluate WITHOUT skills
        if not skip_without_skills:
            print("Running WITHOUT skills...")
            disable_skills(repo_root)

            try:
                raw_output, exec_time = run_copilot_query(prompt, timeout)
                response = CopilotResponse(raw_output, prompt, exec_time)

                tok = response.tokens
                print(f"  Completed in {exec_time:.2f}s | Tokens: ↑{tok['input']} ↓{tok['output']}")

                save_results(query_id, response, output_dir, skills_enabled=False)
            finally:
                # Re-enable skills for next run
                enable_skills(repo_root)

        # Evaluate WITH skills
        if not skip_with_skills:
            print("Running WITH skills...")

            raw_output, exec_time = run_copilot_query(prompt, timeout)
            response = CopilotResponse(raw_output, prompt, exec_time)

            tok = response.tokens
            print(f"  Completed in {exec_time:.2f}s | Tokens: ↑{tok['input']} ↓{tok['output']}")

            save_results(query_id, response, output_dir, skills_enabled=True)

        print(f"{'─' * 60}")

    print("\nEvaluation complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Run HoloViz skills evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all queries (both conditions)
  python run_eval.py

  # Run specific queries only
  python run_eval.py --queries hvplot_basic_line

  # Run only the with-skills condition
  python run_eval.py --skills with

  # Run only the without-skills condition
  python run_eval.py --skills without
        """,
    )

    parser.add_argument(
        "--queries-file",
        type=Path,
        default=Path(__file__).parent / "eval_queries.yaml",
        help="Path to queries YAML file (default: eval_queries.yaml)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Output directory (default: ../eval_results)",
    )

    parser.add_argument("--queries", nargs="+", help="Specific query IDs to run (default: all)")

    parser.add_argument(
        "--skills",
        choices=["both", "with", "without"],
        default="both",
        help="Which condition(s) to evaluate: 'both' (default), 'with', or 'without'",
    )

    args = parser.parse_args()

    # Validate
    if not args.queries_file.exists():
        print(f"Error: Queries file not found: {args.queries_file}")
        return 1

    # Run evaluation
    run_evaluation(
        queries_file=args.queries_file,
        output_dir=args.output,
        query_ids=args.queries,
        skip_without_skills=args.skills == "with",
        skip_with_skills=args.skills == "without",
    )

    return 0


if __name__ == "__main__":
    exit(main())
