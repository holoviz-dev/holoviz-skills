#!/usr/bin/env python3
"""Run eval pipeline and publish the resulting run in one command."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _latest_run_id(eval_results_dir: Path) -> str | None:
    runs_path = eval_results_dir / "runs.json"
    if not runs_path.exists():
        return None
    try:
        payload = json.loads(runs_path.read_text())
    except Exception:
        return None
    runs = payload.get("runs", [])
    if not runs:
        return None
    return runs[0].get("run_id")


def main() -> int:
    repo_root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Run eval and publish results")
    parser.add_argument(
        "--eval-results",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Output directory for eval results",
    )
    parser.add_argument("--run-id", default=None, help="Run ID to use for this eval")
    parser.add_argument(
        "--run-trigger",
        choices=["manual", "ci_comment", "ci_dispatch", "ci_schedule"],
        default="manual",
        help="Run trigger metadata",
    )
    parser.add_argument(
        "--publish-target",
        default="local",
        help="Publish target label stored in run metadata",
    )
    parser.add_argument(
        "--provider",
        choices=["noop", "outerbounds"],
        default="noop",
        help="Publish provider",
    )
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Run eval only, skip publish step",
    )
    parser.add_argument(
        "--allow-publish-failure",
        action="store_true",
        help="Do not fail command if publish fails",
    )
    parser.add_argument(
        "--deploy-dashboard",
        action="store_true",
        default=os.getenv("EVAL_DEPLOY_DASHBOARD", "false").lower() == "true",
        help="Deploy the historical dashboard to Outerbounds after publishing",
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

    args, eval_args = parser.parse_known_args()

    eval_cmd = [
        sys.executable,
        str(Path(__file__).parent / "eval.py"),
        "--output",
        str(args.eval_results),
        "--run-trigger",
        args.run_trigger,
        "--publish-target",
        args.publish_target,
    ]
    if args.run_id:
        eval_cmd.extend(["--run-id", args.run_id])
    eval_cmd.extend(eval_args)

    print("Running eval pipeline...")
    eval_result = subprocess.run(eval_cmd)
    if eval_result.returncode != 0:
        return eval_result.returncode

    if args.skip_publish:
        print("Skipping publish step.")
        return 0

    run_id = args.run_id or _latest_run_id(args.eval_results)
    if not run_id:
        print("Could not determine run ID for publish step.")
        return 1

    publish_cmd = [
        sys.executable,
        str(Path(__file__).parent / "publish_results.py"),
        "--eval-results",
        str(args.eval_results),
        "--run-id",
        run_id,
        "--provider",
        args.provider,
    ]

    # Outerbounds is env-configured in CI. Keep command args explicit so logs
    # show resolved endpoint mode while avoiding embedding secrets in code.
    if args.provider == "outerbounds":
        ingest_url = os.getenv("OUTERBOUNDS_INGEST_URL")
        api_key = os.getenv("OUTERBOUNDS_API_KEY")
        project = os.getenv("OUTERBOUNDS_PROJECT")
        if ingest_url:
            publish_cmd.extend(["--outerbounds-url", ingest_url])
        if api_key:
            publish_cmd.extend(["--outerbounds-api-key", api_key])
        if project:
            publish_cmd.extend(["--outerbounds-project", project])

    if args.allow_publish_failure:
        publish_cmd.append("--allow-failure")

    print(f"Publishing run {run_id} via provider={args.provider}...")
    publish_result = subprocess.run(publish_cmd)
    if publish_result.returncode != 0:
        return publish_result.returncode

    if not args.deploy_dashboard:
        return 0

    config_token = args.outerbounds_config_token or os.getenv("OUTERBOUNDS_CONFIG_TOKEN")
    if config_token:
        configure_cmd = ["outerbounds", "configure", "--force", config_token]
        print("Configuring Outerbounds profile...")
        configure_result = subprocess.run(configure_cmd)
        if configure_result.returncode != 0:
            return configure_result.returncode

    deploy_cmd = [
        "outerbounds",
        "app",
        "deploy",
        "--config-file",
        str(args.outerbounds_deploy_config),
        "--package-src-path",
        str(repo_root),
        "--readiness-condition",
        "at_least_one_running",
    ]
    print("Deploying historical dashboard to Outerbounds...")
    deploy_result = subprocess.run(deploy_cmd)
    return deploy_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
