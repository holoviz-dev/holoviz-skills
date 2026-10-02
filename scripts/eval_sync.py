#!/usr/bin/env python3
"""Sync eval run history and snapshots with the shared `eval-data` branch.

The branch holds JSON only (`runs.json`, `history_summary.json`, and
`runs/<run_id>/` snapshots); plot images stay in each run's CI artifact.

Default (pull) merges the branch's history into local `eval_results/` by key
without overwriting anything local.

`--upload` (CI only) merges local history onto the branch. Concurrent uploads
re-fetch, re-merge, and retry.

Usage:
  python eval_sync.py
  python eval_sync.py --upload --run-id ci-123-1-abcdef
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from aggregate_metrics import (
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
MAX_UPLOAD_ATTEMPTS = 3
README_TEXT = """\
# eval-data

Shared storage for HoloViz skills eval run history. Written by CI via
`scripts/eval_sync.py` after every successful eval run. Data branch — DO NOT
merge into `main`.

Layout mirrors `eval_results/` (JSON only; plot images live in each run's CI
artifact):

- `runs.json`, `history_summary.json` — compact history (see
  `scripts/aggregate_metrics.py`)
- `runs/<run_id>/` — immutable per-run snapshots (`evaluation_results.json`,
  `run_metadata.json`)
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
def _data_branch_worktree(repo_root: Path, remote: str, branch: str) -> Generator[Path]:
    """Check out `branch` into a fresh, temporary git worktree.

    Existence is checked before fetching, since fetching first can miss a
    branch a concurrent uploader creates in between. If that happens anyway,
    the caller's push is rejected and its retry loop picks it up next time.

    Parameters
    ----------
    repo_root : Path
        Local repository to create the worktree from.
    remote : str
        Git remote name, e.g. ``"origin"``.
    branch : str
        Branch to check out.

    Yields
    ------
    Path
        A detached checkout of `branch`, or a fresh orphan branch if it
        doesn't exist on `remote` yet. Removed again on exit.
    """
    _git(["worktree", "prune"], cwd=repo_root, check=False)
    tmp_dir = Path(tempfile.mkdtemp(prefix="eval-data-worktree-"))
    tmp_ref = f"{branch}-tmp-{uuid4().hex[:8]}"
    try:
        if _remote_branch_exists(repo_root, remote, branch):
            _git(
                ["fetch", remote, f"+{branch}:refs/remotes/{remote}/{branch}"],
                cwd=repo_root,
            )
            _git(["worktree", "add", "--detach", str(tmp_dir), f"{remote}/{branch}"], cwd=repo_root)
        else:
            _git(["worktree", "add", "--no-checkout", "--detach", str(tmp_dir)], cwd=repo_root)
            _git(["switch", "--orphan", tmp_ref], cwd=tmp_dir)
        yield tmp_dir
    finally:
        _git(["worktree", "remove", "--force", str(tmp_dir)], cwd=repo_root, check=False)
        _git(["branch", "-D", tmp_ref], cwd=repo_root, check=False)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _validate_branch_json(path: Path) -> bool:
    """Check that `path` is valid JSON if it exists.

    A missing file is fine (there's nothing to merge on top of yet), but a
    malformed one is not: `_load_json` treats unreadable files as missing, so
    merging on top of a corrupted history file would silently replace
    accumulated shared history with just the current run.
    """
    if not path.exists():
        return True
    try:
        json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        print(f"Error: {path.name} on the {DEFAULT_BRANCH} branch is not valid JSON ({e}).")
        print("Refusing to merge on top of it; fix or restore the file on the branch first.")
        return False
    return True


def _copy_run_snapshots(source_root: Path, dest_root: Path, run_ids: set[str] | None) -> int:
    """Copy `runs/<run_id>/` dirs from `source_root` to `dest_root`.

    Snapshots are immutable, so a destination dir that already exists is left
    as-is rather than overwritten.

    Parameters
    ----------
    source_root : Path
        Directory containing a `runs/` subdirectory to copy from.
    dest_root : Path
        Directory to copy `runs/<run_id>/` snapshots into.
    run_ids : set of str or None
        Only copy these run IDs, or all of them if None.

    Returns
    -------
    int
        Number of run snapshots copied.
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


def upload(branch: str, eval_results: Path, run_id: str | None = None) -> int:
    """Merge local run history and snapshots onto `branch` and push it.

    Registries are merged by key, snapshots are added if new. Concurrent
    uploads re-fetch, re-merge, and retry.

    Parameters
    ----------
    branch : str
        Shared branch to update.
    eval_results : Path
        Local `eval_results/` directory to read from.
    run_id : str, optional
        Upload only this run's records and snapshot. All if None.

    Returns
    -------
    int
        Process exit code: 0 on success, 1 on failure.
    """
    if not eval_results.exists():
        print(f"Error: eval results directory not found: {eval_results}")
        return 1

    run_records = _load_json(eval_results / RUNS_REGISTRY_FILE, {"runs": []}).get("runs", [])
    history_rows = _load_json(eval_results / HISTORY_SUMMARY_FILE, {"rows": []}).get("rows", [])

    run_ids: set[str] | None = None
    if run_id:
        run_ids = {run_id}
        run_records = [r for r in run_records if r.get("run_id") == run_id]
        history_rows = [r for r in history_rows if r.get("run_id") == run_id]
        if not run_records:
            print(f"Error: run_id '{run_id}' not found in local {RUNS_REGISTRY_FILE}")
            return 1

    if not run_records and not history_rows:
        print("Nothing to upload: no local run history found.")
        return 0

    for attempt in range(1, MAX_UPLOAD_ATTEMPTS + 1):
        with _data_branch_worktree(REPO_ROOT, DEFAULT_REMOTE, branch) as worktree_dir:
            branch_files = [worktree_dir / RUNS_REGISTRY_FILE, worktree_dir / HISTORY_SUMMARY_FILE]
            if not all(_validate_branch_json(path) for path in branch_files):
                return 1

            for run_record in run_records:
                _update_runs_registry(worktree_dir, run_record)
            if history_rows:
                _update_history_summary(worktree_dir, history_rows)

            snapshots_copied = _copy_run_snapshots(eval_results, worktree_dir, run_ids)
            _write_readme_if_missing(worktree_dir)

            _git(["add", "-A"], cwd=worktree_dir)
            if _git(["diff", "--cached", "--quiet"], cwd=worktree_dir, check=False).returncode == 0:
                print("Nothing new to upload (branch already up to date).")
                return 0

            message = f"chore: eval run {run_id}" if run_id else "chore: sync eval history"
            _git(["commit", "-m", message], cwd=worktree_dir)

            upload_result = _git(
                ["push", DEFAULT_REMOTE, f"HEAD:{branch}"], cwd=worktree_dir, check=False
            )
            if upload_result.returncode == 0:
                print(
                    f"Uploaded {len(run_records)} run record(s), {len(history_rows)} history "
                    f"row(s), {snapshots_copied} snapshot(s) to {DEFAULT_REMOTE}/{branch}."
                )
                return 0

            print(
                f"Upload attempt {attempt}/{MAX_UPLOAD_ATTEMPTS} rejected (concurrent "
                f"update?): {upload_result.stderr.strip()}"
            )
            time.sleep(attempt)

    print(
        f"Error: failed to upload to {DEFAULT_REMOTE}/{branch} after "
        f"{MAX_UPLOAD_ATTEMPTS} attempts."
    )
    return 1


def pull(branch: str, eval_results: Path) -> int:
    """Merge history and snapshots from `branch` into local `eval_results/`.

    Local-only runs and files are never overwritten or removed.

    Returns
    -------
    int
        Process exit code: 0 on success, 1 on failure.
    """
    if not _remote_branch_exists(REPO_ROOT, DEFAULT_REMOTE, branch):
        print(
            f"Error: branch '{branch}' not found on {DEFAULT_REMOTE}. "
            "It is created by the first successful CI eval run."
        )
        return 1

    with _data_branch_worktree(REPO_ROOT, DEFAULT_REMOTE, branch) as worktree_dir:
        branch_files = [worktree_dir / RUNS_REGISTRY_FILE, worktree_dir / HISTORY_SUMMARY_FILE]
        if not all(_validate_branch_json(path) for path in branch_files):
            return 1

        eval_results.mkdir(parents=True, exist_ok=True)
        run_records = _load_json(worktree_dir / RUNS_REGISTRY_FILE, {"runs": []}).get("runs", [])
        history_rows = _load_json(worktree_dir / HISTORY_SUMMARY_FILE, {"rows": []}).get("rows", [])
        for run_record in run_records:
            _update_runs_registry(eval_results, run_record)
        if history_rows:
            _update_history_summary(eval_results, history_rows)
        snapshots_copied = _copy_run_snapshots(worktree_dir, eval_results, run_ids=None)

    print(
        f"Merged {len(run_records)} run record(s), {len(history_rows)} history row(s), "
        f"{snapshots_copied} new snapshot(s) from {DEFAULT_REMOTE}/{branch} into {eval_results}."
    )
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print(
            "Error: --upload is restricted to CI. Run without it to refresh local "
            "eval_results/ from the shared branch."
        )
        return 1
    return upload(args.branch, args.eval_results, args.run_id)


def cmd_pull(args: argparse.Namespace) -> int:
    return pull(args.branch, args.eval_results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync eval run history and snapshots with the shared eval-data branch",
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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.upload:
        return cmd_upload(args)
    return cmd_pull(args)


if __name__ == "__main__":
    sys.exit(main())
