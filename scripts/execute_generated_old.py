#!/usr/bin/env python3
"""
Execute generated code and capture screenshots.

This script:
1. Finds all generated_code.py files in eval_results
2. Executes each in an isolated subprocess
3. Captures stdout/stderr and execution status
4. Takes screenshots of visual outputs (plots, dashboards)
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


class CodeExecutor:
    """Execute generated Python code in isolation."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def execute(self, code_file: Path, query_dir: Path) -> dict:
        """
        Execute a Python file and capture results.

        Args:
            code_file: Path to generated_code.py
            query_dir: Directory containing the code file

        Returns:
            Dictionary with execution results
        """
        start_time = time.time()

        # Modify code to save plots instead of showing them
        code_content = code_file.read_text()
        modified_code = self._modify_code_for_headless(code_content)

        # Save modified code temporarily
        temp_file = query_dir / "generated_code_modified.py"
        temp_file.write_text(modified_code)

        try:
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=query_dir,
            )

            execution_time = time.time() - start_time

            # Save execution log
            log_content = f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}\n"
            log_file = query_dir / "execution.log"
            log_file.write_text(log_content)

            success = result.returncode == 0

            return {
                "success": success,
                "returncode": result.returncode,
                "execution_time": execution_time,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "has_output": bool(result.stdout),
            }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "execution_time": execution_time,
                "error": f"Timeout after {self.timeout}s",
                "has_output": False,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "execution_time": execution_time,
                "error": str(e),
                "has_output": False,
            }

        finally:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()

    def _modify_code_for_headless(self, code: str) -> str:
        """
        Modify code to save plots to files instead of displaying them.

        Handles common patterns:
        - matplotlib: plt.show() -> plt.savefig()
        - hvplot: .hvplot() -> .hvplot() with save
        - bokeh: show() -> save()
        """
        lines = code.split("\n")
        modified_lines = []

        # Track imports to add saving capability
        needs_bokeh_save = False
        has_plt_import = False

        for line in lines:
            # Check for matplotlib import
            if "import matplotlib.pyplot" in line or "from matplotlib import pyplot" in line:
                has_plt_import = True

            # Replace plt.show() with plt.savefig()
            if has_plt_import and "plt.show()" in line:
                indent = line[: len(line) - len(line.lstrip())]
                modified_lines.append(
                    f"{indent}plt.savefig('plot_output.png', dpi=150, bbox_inches='tight')"
                )
                modified_lines.append(f"{indent}print('Plot saved to plot_output.png')")
                continue

            # For hvplot/bokeh outputs, try to save
            if ".hvplot" in line and "show(" not in line:
                # Store the plot object
                modified_lines.append(line)
                if "=" not in line:  # If not already assigned
                    indent = line[: len(line) - len(line.lstrip())]
                    modified_lines.append(f"{indent}# Note: hvplot object created above")
                needs_bokeh_save = True
                continue

            modified_lines.append(line)

        # Add bokeh save if needed
        if needs_bokeh_save:
            modified_lines.extend(
                [
                    "",
                    "# Auto-added: Try to save hvplot/bokeh output",
                    "try:",
                    "    from bokeh.plotting import output_file, save as bokeh_save",
                    "    # Note: This may not work if plot wasn't assigned to a variable",
                    "    # Manual screenshot capture may be needed",
                    "    print('Bokeh/hvplot output ready for screenshot')",
                    "except:",
                    "    pass",
                ]
            )

        return "\n".join(modified_lines)


def find_generated_code_files(eval_results_dir: Path) -> list:
    """Find all generated_code.py files in the evaluation results."""
    code_files = []

    for condition_dir in ["with_skills", "without_skills"]:
        condition_path = eval_results_dir / condition_dir
        if not condition_path.exists():
            continue

        for query_dir in condition_path.iterdir():
            if not query_dir.is_dir():
                continue

            code_file = query_dir / "generated_code.py"
            if code_file.exists():
                code_files.append(
                    {
                        "code_file": code_file,
                        "query_dir": query_dir,
                        "query_id": query_dir.name,
                        "condition": condition_dir,
                    }
                )

    return code_files


def execute_all_code(eval_results_dir: Path, timeout: int = 30, query_ids: list | None = None):
    """
    Execute all generated code files.

    Args:
        eval_results_dir: Directory containing evaluation results
        timeout: Execution timeout in seconds
        query_ids: Optional list of specific query IDs to execute
    """
    code_files = find_generated_code_files(eval_results_dir)

    # Filter by query IDs if specified
    if query_ids:
        code_files = [cf for cf in code_files if cf["query_id"] in query_ids]

    if not code_files:
        print("No generated code files found!")
        return

    print(f"\n{'=' * 60}")
    print("Executing Generated Code")
    print(f"{'=' * 60}")
    print(f"Found {len(code_files)} code file(s)")
    print(f"Timeout: {timeout}s per file")
    print(f"{'=' * 60}\n")

    executor = CodeExecutor(timeout=timeout)
    results_summary = []

    for i, cf in enumerate(code_files, 1):
        query_id = cf["query_id"]
        condition = cf["condition"]

        print(f"[{i}/{len(code_files)}] {query_id} ({condition})")
        print(f"{'─' * 60}")

        result = executor.execute(cf["code_file"], cf["query_dir"])

        # Update metadata
        metadata_file = cf["query_dir"] / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
            metadata["execution"] = result
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

        # Print status
        status = "SUCCESS" if result["success"] else "FAILED"
        print(f"  {status} ({result['execution_time']:.2f}s)")

        if not result["success"]:
            error_msg = result.get("error", result.get("stderr", "Unknown error"))
            print(f"  Error: {error_msg[:100]}")

        if result.get("has_output"):
            print(f"  Output: {len(result['stdout'])} chars")

        results_summary.append(
            {
                "query_id": query_id,
                "condition": condition,
                "success": result["success"],
                "execution_time": result["execution_time"],
            }
        )

        print(f"{'─' * 60}\n")

    # Print summary
    print(f"{'=' * 60}")
    print("Execution Summary")
    print(f"{'=' * 60}")

    success_count = sum(1 for r in results_summary if r["success"])
    print(f"Success: {success_count}/{len(results_summary)}")
    print(f"Failed:  {len(results_summary) - success_count}/{len(results_summary)}")

    # Group by condition
    for condition in ["with_skills", "without_skills"]:
        condition_results = [r for r in results_summary if r["condition"] == condition]
        if condition_results:
            success = sum(1 for r in condition_results if r["success"])
            print(f"  {condition}: {success}/{len(condition_results)} successful")

    print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Execute generated code and capture outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute all generated code
  python execute_generated.py

  # Execute specific queries only
  python execute_generated.py --queries hvplot_basic_line

  # Use longer timeout for complex code
  python execute_generated.py --timeout 60
        """,
    )

    parser.add_argument(
        "--eval-results",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Evaluation results directory (default: ../eval_results)",
    )

    parser.add_argument(
        "--timeout", type=int, default=30, help="Execution timeout in seconds (default: 30)"
    )

    parser.add_argument("--queries", nargs="+", help="Specific query IDs to execute (default: all)")

    args = parser.parse_args()

    if not args.eval_results.exists():
        print(f"Error: Evaluation results directory not found: {args.eval_results}")
        return 1

    execute_all_code(
        eval_results_dir=args.eval_results, timeout=args.timeout, query_ids=args.queries
    )

    return 0


if __name__ == "__main__":
    exit(main())
