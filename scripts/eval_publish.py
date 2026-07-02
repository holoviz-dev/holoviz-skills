#!/usr/bin/env python3
"""Deploy the historical dashboard from existing eval results."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Deploy the historical dashboard")
    parser.add_argument(
        "--eval-results",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
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

    args = parser.parse_args()

    config_token = args.outerbounds_config_token or os.getenv("OUTERBOUNDS_CONFIG_TOKEN")
    if config_token:
        configure_cmd = ["outerbounds", "configure", "--force", config_token]
        print("Configuring Outerbounds profile...")
        configure_result = subprocess.run(configure_cmd)
        if configure_result.returncode != 0:
            return configure_result.returncode

    check_cmd = ["outerbounds", "check"]
    print("Checking Outerbounds configuration...")
    check_result = subprocess.run(check_cmd)
    if check_result.returncode != 0:
        return check_result.returncode

    with tempfile.TemporaryDirectory(prefix="outerbounds-history-") as staging_root:
        staging_path = Path(staging_root)
        shutil.copy2(
            Path(__file__).parent / "compare_history.py", staging_path / "compare_history.py"
        )

        eval_results_dst = staging_path / "eval_results"
        eval_results_dst.mkdir(parents=True, exist_ok=True)
        for name in ("runs.json", "history_summary.json"):
            src = args.eval_results / name
            if not src.exists():
                print(f"Missing tracked eval history file: {src}")
                return 1
            shutil.copy2(src, eval_results_dst / name)

        deploy_cmd = [
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
        print("Deploying historical dashboard to Outerbounds...")
        deploy_result = subprocess.run(deploy_cmd)
        return deploy_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
