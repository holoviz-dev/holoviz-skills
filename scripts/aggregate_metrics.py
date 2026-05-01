#!/usr/bin/env python3
"""
Aggregate metrics from evaluation results.

This script:
1. Collects all metadata.json files from eval_results
2. Compares metrics between with_skills and without_skills conditions
3. Generates summary reports: evaluation_results.json and evaluation_summary.md
"""

import argparse
import json
from pathlib import Path


def collect_metrics(eval_results_dir: Path, query_filter: list[str] = None) -> dict:
    """
    Collect all metrics from evaluation results.

    Args:
        eval_results_dir: Directory containing evaluation results
        query_filter: Optional list of query IDs to include (None = all queries)

    Returns:
        Dictionary mapping query_id -> condition -> metrics
    """
    metrics = {}

    for condition in ["with_skills", "without_skills"]:
        condition_dir = eval_results_dir / condition
        if not condition_dir.exists():
            continue

        for query_dir in condition_dir.iterdir():
            if not query_dir.is_dir():
                continue

            query_id = query_dir.name

            # Skip if not in filter
            if query_filter and query_id not in query_filter:
                continue

            metadata_file = query_dir / "metadata.json"

            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            if query_id not in metrics:
                metrics[query_id] = {}

            # Extract key metrics
            metrics[query_id][condition] = {
                "has_code": metadata.get("has_code", False),
                "code_blocks_count": metadata.get("code_blocks_count", 0),
                "execution_time": metadata.get("execution_time", 0),
                "tokens_input": metadata.get("tokens", {}).get("input", 0),
                "tokens_output": metadata.get("tokens", {}).get("output", 0),
                "tokens_total": metadata.get("tokens", {}).get("input", 0)
                + metadata.get("tokens", {}).get("output", 0),
                "tokens_cached": metadata.get("tokens", {}).get("cached", 0),
                "execution_success": metadata.get("execution", {}).get("success", None),
                "execution_duration": metadata.get("execution", {}).get("execution_time", None),
            }

    return metrics


def generate_comparison_summary(metrics: dict) -> dict:
    """Generate summary comparing with_skills vs without_skills."""
    summary = {"total_queries": len(metrics), "queries": {}}

    for query_id, conditions in metrics.items():
        with_skills = conditions.get("with_skills", {})
        without_skills = conditions.get("without_skills", {})

        query_summary = {
            "with_skills": with_skills,
            "without_skills": without_skills,
            "comparison": {},
        }

        # Calculate differences
        if with_skills and without_skills:
            query_summary["comparison"] = {
                "token_difference": with_skills["tokens_output"] - without_skills["tokens_output"],
                "time_difference": with_skills["execution_time"] - without_skills["execution_time"],
                "both_have_code": with_skills["has_code"] and without_skills["has_code"],
                "both_executed": with_skills["execution_success"] is not None
                and without_skills["execution_success"] is not None,
            }

            # Execution comparison
            if (
                with_skills["execution_success"] is not None
                and without_skills["execution_success"] is not None
            ):
                query_summary["comparison"]["execution_improvement"] = (
                    with_skills["execution_success"] and not without_skills["execution_success"]
                )
                query_summary["comparison"]["execution_regression"] = (
                    not with_skills["execution_success"] and without_skills["execution_success"]
                )

        summary["queries"][query_id] = query_summary

    # Calculate aggregate statistics
    comparisons = [q["comparison"] for q in summary["queries"].values() if q["comparison"]]

    if comparisons:
        summary["aggregate"] = {
            "avg_token_difference": sum(c.get("token_difference", 0) for c in comparisons)
            / len(comparisons),
            "avg_time_difference": sum(c.get("time_difference", 0) for c in comparisons)
            / len(comparisons),
            "code_generation_rate_with": sum(
                1 for q in summary["queries"].values() if q["with_skills"].get("has_code")
            )
            / len(metrics),
            "code_generation_rate_without": sum(
                1 for q in summary["queries"].values() if q["without_skills"].get("has_code")
            )
            / len(metrics),
        }

        # Execution success rates
        executed_with = [
            q["with_skills"]
            for q in summary["queries"].values()
            if q["with_skills"].get("execution_success") is not None
        ]
        executed_without = [
            q["without_skills"]
            for q in summary["queries"].values()
            if q["without_skills"].get("execution_success") is not None
        ]

        if executed_with:
            summary["aggregate"]["execution_success_rate_with"] = sum(
                1 for e in executed_with if e["execution_success"]
            ) / len(executed_with)
        if executed_without:
            summary["aggregate"]["execution_success_rate_without"] = sum(
                1 for e in executed_without if e["execution_success"]
            ) / len(executed_without)

    return summary


def save_markdown_report(summary: dict, output_file: Path):
    """Save a human-readable summary as a Markdown file."""
    lines = [
        "# Evaluation Summary\n",
        f"**Total Queries:** {summary['total_queries']}\n",
    ]

    if "aggregate" in summary:
        agg = summary["aggregate"]
        lines += [
            "## Aggregate Statistics\n",
            "### Code Generation Rate\n",
            "| Condition | Rate |",
            "|-----------|------|",
            f"| With Skills | {agg.get('code_generation_rate_with', 0):.1%} |",
            f"| Without Skills | {agg.get('code_generation_rate_without', 0):.1%} |",
            "",
        ]

        if "execution_success_rate_with" in agg:
            lines += [
                "### Execution Success Rate\n",
                "| Condition | Rate |",
                "|-----------|------|",
                f"| With Skills | {agg.get('execution_success_rate_with', 0):.1%} |",
                f"| Without Skills | {agg.get('execution_success_rate_without', 0):.1%} |",
                "",
            ]

        lines += [
            "### Resource Usage\n",
            f"**Avg Token Difference:** {agg.get('avg_token_difference', 0):+,.0f} tokens",
            f"**Avg Response Time Difference:** {agg.get('avg_time_difference', 0):+.2f}s",
            "",
        ]

    lines.append("## Per-Query Results\n")

    for query_id, data in summary["queries"].items():
        lines.append(f"### `{query_id}`\n")
        with_skills = data.get("with_skills", {})
        without_skills = data.get("without_skills", {})

        if with_skills and without_skills:
            ws_time = f"{with_skills['execution_time']:.2f}s"
            wos_time = f"{without_skills['execution_time']:.2f}s"
            ws_tokens = f"{with_skills['tokens_output']:,}"
            wos_tokens = f"{without_skills['tokens_output']:,}"
            lines += [
                "| Metric | With Skills | Without Skills |",
                "|--------|-------------|----------------|",
                f"| Code Generated | {with_skills['has_code']} | {without_skills['has_code']} |",
                f"| Response Time | {ws_time} | {wos_time} |",
                f"| Tokens (output) | {ws_tokens} | {wos_tokens} |",
            ]

            if (
                with_skills["execution_success"] is not None
                and without_skills["execution_success"] is not None
            ):
                ws_exec = with_skills["execution_success"]
                wos_exec = without_skills["execution_success"]
                lines.append(f"| Execution Success | {ws_exec} | {wos_exec} |")

            lines.append("")

            if data.get("comparison"):
                comp = data["comparison"]
                if comp.get("execution_improvement"):
                    lines.append("**IMPROVED:** Code executes successfully with skills\n")
                elif comp.get("execution_regression"):
                    lines.append("**REGRESSION:** Code fails with skills\n")

    output_file.write_text("\n".join(lines))
    print(f"Markdown report saved: {output_file}")


def aggregate_metrics(
    eval_results_dir: Path, output_dir: Path = None, query_filter: list[str] = None
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

    print(f"\n{'=' * 70}")
    print("AGGREGATING EVALUATION METRICS")
    print(f"{'=' * 70}")
    print(f"Source: {eval_results_dir}")
    print(f"Output: {output_dir}")
    if query_filter:
        print(f"Query Filter: {', '.join(query_filter)}")
    print(f"{'=' * 70}\n")

    # Collect metrics
    print("Collecting metrics...")
    metrics = collect_metrics(eval_results_dir, query_filter)

    if not metrics:
        print("No metrics found!")
        return

    print(f"Found metrics for {len(metrics)} quer(ies)\n")

    # Generate comparison summary
    print("Generating comparison summary...")
    summary = generate_comparison_summary(metrics)

    # Save single JSON report with all data
    json_file = output_dir / "evaluation_results.json"
    with open(json_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Evaluation results saved: {json_file}")

    # Save markdown summary report
    md_file = output_dir / "evaluation_summary.md"
    save_markdown_report(summary, md_file)


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
        "--output", type=Path, help="Output directory for reports (default: same as eval-results)"
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
        eval_results_dir=args.eval_results, output_dir=args.output, query_filter=args.queries
    )

    return 0


if __name__ == "__main__":
    exit(main())
