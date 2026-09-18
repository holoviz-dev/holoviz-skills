#!/usr/bin/env python3
"""Deploy the historical dashboard from existing eval results."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# For Plot Outputs tab.
_PLOT_FILES = frozenset({"plot_output.html", "screenshot.png"})


def _copy_plot_artifacts(src: Path, dst: Path) -> int:
    """Copy one visual per query dir: plot HTML if present, else screenshot."""
    n = 0
    query_dirs = {p.parent for p in src.rglob("*") if p.is_file() and p.name in _PLOT_FILES}
    for query_dir in sorted(query_dirs):
        if "runs" in query_dir.relative_to(src).parts:
            continue
        plot = query_dir / "plot_output.html"
        shot = query_dir / "screenshot.png"
        chosen = plot if plot.exists() else shot if shot.exists() else None
        if chosen is None:
            continue
        target = dst / chosen.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(chosen, target)
        n += 1
    return n


def main() -> int:
    repo_root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Deploy the historical dashboard")
    parser.add_argument(
        "--eval-results",
        type=Path,
        default=repo_root / "eval_results",
        help="Output directory for eval results",
    )
    parser.add_argument(
        "--outerbounds-config-token",
        default=None,
        help="Outerbounds config token (or OUTERBOUNDS_CONFIG_TOKEN env)",
    )
    parser.add_argument(
        "--outerbounds-deploy-config",
        type=Path,
        default=repo_root / "deploy" / "outerbounds" / "compare_history.yaml",
        help="Outerbounds app config file",
    )
    parser.add_argument(
        "--skip-plot-outputs",
        action="store_true",
        help="Skip bundling plot_output.html / screenshot.png for the Plot Outputs tab.",
    )
    args = parser.parse_args()

    config_token = args.outerbounds_config_token or os.getenv("OUTERBOUNDS_CONFIG_TOKEN")
    if config_token:
        print("Configuring Outerbounds profile...")
        result = subprocess.run(["outerbounds", "configure", "--force", config_token])
        if result.returncode:
            return result.returncode

    print("Checking Outerbounds configuration...")
    result = subprocess.run(["outerbounds", "check"])
    if result.returncode:
        return result.returncode

    with tempfile.TemporaryDirectory(prefix="outerbounds-history-") as staging_root:
        staging_path = Path(staging_root)
        shutil.copy2(
            Path(__file__).parent / "compare_history.py",
            staging_path / "compare_history.py",
        )

        eval_results_dst = staging_path / "eval_results"
        eval_results_dst.mkdir(parents=True, exist_ok=True)
        for name in ("runs.json", "history_summary.json"):
            src = args.eval_results / name
            if not src.exists():
                print(f"Missing tracked eval history file: {src}")
                return 1
            shutil.copy2(src, eval_results_dst / name)

        if not args.skip_plot_outputs:
            n = _copy_plot_artifacts(args.eval_results, eval_results_dst)
            print(f"Bundled {n} plot artifact(s) into the deploy staging dir.")

        print("Deploying historical dashboard to Outerbounds...")
        return subprocess.run(
            [
                "outerbounds",
                "app",
                "deploy",
                "--config-file",
                str(args.outerbounds_deploy_config),
                "--package-src-path",
                str(staging_path),
                "--readiness-condition",
                "at_least_one_running",
            ]
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
