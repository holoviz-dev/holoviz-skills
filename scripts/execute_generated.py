#!/usr/bin/env python3
"""
Execute generated code and capture screenshots.

WARNING: This script executes Copilot-generated Python code in a subprocess.
Although execution is confined to a temporary working directory, the subprocess
runs with the same user permissions and has full network access. Only run this
against code you are willing to execute locally.

This script:
1. Finds all generated_code.py files in eval_results
2. Executes each in a temporary working directory
3. Captures stdout/stderr and execution status
4. Copies expected output files (plot_output.html/png) back to the results directory
5. Takes screenshots of visual outputs (plots, dashboards)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

# Appended to every generated script before execution.
# Tries to save the last plot object to plot_output.html/png so the executor
# can copy it back to the results directory.
_HEADLESS_SAVE_CODE = textwrap.dedent("""
    # AUTO-ADDED: Save plot output
    import sys
    _plot_saved = False

    def _try_save_plot(obj):
        \"\"\"Attempt to save a plot object to plot_output.html. Returns True on success.\"\"\"
        try:
            import holoviews as hv
            import holoviews.core
            if isinstance(obj, holoviews.core.Dimensioned):
                hv.save(obj, 'plot_output.html')
                print('Plot saved to plot_output.html')
                return True
        except Exception:
            pass
        try:
            from bokeh.model import Model
            from bokeh.io import output_file, save as bokeh_save
            if isinstance(obj, Model):
                output_file('plot_output.html')
                bokeh_save(obj)
                print('Plot saved to plot_output.html')
                return True
        except Exception:
            pass
        return False

    # 1. Check well-known variable names first
    for _var_name in ['plot', 'fig', 'p', 'chart', 'viz', '_last_plot']:
        if _var_name in globals() and globals()[_var_name] is not None:
            if _try_save_plot(globals()[_var_name]):
                _plot_saved = True
                break

    # 2. Scan all globals for any HoloViews/Bokeh object
    if not _plot_saved:
        try:
            import holoviews.core
            from bokeh.model import Model
            for _v in list(globals().values()):
                if isinstance(_v, (holoviews.core.Dimensioned, Model)):
                    if _try_save_plot(_v):
                        _plot_saved = True
                        break
        except Exception:
            pass

    # 3. Try matplotlib if not saved yet
    if not _plot_saved:
        try:
            import matplotlib.pyplot as plt
            if plt.get_fignums():
                plt.savefig('plot_output.png', dpi=150, bbox_inches='tight')
                print('Plot saved to plot_output.png')
                _plot_saved = True
        except Exception:
            pass

    if not _plot_saved:
        print('Warning: Could not detect or save plot output')
""")


class CodeExecutor:
    """Execute generated Python code in isolation."""

    def __init__(self, timeout: int = 30, capture_screenshots: bool = True):
        self.timeout = timeout
        self.capture_screenshots = capture_screenshots

    def execute(self, code_file: Path, query_dir: Path) -> dict:
        """
        Execute a Python file and capture results.

        The code runs inside a temporary working directory so it cannot
        overwrite files in the repository. Only known output files
        (plot_output.html, plot_output.png) are copied back to query_dir.

        Args:
            code_file: Path to generated_code.py
            query_dir: Directory where results are saved

        Returns:
            Dictionary with execution results
        """
        start_time = time.time()

        # Modify code to save plots
        code_content = code_file.read_text()
        modified_code = self._modify_code_for_headless(code_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Write modified code into the temp directory
            temp_file = tmp_path / "generated_code_modified.py"
            temp_file.write_text(modified_code)

            try:
                exec_env = {**os.environ, "MPLBACKEND": "Agg"}
                result = subprocess.run(
                    [sys.executable, str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir,
                    env=exec_env,
                )

                execution_time = time.time() - start_time

                # Save execution log to the persistent results directory
                log_content = (
                    f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}\n"
                )
                log_file = query_dir / "execution.log"
                log_file.write_text(log_content)

                success = result.returncode == 0

                # Copy only the expected output files back to query_dir
                for output_name in ("plot_output.html", "plot_output.png"):
                    src = tmp_path / output_name
                    if src.exists():
                        shutil.copy(src, query_dir / output_name)

                # Capture screenshot if execution succeeded and screenshots enabled
                screenshot_path = None
                if success and self.capture_screenshots:
                    screenshot_path = self._capture_screenshot(query_dir)

                return {
                    "success": success,
                    "returncode": result.returncode,
                    "execution_time": execution_time,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "has_output": bool(result.stdout),
                    "screenshot": screenshot_path is not None,
                }

            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "returncode": -1,
                    "execution_time": execution_time,
                    "error": f"Timeout after {self.timeout}s",
                    "has_output": False,
                    "screenshot": False,
                }

            except Exception as e:
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "returncode": -1,
                    "execution_time": execution_time,
                    "error": str(e),
                    "has_output": False,
                    "screenshot": False,
                }

    def _modify_code_for_headless(self, code: str) -> str:
        """
        Modify code to save plots to files instead of displaying them.

        Handles common patterns:
        - matplotlib: plt.show() -> plt.savefig()
        - hvplot/bokeh: save plot object to HTML
        """
        # Comment out any display calls
        modified_code = code.replace("plt.show()", "# plt.show() # commented by eval")
        modified_code = re.sub(r"(?<!\w)show\(\)", "# show() # commented by eval", modified_code)

        # Use AST to detect a bare expression as the last statement and assign it
        # to _last_plot so the globals scan can find it. This correctly handles
        # multi-line expressions like df.hvplot.points(\n    ...\n).
        try:
            import ast as _ast

            tree = _ast.parse(modified_code)
            if tree.body and isinstance(tree.body[-1], _ast.Expr):
                last_stmt = tree.body[-1]
                start = last_stmt.lineno - 1  # 0-indexed
                lines = modified_code.splitlines()
                prefix = "\n".join(lines[:start])
                expr_src = "\n".join(lines[start:])
                modified_code = prefix + "\n_last_plot = " + expr_src + "\n"
        except Exception:
            pass  # Leave code unmodified if AST parse fails

        return modified_code + _HEADLESS_SAVE_CODE

    def _capture_screenshot(self, query_dir: Path) -> Path | None:
        """
        Capture screenshot of plot output.

        Looks for plot_output.html (Bokeh/hvPlot) or plot_output.png (matplotlib).

        Args:
            query_dir: Directory containing the output files

        Returns:
            Path to screenshot file, or None if capture failed
        """
        html_file = query_dir / "plot_output.html"
        png_file = query_dir / "plot_output.png"

        # If PNG already exists (matplotlib), just return it
        if png_file.exists():
            screenshot_path = query_dir / "screenshot.png"
            # Copy/rename to screenshot.png for consistency
            shutil.copy(png_file, screenshot_path)
            return screenshot_path

        # If HTML exists, use Playwright to screenshot it
        if html_file.exists():
            try:
                from playwright.sync_api import sync_playwright

                screenshot_path = query_dir / "screenshot.png"

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(viewport={"width": 1200, "height": 800})

                    # Load the HTML file
                    page.goto(f"file://{html_file.absolute()}")

                    # Wait for Bokeh to render
                    page.wait_for_timeout(2000)  # 2 seconds

                    # Take screenshot
                    page.screenshot(path=screenshot_path, full_page=False)

                    browser.close()

                return screenshot_path
            except ImportError:
                print("Playwright not installed, skipping screenshot")
                print("Install with: pip install playwright && playwright install chromium")
                return None
            except Exception as e:
                print(f"Screenshot capture failed: {e}")
                return None

        return None


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


def execute_all_code(
    eval_results_dir: Path,
    timeout: int = 30,
    query_ids: list[str] | None = None,
    skip_screenshots: bool = False,
):
    """
    Execute all generated code files.

    Args:
        eval_results_dir: Directory containing evaluation results
        timeout: Execution timeout in seconds
        query_ids: Optional list of specific query IDs to execute
        skip_screenshots: Skip screenshot capture
    """
    code_files = find_generated_code_files(eval_results_dir)

    # Filter by query IDs if specified
    if query_ids:
        code_files = [cf for cf in code_files if cf["query_id"] in query_ids]

    if not code_files:
        print("No generated code files found!")
        return

    screenshots = "off" if skip_screenshots else "on"
    print(
        f"Executing {len(code_files)} generated code file(s)"
        f" (timeout: {timeout}s, screenshots: {screenshots})\n"
    )

    executor = CodeExecutor(timeout=timeout, capture_screenshots=not skip_screenshots)
    results_summary = []

    for i, cf in enumerate(code_files, 1):
        query_id = cf["query_id"]
        condition = cf["condition"]

        print(f"[{i}/{len(code_files)}] {query_id} ({condition})")

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

        if result.get("screenshot"):
            print("  screenshot: screenshot.png")

        results_summary.append(
            {
                "query_id": query_id,
                "condition": condition,
                "success": result["success"],
                "execution_time": result["execution_time"],
                "has_screenshot": result.get("screenshot", False),
            }
        )

    # Print summary
    success_count = sum(1 for r in results_summary if r["success"])
    fail_count = len(results_summary) - success_count
    screenshot_count = sum(1 for r in results_summary if r.get("has_screenshot"))

    parts = [f"{success_count}/{len(results_summary)} succeeded"]
    if fail_count:
        parts.append(f"{fail_count} failed")
    if screenshot_count:
        parts.append(f"{screenshot_count} screenshots")
    print(f"\nExecution complete: {', '.join(parts)}")


def main():
    parser = argparse.ArgumentParser(
        description="Execute generated code and capture outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Execute all generated code\n"
            "  python execute_generated.py\n\n"
            "  # Execute specific queries only\n"
            "  python execute_generated.py --queries hvplot_basic_line\n\n"
            "  # Use longer timeout for complex code\n"
            "  python execute_generated.py --timeout 60\n\n"
            "  # Skip screenshot capture\n"
            "  python execute_generated.py --skip-screenshots\n"
        ),
    )

    parser.add_argument(
        "--eval-results",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Evaluation results directory (default: ../eval_results)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Execution timeout in seconds (default: 30)",
    )

    parser.add_argument("--queries", nargs="+", help="Specific query IDs to execute (default: all)")

    parser.add_argument(
        "--skip-screenshots", action="store_true", help="Skip screenshot capture (faster)"
    )

    args = parser.parse_args()

    if not args.eval_results.exists():
        print(f"Error: Evaluation results directory not found: {args.eval_results}")
        return 1

    execute_all_code(
        eval_results_dir=args.eval_results,
        timeout=args.timeout,
        query_ids=args.queries,
        skip_screenshots=args.skip_screenshots,
    )

    return 0


if __name__ == "__main__":
    exit(main())
