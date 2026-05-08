#!/usr/bin/env python3
"""
Quick test to verify the evaluation system is set up correctly.

This script checks:
1. Python version
2. Required dependencies (matches feature.eval.dependencies in pixi.toml)
3. Playwright availability (required for screenshot capture)
4. Copilot CLI availability
5. SKILL.md files
6. Query file validity
7. Evaluation scripts
"""

import argparse
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def _run_check(label: str, fn) -> bool:
    """
    Run a check function, capturing its output.
    On pass: silent. On fail: print label + captured output.
    """
    buf = io.StringIO()
    with redirect_stdout(buf):
        passed = fn()
    if not passed:
        print(f"✗ FAIL  {label}")
        detail = buf.getvalue().strip()
        if detail:
            for line in detail.splitlines():
                print(f"        {line}")
    return passed


def check_python_version():
    """Check if Python version is >= 3.12"""
    version = sys.version_info
    required = (3, 12)
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    if (version.major, version.minor) >= required:
        return True
    else:
        print(f"Python {required[0]}.{required[1]}+ required")
        return False


def check_dependency(module_name, import_name=None):
    """Check if a Python module is installed"""
    import_name = import_name or module_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        print(f"{module_name} is NOT installed")
        return False


def check_dependencies():
    """Check all runtime dependencies from feature.eval.dependencies."""
    results = [
        check_dependency("PyYAML", "yaml"),
        check_dependency("pandas"),
        check_dependency("matplotlib"),
        check_dependency("bokeh"),
        check_dependency("hvplot"),
        check_dependency("holoviews"),
    ]
    return all(results)


def check_playwright():
    """Check if Playwright and the Chromium browser are available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print("playwright is NOT installed (required for screenshots)")
        print("Install with: pip install playwright && playwright install chromium")
        return False

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as e:
        print(f"Chromium browser is NOT available: {e}")
        print("Run: playwright install chromium")
        return False


def check_copilot_cli():
    """Check if Copilot CLI is available"""
    try:
        result = subprocess.run(["copilot", "--help"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True
        else:
            print("Copilot CLI returned a non-zero exit code")
            return False
    except FileNotFoundError:
        print("Copilot CLI is NOT installed or not in PATH")
        print(
            "See: https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli"
        )
        return False
    except Exception as e:
        print(f"Error checking Copilot CLI: {e}")
        return False


def check_skill_files():
    """Check if SKILL.md files exist"""
    repo_root = Path(__file__).parent.parent
    skill_files = list(repo_root.rglob("SKILL.md"))

    exclude_dirs = {".git", "node_modules", "__pycache__", ".cache", "site", ".pixi"}
    skill_files = [
        f for f in skill_files if not any(parent.name in exclude_dirs for parent in f.parents)
    ]

    if skill_files:
        return True
    else:
        print("No SKILL.md files found")
        return True  # Not a hard failure


def check_queries_file():
    """Check if eval_queries.yaml exists and is valid"""
    queries_file = Path(__file__).parent / "eval_queries.yaml"

    if not queries_file.exists():
        print(f"eval_queries.yaml not found at {queries_file}")
        return False

    if yaml is None:
        return True

    try:
        with open(queries_file) as f:
            data = yaml.safe_load(f)

        queries = data.get("queries", [])
        if not queries:
            print("eval_queries.yaml contains no queries")
            return False
        return True

    except Exception as e:
        print(f"Error parsing eval_queries.yaml: {e}")
        return False


def check_scripts():
    """Check if all evaluation scripts exist"""
    scripts_dir = Path(__file__).parent
    required_scripts = [
        "eval.py",
        "execute_generated.py",
        "aggregate_metrics.py",
        "toggle_skills.py",
    ]

    missing = [s for s in required_scripts if not (scripts_dir / s).exists()]
    if missing:
        for s in missing:
            print(f"{s} NOT FOUND")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify the evaluation system is set up correctly")
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Skip the Playwright/Chromium check (use when running eval-no-screenshots)",
    )
    args = parser.parse_args()

    checks = {
        "Python Version": lambda: check_python_version(),
        "Dependencies": lambda: check_dependencies(),
        "Copilot CLI": lambda: check_copilot_cli(),
        "SKILL.md Files": lambda: check_skill_files(),
        "Queries File": lambda: check_queries_file(),
        "Evaluation Scripts": lambda: check_scripts(),
    }
    if not args.skip_screenshots:
        checks["Playwright"] = lambda: check_playwright()

    results = {label: _run_check(label, fn) for label, fn in checks.items()}

    if all(results.values()):
        print("eval-check passed")
        return 0
    else:
        print("\nSome checks failed. Common fixes:")
        print("  - Install dependencies: pixi install")
        print("  - Install Playwright browser: playwright install chromium")
        print("  - Verify you're in the root directory")
        return 1


if __name__ == "__main__":
    exit(main())
