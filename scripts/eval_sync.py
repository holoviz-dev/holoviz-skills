#!/usr/bin/env python3
"""Sync eval run history, snapshots, and visuals with the shared `eval-data` branch.

Copies `runs.json`, `history_summary.json`, `runs/<run_id>/` snapshots, and
per-query `plot_output.html` / `screenshot.png` from the branch into local
`eval_results/`.

`--upload` (CI) merges those files onto the branch: JSON registries by key,
new run snapshots, latest-wins visuals. Concurrent uploads re-fetch, re-merge,
and retry.

Usage:
  python eval_sync.py
  python eval_sync.py --upload --run-id ci-123-1-abcdef
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from aggregate_metrics import (
    CONDITIONS,
    HISTORY_SUMMARY_FILE,
    RUNS_REGISTRY_FILE,
    _load_json,
    _update_history_summary,
    _update_runs_registry,
)

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_BRANCH = "eval-data"
DEFAULT_REMOTE = "origin"
VISUAL_FILENAMES = ("plot_output.html", "screenshot.png")
MAX_UPLOAD_ATTEMPTS = 3
README_TEXT = """\
# eval-data

Shared storage for HoloViz skills eval run history, snapshots, and per-query
visuals. Written by CI via `scripts/eval_sync.py` after every successful eval
run. Data branch — do not merge into `main`.

Layout mirrors `eval_results/`:

- `runs.json`, `history_summary.json` — compact history (see
  `scripts/aggregate_metrics.py`)
- `runs/<run_id>/` — immutable per-run snapshots (`evaluation_results.json`,
  `run_metadata.json`)
- `<model>/<condition>/<query_id>/plot_output.html`, `screenshot.png` —
  latest-wins visuals, overwritten by whichever run touched that query last
"""


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return result


def _remote_branch_exists(repo_root: Path, remote: str, branch: str) -> bool:
    result = _git(["ls-remote", "--heads", remote, branch], cwd=repo_root, check=False)
    return bool(result.stdout.strip())


@contextmanager
def _data_branch_worktree(repo_root: Path, remote: str, branch: str) -> Iterator[Path]:
    """Check out `branch` into a fresh, temporary git worktree.

    Yields a detached checkout of the remote branch, or a fresh orphan ref at
    a unique temporary name when the branch does not exist on `remote` yet.
    """
    _git(["worktree", "prune"], cwd=repo_root, check=False)
    _git(
        ["fetch", remote, f"+{branch}:refs/remotes/{remote}/{branch}"],
        cwd=repo_root,
        check=False,
    )
    tmp_dir = Path(tempfile.mkdtemp(prefix="eval-data-worktree-"))
    tmp_ref = f"{branch}-tmp-{uuid4().hex[:8]}"
    try:
        if _remote_branch_exists(repo_root, remote, branch):
            _git(["worktree", "add", "--detach", str(tmp_dir), f"{remote}/{branch}"], cwd=repo_root)
        else:
            _git(["worktree", "add", "--no-checkout", "--detach", str(tmp_dir)], cwd=repo_root)
            _git(["switch", "--orphan", tmp_ref], cwd=tmp_dir)
        yield tmp_dir
    finally:
        _git(["worktree", "remove", "--force", str(tmp_dir)], cwd=repo_root, check=False)
        _git(["branch", "-D", tmp_ref], cwd=repo_root, check=False)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _iter_query_dirs(eval_results_dir: Path) -> Iterator[tuple[str, str, Path]]:
    if not eval_results_dir.is_dir():
        return
    for model_dir in sorted(eval_results_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.name == "runs":
            continue
        for condition_dir in sorted(model_dir.iterdir()):
            if not condition_dir.is_dir() or condition_dir.name not in CONDITIONS:
                continue
            for query_dir in sorted(condition_dir.iterdir()):
                if query_dir.is_dir():
                    yield model_dir.name, condition_dir.name, query_dir


def _copy_visuals(source_root: Path, dest_root: Path) -> int:
    """Copy plot_output.html/screenshot.png for every query dir, latest-wins.

    The destination pair is cleared per query dir so both filenames stay in
    sync with the source run.
    """
    copied = 0
    for model, condition, query_dir in _iter_query_dirs(source_root):
        dest_dir = dest_root / model / condition / query_dir.name
        for filename in VISUAL_FILENAMES:
            (dest_dir / filename).unlink(missing_ok=True)
        for filename in VISUAL_FILENAMES:
            src = query_dir / filename
            if not src.exists():
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir / filename)
            copied += 1
    return copied


def _copy_run_snapshots(source_root: Path, dest_root: Path, run_ids: set[str] | None) -> int:
    """Copy runs/<run_id>/ dirs not already present at the destination.

    Snapshots are immutable, so an existing destination dir is kept.
    """
    source_runs_dir = source_root / "runs"
    if not source_runs_dir.is_dir():
        return 0
    dest_runs_dir = dest_root / "runs"
    copied = 0
    for run_dir in sorted(source_runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        if run_ids is not None and run_dir.name not in run_ids:
            continue
        dest_dir = dest_runs_dir / run_dir.name
        if dest_dir.exists():
            continue
        shutil.copytree(run_dir, dest_dir)
        copied += 1
    return copied


def _write_readme_if_missing(worktree_dir: Path) -> None:
    readme = worktree_dir / "README.md"
    if not readme.exists():
        readme.write_text(README_TEXT)


def cmd_upload(args: argparse.Namespace) -> int:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print(
            "Error: --upload is restricted to CI. Run without it to refresh local "
            "eval_results/ from the shared branch."
        )
        return 1

    eval_results = args.eval_results
    if not eval_results.exists():
        print(f"Error: eval results directory not found: {eval_results}")
        return 1

    run_records = _load_json(eval_results / RUNS_REGISTRY_FILE, {"runs": []}).get("runs", [])
    history_rows = _load_json(eval_results / HISTORY_SUMMARY_FILE, {"rows": []}).get("rows", [])

    run_ids: set[str] | None = None
    if args.run_id:
        run_ids = {args.run_id}
        run_records = [r for r in run_records if r.get("run_id") == args.run_id]
        history_rows = [r for r in history_rows if r.get("run_id") == args.run_id]
        if not run_records:
            print(f"Error: run_id '{args.run_id}' not found in local {RUNS_REGISTRY_FILE}")
            return 1

    if not run_records and not history_rows and args.skip_visuals:
        print("Nothing to upload: no local run history found.")
        return 0

    for attempt in range(1, MAX_UPLOAD_ATTEMPTS + 1):
        with _data_branch_worktree(REPO_ROOT, DEFAULT_REMOTE, args.branch) as worktree_dir:
            for run_record in run_records:
                _update_runs_registry(worktree_dir, run_record)
            if history_rows:
                _update_history_summary(worktree_dir, history_rows)

            snapshots_copied = _copy_run_snapshots(eval_results, worktree_dir, run_ids)
            visuals_copied = 0
            if not args.skip_visuals:
                visuals_copied = _copy_visuals(eval_results, worktree_dir)
            _write_readme_if_missing(worktree_dir)

            _git(["add", "-A"], cwd=worktree_dir)
            if _git(["diff", "--cached", "--quiet"], cwd=worktree_dir, check=False).returncode == 0:
                print("Nothing new to upload (branch already up to date).")
                return 0

            message = (
                f"chore: eval run {args.run_id}" if args.run_id else "chore: sync eval history"
            )
            _git(["commit", "-m", message], cwd=worktree_dir)

            upload_result = _git(
                ["push", DEFAULT_REMOTE, f"HEAD:{args.branch}"], cwd=worktree_dir, check=False
            )
            if upload_result.returncode == 0:
                print(
                    f"Uploaded {len(run_records)} run record(s), {len(history_rows)} history "
                    f"row(s), {snapshots_copied} snapshot(s), {visuals_copied} visual(s) to "
                    f"{DEFAULT_REMOTE}/{args.branch}."
                )
                return 0

            print(
                f"Upload attempt {attempt}/{MAX_UPLOAD_ATTEMPTS} rejected (concurrent "
                f"update?): {upload_result.stderr.strip()}"
            )
            time.sleep(attempt)

    print(
        f"Error: failed to upload to {DEFAULT_REMOTE}/{args.branch} after "
        f"{MAX_UPLOAD_ATTEMPTS} attempts."
    )
    return 1


def cmd_pull(args: argparse.Namespace) -> int:
    if not _remote_branch_exists(REPO_ROOT, DEFAULT_REMOTE, args.branch):
        print(
            f"Error: branch '{args.branch}' not found on {DEFAULT_REMOTE}. "
            "It is created by the first successful CI eval run."
        )
        return 1

    with _data_branch_worktree(REPO_ROOT, DEFAULT_REMOTE, args.branch) as worktree_dir:
        args.eval_results.mkdir(parents=True, exist_ok=True)

        for name in (RUNS_REGISTRY_FILE, HISTORY_SUMMARY_FILE):
            src = worktree_dir / name
            if src.exists():
                shutil.copy2(src, args.eval_results / name)

        snapshots_copied = _copy_run_snapshots(worktree_dir, args.eval_results, run_ids=None)
        visuals_copied = 0
        if not args.skip_visuals:
            visuals_copied = _copy_visuals(worktree_dir, args.eval_results)

    print(
        f"Pulled history, {snapshots_copied} snapshot(s), {visuals_copied} visual(s) from "
        f"{DEFAULT_REMOTE}/{args.branch} into {args.eval_results}."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync eval run history, snapshots, and visuals with the shared "
        "eval-data branch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="CI only: merge run history onto the shared branch instead of pulling",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"Shared eval-data branch name (default: {DEFAULT_BRANCH})",
    )
    parser.add_argument(
        "--eval-results",
        type=Path,
        default=REPO_ROOT / "eval_results",
        help="Local eval results directory (default: ../eval_results)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="With --upload, merge only this run's history rows and runs/<run_id>/ snapshot",
    )
    parser.add_argument(
        "--skip-visuals",
        action="store_true",
        help="Don't sync plot_output.html/screenshot.png visuals",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.upload:
        return cmd_upload(args)
    return cmd_pull(args)


if __name__ == "__main__":
    sys.exit(main())
