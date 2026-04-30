#!/usr/bin/env python3
"""
Quick test to verify the evaluation system is set up correctly.

This script checks:
1. Python version
2. Required dependencies
3. Copilot CLI availability
4. SKILL.md files
5. Query file validity
"""

import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is >= 3.12"""
    version = sys.version_info
    required = (3, 12)

    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if (version.major, version.minor) >= required:
        print("Python version is compatible\n")
        return True
    else:
        print(f"Python {required[0]}.{required[1]}+ required\n")
        return False


def check_dependency(module_name, import_name=None):
    """Check if a Python module is installed"""
    import_name = import_name or module_name
    try:
        __import__(import_name)
        print(f"{module_name} is installed")
        return True
    except ImportError:
        print(f"{module_name} is NOT installed")
        return False


def check_copilot_cli():
    """Check if Copilot CLI is available"""
    try:
        result = subprocess.run(["copilot", "--help"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("Copilot CLI is available")
            return True
        else:
            print("Copilot CLI returned error")
            return False
    except FileNotFoundError:
        print("Copilot CLI is NOT installed or not in PATH")
        return False
    except Exception as e:
        print(f"Error checking Copilot CLI: {e}")
        return False


def check_skill_files():
    """Check if SKILL.md files exist"""
    repo_root = Path(__file__).parent.parent
    skill_files = list(repo_root.rglob("SKILL.md"))

    # Filter out certain directories
    exclude_dirs = {".git", "node_modules", "__pycache__", ".cache", "site"}
    skill_files = [
        f for f in skill_files if not any(parent.name in exclude_dirs for parent in f.parents)
    ]

    print(f"Found {len(skill_files)} SKILL.md file(s):")
    for sf in skill_files:
        print(f"  - {sf.relative_to(repo_root)}")

    if skill_files:
        print("SKILL.md files found\n")
        return True
    else:
        print("No SKILL.md files found (this is OK for testing)\n")
        return True


def check_queries_file():
    """Check if eval_queries.yaml exists and is valid"""
    queries_file = Path(__file__).parent / "eval_queries.yaml"

    if not queries_file.exists():
        print(f"eval_queries.yaml not found at {queries_file}")
        return False

    print("eval_queries.yaml exists")

    try:
        import yaml

        with open(queries_file) as f:
            data = yaml.safe_load(f)

        queries = data.get("queries", [])
        print(f"YAML is valid, contains {len(queries)} queries")

        for query in queries:
            query_id = query.get("id", "UNKNOWN")
            print(f"  - {query_id}")

        print()
        return True

    except ImportError:
        print("PyYAML not installed, cannot validate YAML content")
        print("  Install with: pip install pyyaml or pixi install\n")
        return True
    except Exception as e:
        print(f"Error parsing YAML: {e}\n")
        return False


def check_scripts():
    """Check if all evaluation scripts exist"""
    scripts_dir = Path(__file__).parent
    required_scripts = [
        "run_eval.py",
        "execute_generated.py",
        "aggregate_metrics.py",
        "toggle_skills.py",
        "run_full_evaluation.py",
    ]

    all_exist = True
    for script in required_scripts:
        script_path = scripts_dir / script
        if script_path.exists():
            print(f"{script}")
        else:
            print(f"{script} NOT FOUND")
            all_exist = False

    print()
    return all_exist


def main():
    print("=" * 70)
    print("HoloViz Skills Evaluation - System Check")
    print("=" * 70)
    print()

    checks = {
        "Python Version": check_python_version(),
        "Dependencies": all(
            [
                check_dependency("PyYAML", "yaml"),
            ]
        ),
        "Copilot CLI": check_copilot_cli(),
        "SKILL.md Files": check_skill_files(),
        "Queries File": check_queries_file(),
        "Evaluation Scripts": check_scripts(),
    }

    print("=" * 70)
    print("Summary")
    print("=" * 70)

    for check_name, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {check_name}")

    print()

    if all(checks.values()):
        print("All checks passed! System is ready for evaluation.")
        print()
        print("Next steps:")
        print("  1. Run: python run_full_evaluation.py")
        print("  2. Or see EVALUATION_GUIDE.md for detailed usage")
        return 0
    else:
        print("Some checks failed. Please address the issues above.")
        print()
        print("Common fixes:")
        print("  - Install PyYAML: pip install pyyaml or pixi install")
        print(
            "  - Install Copilot CLI: https://docs.github.com/en/copilot/github-copilot-in-the-cli"
        )
        print("  - Verify you're in the scripts/ directory")
        return 1


if __name__ == "__main__":
    exit(main())
