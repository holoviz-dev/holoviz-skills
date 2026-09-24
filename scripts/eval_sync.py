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
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator, Iterator
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
VISUALS_MANIFEST_FILE = "visuals.json"
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
- `visuals.json` — manifest of every query's current visual filenames (an
  empty list marks a query whose latest run produced no visual, so pulls can
  remove a stale local copy that the branch no longer has)
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


def _load_visuals_manifest(root: Path) -> dict[str, list[str]]:
    payload = _load_json(root / VISUALS_MANIFEST_FILE, {"schema_version": 1, "visuals": {}})
    return payload.get("visuals", {})


def _write_visuals_manifest(root: Path, visuals: dict[str, list[str]]) -> None:
    payload = {"schema_version": 1, "visuals": dict(sorted(visuals.items()))}
    (root / VISUALS_MANIFEST_FILE).write_text(json.dumps(payload, indent=2) + "\n")


def _reconcile_visual_files(
    dest_root: Path, key: str, files: list[str], source_dir: Path | None
) -> int:
    """Make `dest_root/key` hold exactly `files`, copied from `source_dir`.

    Both possible filenames are removed from the destination first, so an
    empty `files` list (a query whose latest run produced no visual) clears a
    stale copy just as reliably as a non-empty list replaces one.

    Parameters
    ----------
    dest_root : Path
        Root directory to update.
    key : str
        Query key, ``"{model}/{condition}/{query_id}"``.
    files : list of str
        Filenames that should exist at `dest_root/key` afterwards.
    source_dir : Path or None
        Directory to copy `files` from. None if there's nothing to copy from.

    Returns
    -------
    int
        Number of files copied.
    """
    dest_dir = dest_root / key
    for filename in VISUAL_FILENAMES:
        (dest_dir / filename).unlink(missing_ok=True)
    copied = 0
    for filename in files:
        if source_dir is None:
            continue
        src = source_dir / filename
        if not src.exists():
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / filename)
        copied += 1
    return copied


def _push_visuals(source_root: Path, dest_root: Path) -> int:
    """Upload local visuals to `dest_root`, latest-wins, updating its manifest.

    Only touches query dirs present in `source_root` (the local run that just
    finished); the manifest's other entries are left as they were.

    Parameters
    ----------
    source_root : Path
        Local `eval_results/` to read visuals from.
    dest_root : Path
        Branch worktree to update.

    Returns
    -------
    int
        Number of files copied.
    """
    manifest = _load_visuals_manifest(dest_root)
    copied = 0
    for model, condition, query_dir in _iter_query_dirs(source_root):
        key = f"{model}/{condition}/{query_dir.name}"
        present = [name for name in VISUAL_FILENAMES if (query_dir / name).exists()]
        copied += _reconcile_visual_files(dest_root, key, present, query_dir)
        manifest[key] = present
    _write_visuals_manifest(dest_root, manifest)
    return copied


def _pull_visuals(source_root: Path, dest_root: Path) -> int:
    """Mirror `source_root`'s visuals into `dest_root`, including deletions.

    Reconciles every key the manifest has ever recorded rather than just
    query dirs that still exist in `source_root`, since a directory with no
    tracked files doesn't exist in a git checkout and so can't be iterated —
    this is what lets a query whose latest run produced no visual have its
    local copy removed too.

    Parameters
    ----------
    source_root : Path
        Branch worktree to read visuals from.
    dest_root : Path
        Local `eval_results/` to update.

    Returns
    -------
    int
        Number of files copied.
    """
    manifest = _load_visuals_manifest(source_root)
    copied = 0
    for key, files in manifest.items():
        copied += _reconcile_visual_files(dest_root, key, files, source_root / key)
    _write_visuals_manifest(dest_root, manifest)
    return copied


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
            manifest_file = None if args.skip_visuals else worktree_dir / VISUALS_MANIFEST_FILE
            branch_files = [worktree_dir / RUNS_REGISTRY_FILE, worktree_dir / HISTORY_SUMMARY_FILE]
            if manifest_file is not None:
                branch_files.append(manifest_file)
            if not all(_validate_branch_json(path) for path in branch_files):
                return 1

            for run_record in run_records:
                _update_runs_registry(worktree_dir, run_record)
            if history_rows:
                _update_history_summary(worktree_dir, history_rows)

            snapshots_copied = _copy_run_snapshots(eval_results, worktree_dir, run_ids)
            visuals_copied = 0
            if not args.skip_visuals:
                visuals_copied = _push_visuals(eval_results, worktree_dir)
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
    """Copy eval history and visuals from the shared branch into local `eval_results/`."""
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
            if not _validate_branch_json(worktree_dir / VISUALS_MANIFEST_FILE):
                return 1
            visuals_copied = _pull_visuals(worktree_dir, args.eval_results)

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
