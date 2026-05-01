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
    print(f"\n{'=' * 70}")
    print(f"Step: {description}")
    print(f"{'=' * 70}")
    print(f"Command: {' '.join(str(c) for c in cmd)}\n")

    try:
        result = subprocess.run(cmd, cwd=cwd, check=False)
        success = result.returncode == 0

        if success:
            print(f"\n{description} completed successfully")
        else:
            print(f"\n{description} failed with return code {result.returncode}")

        return success

    except Exception as e:
        print(f"\n{description} failed with error: {e}")
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

    print(f"\n{'=' * 70}")
    print("HoloViz Skills Evaluation - Full Pipeline")
    print(f"{'=' * 70}")
    print(f"Queries File: {args.queries_file}")
    print(f"Output Directory: {args.output}")
    if args.queries:
        print(f"Query Filter: {', '.join(args.queries)}")
    print(f"{'=' * 70}")

    # Track success of each step
    results = {}

    # Step 1: Run evaluation
    eval_cmd = [sys.executable, scripts_dir / "run_eval.py"]
    eval_cmd.extend(["--queries-file", str(args.queries_file)])
    eval_cmd.extend(["--output", str(args.output)])
    if args.queries:
        eval_cmd.extend(["--queries"] + args.queries)

    results["evaluation"] = run_command(eval_cmd, "Running Copilot Evaluation", cwd=scripts_dir)

    if not results["evaluation"]:
        print("\nEvaluation step failed. Stopping pipeline.")
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

        results["execution"] = run_command(exec_cmd, "Executing Generated Code", cwd=scripts_dir)

        if not results["execution"]:
            print("\nExecution step failed. Continuing to aggregation...")
    else:
        print("\nSkipping code execution (--skip-execution)")
        results["execution"] = None

    # Step 3: Aggregate metrics (optional)
    if not args.skip_aggregation:
        agg_cmd = [sys.executable, scripts_dir / "aggregate_metrics.py"]
        agg_cmd.extend(["--eval-results", str(args.output)])

        # Pass query filter to aggregation
        if args.queries:
            agg_cmd.append("--queries")
            agg_cmd.extend(args.queries)

        results["aggregation"] = run_command(agg_cmd, "Aggregating Metrics", cwd=scripts_dir)

        if not results["aggregation"]:
            print("\nAggregation step failed.")
    else:
        print("\nSkipping metrics aggregation (--skip-aggregation)")
        results["aggregation"] = None

    # Final summary
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print("\nResults:")
    print(f"  Evaluation:  {'Success' if results['evaluation'] else 'Failed'}")

    if results["execution"] is not None:
        print(f"  Execution:   {'Success' if results['execution'] else 'Failed'}")
    else:
        print("  Execution:   Skipped")

    if results["aggregation"] is not None:
        print(f"  Aggregation: {'Success' if results['aggregation'] else 'Failed'}")
    else:
        print("  Aggregation: Skipped")

    print(f"\nResults saved to: {args.output}")
    print(f"{'=' * 70}\n")

    # Return success if evaluation completed (minimum requirement)
    return 0 if results["evaluation"] else 1


if __name__ == "__main__":
    exit(main())
