#!/usr/bin/env python3
"""Publish eval run artifacts to an external sink.

Default provider is `noop`, which writes a local publish manifest only.
Use `outerbounds` provider to POST payload to an external endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib import request

RUNS_REGISTRY_FILE = "runs.json"
HISTORY_SUMMARY_FILE = "history_summary.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2) + "\n")


def _latest_run_id(eval_results_dir: Path) -> str | None:
    registry = _load_json(eval_results_dir / RUNS_REGISTRY_FILE, {"runs": []})
    runs = registry.get("runs", [])
    if not runs:
        return None
    return runs[0].get("run_id")


def _load_run_record(eval_results_dir: Path, run_id: str) -> dict | None:
    registry_path = eval_results_dir / RUNS_REGISTRY_FILE
    registry = _load_json(registry_path, {"runs": []})
    for run in registry.get("runs", []):
        if run.get("run_id") == run_id:
            return run
    return None


def _load_history_rows(eval_results_dir: Path, run_id: str) -> list[dict]:
    history = _load_json(eval_results_dir / HISTORY_SUMMARY_FILE, {"rows": []})
    rows = history.get("rows", [])
    return [row for row in rows if row.get("run_id") == run_id]


def _build_payload(eval_results_dir: Path, run_id: str) -> dict:
    run = _load_run_record(eval_results_dir, run_id)
    if run is None:
        raise ValueError(f"Run ID not found in runs.json: {run_id}")

    return {
        "run": run,
        "history_rows": _load_history_rows(eval_results_dir, run_id),
        "published_at": _utc_now_iso(),
    }


def _publish_noop(eval_results_dir: Path, run_id: str, payload: dict) -> dict:
    out_dir = eval_results_dir / "published"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / f"{run_id}.json"
    _save_json(manifest, payload)
    return {
        "provider": "noop",
        "status": "ok",
        "manifest": str(manifest),
    }


def _publish_outerbounds(
    payload: dict,
    ingest_url: str,
    api_key: str | None,
    project: str | None,
) -> dict:
    wire_payload = {
        "project": project,
        "payload": payload,
    }
    body = json.dumps(wire_payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = request.Request(
        url=ingest_url,
        data=body,
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8") if resp.length != 0 else "{}"
        response_payload = json.loads(raw) if raw else {}

    return {
        "provider": "outerbounds",
        "status": "ok",
        "ingest_url": ingest_url,
        "response": response_payload,
    }


def _update_publish_status(eval_results_dir: Path, run_id: str, publish_result: dict):
    registry_path = eval_results_dir / RUNS_REGISTRY_FILE
    registry = _load_json(registry_path, {"schema_version": 1, "runs": []})

    updated = False
    for run in registry.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        run["published"] = {
            "at": _utc_now_iso(),
            **publish_result,
        }
        updated = True
        break

    if updated:
        _save_json(registry_path, registry)

    snapshot_meta = eval_results_dir / "runs" / run_id / "run_metadata.json"
    if snapshot_meta.exists():
        payload = _load_json(snapshot_meta, {})
        payload["published"] = {
            "at": _utc_now_iso(),
            **publish_result,
        }
        _save_json(snapshot_meta, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish eval run results")
    parser.add_argument(
        "--eval-results",
        type=Path,
        default=Path(__file__).parent.parent / "eval_results",
        help="Evaluation results directory",
    )
    parser.add_argument("--run-id", default=None, help="Run ID to publish (default: latest)")
    parser.add_argument(
        "--provider",
        choices=["noop", "outerbounds"],
        default="noop",
        help="Publish provider",
    )
    parser.add_argument(
        "--outerbounds-url",
        default=None,
        help="Outerbounds ingest URL (or OUTERBOUNDS_INGEST_URL env)",
    )
    parser.add_argument(
        "--outerbounds-api-key",
        default=None,
        help="Outerbounds API key (or OUTERBOUNDS_API_KEY env)",
    )
    parser.add_argument(
        "--outerbounds-project",
        default=None,
        help="Outerbounds project label (or OUTERBOUNDS_PROJECT env)",
    )
    parser.add_argument(
        "--allow-failure",
        action="store_true",
        help="Exit successfully even if publish fails",
    )

    args = parser.parse_args()

    run_id = args.run_id or _latest_run_id(args.eval_results)
    if not run_id:
        print("No run ID provided and no runs available to publish.")
        return 1

    try:
        payload = _build_payload(args.eval_results, run_id)

        if args.provider == "noop":
            result = _publish_noop(args.eval_results, run_id, payload)
        else:
            ingest_url = args.outerbounds_url or os.getenv("OUTERBOUNDS_INGEST_URL", "")
            api_key = args.outerbounds_api_key or os.getenv("OUTERBOUNDS_API_KEY")
            project = args.outerbounds_project or os.getenv("OUTERBOUNDS_PROJECT")
            if not ingest_url:
                raise ValueError("outerbounds provider requires --outerbounds-url")
            result = _publish_outerbounds(
                payload=payload,
                ingest_url=ingest_url,
                api_key=api_key,
                project=project,
            )

        _update_publish_status(args.eval_results, run_id, result)
        print(f"Publish succeeded for run {run_id} via {result['provider']}")
        return 0
    except Exception as exc:
        print(f"Publish failed for run {run_id}: {exc}")
        if args.allow_failure:
            return 0
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
