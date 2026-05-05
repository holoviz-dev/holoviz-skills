#!/usr/bin/env python3
"""
Full evaluation pipeline orchestrator.

This script runs the complete evaluation workflow:
1. Run evaluation (with/without skills)
2. Execute generated code
3. Aggregate metrics and generate reports

Usage:
    python run_full_evaluation.py [options]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str, cwd: Path = None) -> bool:
    """
    Run a command and return success status.

    Args:
        cmd: Command and arguments as list
        description: Description for user
        cwd: Working directory

    Returns:
        True if successful, False otherwise
    """
    print(f"→ {description}...", flush=True)

    try:
        result = subprocess.run(cmd, cwd=cwd, check=False)
        success = result.returncode == 0

        if not success:
            print(f"  ✗ {description} failed (exit code {result.returncode})")

        return success

    except Exception as e:
        print(f"  ✗ {description} failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run complete HoloViz skills evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Full Pipeline Steps:
  1. Run Copilot queries with and without skills
  2. Execute generated code
  3. Aggregate metrics and generate reports

Examples:
  # Run full evaluation
  python run_full_evaluation.py

  # Evaluate specific queries only
  python run_full_evaluation.py --queries hvplot_basic_line

  # Evaluate only the with-skills condition
  python run_full_evaluation.py --skills with

  # Skip code execution
  python run_full_evaluation.py --skip-execution

  # Custom output directory
  python run_full_evaluation.py --output ./my_results
        """,
    )

    parser.add_argument(
        "--queries", nargs="+", help="Specific query IDs to evaluate (default: all)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Output directory (default: ../eval_results)",
    )

    parser.add_argument(
        "--skills",
        choices=["both", "with", "without"],
        default="both",
        help="Which condition(s) to evaluate: 'both' (default), 'with', or 'without'",
    )

    parser.add_argument(
        "--skip-execution",
        action="store_true",
        help="Skip code execution step (only generate code)",
    )

    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Skip screenshot capture during code execution (faster)",
    )

    parser.add_argument(
        "--skip-aggregation", action="store_true", help="Skip metrics aggregation step"
    )

    parser.add_argument(
        "--timeout", type=int, default=30, help="Execution timeout in seconds (default: 30)"
    )

    parser.add_argument(
        "--queries-file",
        type=Path,
        default=Path(__file__).parent / "eval_queries.yaml",
        help="Path to queries YAML file",
    )

    args = parser.parse_args()

    scripts_dir = Path(__file__).parent

    # Track success of each step
    results = {}

    # Step 1: Run evaluation
    eval_cmd = [sys.executable, scripts_dir / "run_eval.py"]
    eval_cmd.extend(["--queries-file", str(args.queries_file)])
    eval_cmd.extend(["--output", str(args.output)])
    eval_cmd.extend(["--skills", args.skills])
    if args.queries:
        eval_cmd.extend(["--queries"] + args.queries)

    results["evaluation"] = run_command(eval_cmd, "Running Copilot evaluation", cwd=scripts_dir)

    if not results["evaluation"]:
        return 1

    # Step 2: Execute generated code (optional)
    if not args.skip_execution:
        exec_cmd = [sys.executable, scripts_dir / "execute_generated.py"]
        exec_cmd.extend(["--eval-results", str(args.output)])
        exec_cmd.extend(["--timeout", str(args.timeout)])
        if args.queries:
            exec_cmd.extend(["--queries"] + args.queries)
        if args.skip_screenshots:
            exec_cmd.append("--skip-screenshots")

        results["execution"] = run_command(exec_cmd, "Executing generated code", cwd=scripts_dir)

    # Step 3: Aggregate metrics (optional)
    if not args.skip_aggregation:
        agg_cmd = [sys.executable, scripts_dir / "aggregate_metrics.py"]
        agg_cmd.extend(["--eval-results", str(args.output)])
        if args.queries:
            agg_cmd.extend(["--queries"] + args.queries)

        results["aggregation"] = run_command(agg_cmd, "Aggregating metrics", cwd=scripts_dir)

    print(f"\nDone. Results saved to: {args.output}")

    return 0 if results["evaluation"] else 1


if __name__ == "__main__":
    exit(main())
