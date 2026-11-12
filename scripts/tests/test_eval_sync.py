"""Tests for eval_sync.py against a local bare repo standing in for `origin`."""

import argparse
import json
import subprocess
from pathlib import Path

import aggregate_metrics
import eval_sync
import pytest


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")
    monkeypatch.setattr(eval_sync.time, "sleep", lambda _: None)


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    git("init", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    return bare


@pytest.fixture
def repo(tmp_path, remote, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    git("init", "-b", "main", cwd=work)
    (work / "README").write_text("x")
    git("add", "-A", cwd=work)
    git("commit", "-m", "init", cwd=work)
    git("remote", "add", "origin", str(remote), cwd=work)
    git("push", "origin", "main", cwd=work)
    monkeypatch.setattr(eval_sync, "REPO_ROOT", work)
    return work


def make_record(run_id: str) -> dict:
    """Return a run record with every key the producer always emits."""
    return {
        "run_id": run_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "success",
        "results_relpath": f"runs/{run_id}",
        "total_queries": 1,
        "models": ["m"],
        "run_trigger": "manual",
        "pr_number": None,
        "resolved_models": {"m": ["m"]},
        "anonymous_models": [],
        "publish_target": "local",
        "models_requested": ["m"],
        "query_ids": ["q"],
        "skip_generation": False,
        "skip_execution": False,
        "skip_aggregation": False,
        "git_commit": "abc1234",
        "git_branch": "main",
        "python_version": "3.12.0",
        "platform": "test",
    }


def make_row(run_id: str) -> dict:
    """Return a history row with every key the producer always emits."""
    return {
        "run_id": run_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "run_trigger": "manual",
        "pr_number": None,
        "query_id": "q",
        "model": "m",
        "condition": "with_skills",
        "tokens_output": 10,
        "tokens_input": 20,
        "tokens_cached": 0,
        "execution_time": 1.0,
        "cost": 0.01,
        "execution_success": True,
        "has_code": True,
        "timed_out": False,
        "resolved_models": ["m"],
        "anonymous": False,
    }


def make_results(root: Path, run_id: str) -> Path:
    """Write a minimal local eval_results dir containing one full-schema run."""
    results = root / f"results-{run_id}"
    snapshot = results / "runs" / run_id
    snapshot.mkdir(parents=True)
    record = make_record(run_id)
    (snapshot / "run_metadata.json").write_text(json.dumps(record))
    (results / "runs.json").write_text(json.dumps({"schema_version": 1, "runs": [record]}))
    (results / "history_summary.json").write_text(
        json.dumps({"schema_version": 1, "rows": [make_row(run_id)]})
    )
    return results


def push_orphan_branch(repo: Path, tmp_path: Path, files: dict[str, str], name: str) -> None:
    """Create an orphan `eval-data` branch containing exactly `files` and push it."""
    worktree = tmp_path / name
    git("worktree", "add", "--no-checkout", "--detach", str(worktree), cwd=repo)
    git("switch", "--orphan", "eval-data", cwd=worktree)
    for relpath, text in files.items():
        path = worktree / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git("add", "-A", cwd=worktree)
    git("commit", "-m", "seed eval-data", cwd=worktree)
    git("push", "origin", "HEAD:eval-data", cwd=worktree)
    git("worktree", "remove", "--force", str(worktree), cwd=repo)


def commit_to_branch(remote: Path, tmp_path: Path, files: dict[str, str], name: str) -> str:
    """Commit `files` onto `eval-data` from a clone and return the new tip SHA."""
    clone = tmp_path / name
    git("clone", "-b", "eval-data", str(remote), str(clone), cwd=tmp_path)
    for relpath, text in files.items():
        path = clone / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git("add", "-A", cwd=clone)
    git("commit", "-m", "seed", cwd=clone)
    git("push", "origin", "eval-data", cwd=clone)
    return git("rev-parse", "eval-data", cwd=remote).stdout.strip()


def branch_json(remote: Path, tmp_path: Path, name: str) -> dict:
    out = git("show", f"eval-data:{name}", cwd=remote).stdout
    return json.loads(out)


def run_ids(payload: dict, key: str) -> set[str]:
    return {item["run_id"] for item in payload[key]}


def test_upload_creates_orphan_branch(repo, remote, tmp_path):
    results = make_results(tmp_path, "run-a")
    assert eval_sync.upload("eval-data", results, "run-a") == 0

    files = git("ls-tree", "-r", "--name-only", "eval-data", cwd=remote).stdout.split()
    assert sorted(files) == [
        "README.md",
        "history_summary.json",
        "runs.json",
        "runs/run-a/run_metadata.json",
    ]


def test_upload_merges_sequential_runs(repo, remote, tmp_path):
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 0
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-b"), "run-b") == 0

    assert run_ids(branch_json(remote, tmp_path, "runs.json"), "runs") == {"run-a", "run-b"}
    assert run_ids(branch_json(remote, tmp_path, "history_summary.json"), "rows") == {
        "run-a",
        "run-b",
    }


def test_upload_is_idempotent(repo, remote, tmp_path, capsys):
    results = make_results(tmp_path, "run-a")
    assert eval_sync.upload("eval-data", results, "run-a") == 0
    assert eval_sync.upload("eval-data", results, "run-a") == 0
    assert "up to date" in capsys.readouterr().out


def test_upload_unknown_run_id_fails(repo, tmp_path):
    results = make_results(tmp_path, "run-a")
    assert eval_sync.upload("eval-data", results, "nope") == 1


def test_pull_keeps_local_only_runs(repo, remote, tmp_path):
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 0

    local = make_results(tmp_path, "local-only")
    assert eval_sync.pull("eval-data", local) == 0

    assert run_ids(json.loads((local / "runs.json").read_text()), "runs") == {
        "run-a",
        "local-only",
    }
    assert run_ids(json.loads((local / "history_summary.json").read_text()), "rows") == {
        "run-a",
        "local-only",
    }
    assert (local / "runs" / "local-only" / "run_metadata.json").exists()
    assert (local / "runs" / "run-a" / "run_metadata.json").exists()


def test_pull_does_not_overwrite_existing_snapshot(repo, remote, tmp_path):
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 0
    local = make_results(tmp_path, "run-a-local")
    snapshot = local / "runs" / "run-a"
    snapshot.mkdir()
    (snapshot / "run_metadata.json").write_text("local")

    assert eval_sync.pull("eval-data", local) == 0
    assert (snapshot / "run_metadata.json").read_text() == "local"


def test_pull_missing_branch_fails(repo, tmp_path, capsys):
    assert eval_sync.pull("eval-data", tmp_path / "out") == 1
    assert "not found on origin" in capsys.readouterr().out


def test_cmd_upload_requires_ci(repo, remote, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    args = argparse.Namespace(
        branch="eval-data", eval_results=make_results(tmp_path, "run-a"), run_id="run-a"
    )
    assert eval_sync.cmd_upload(args) == 1
    assert "restricted to CI" in capsys.readouterr().out
    assert git("ls-remote", "--heads", str(remote), "eval-data", cwd=tmp_path).stdout == ""

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert eval_sync.cmd_upload(args) == 0


def test_upload_retries_after_concurrent_push(repo, remote, tmp_path, monkeypatch):
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 0

    other = tmp_path / "other"
    git("clone", "-b", "eval-data", str(remote), str(other), cwd=tmp_path)
    competing = other / "runs" / "run-other" / "run_metadata.json"
    competing.parent.mkdir(parents=True)
    competing.write_text("competing commit")
    git("add", "-A", cwd=other)
    git("commit", "-m", "competing", cwd=other)

    real_git = eval_sync._git
    raced = []

    def racing_git(args, cwd, check=True):
        if args[0] == "push" and not raced:
            raced.append(True)
            git("push", "origin", "HEAD:eval-data", cwd=other)
        return real_git(args, cwd, check)

    monkeypatch.setattr(eval_sync, "_git", racing_git)
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-b"), "run-b") == 0

    assert raced
    assert run_ids(branch_json(remote, tmp_path, "runs.json"), "runs") == {"run-a", "run-b"}
    assert (
        "runs/run-other/run_metadata.json"
        in git("ls-tree", "-r", "--name-only", "eval-data", cwd=remote).stdout
    )


def test_upload_gives_up_after_max_attempts(repo, remote, tmp_path, monkeypatch, capsys):
    real_git = eval_sync._git
    pushes = []

    def failing_git(args, cwd, check=True):
        if args[0] == "push":
            pushes.append(1)
            return subprocess.CompletedProcess(args, 1, "", "rejected")
        return real_git(args, cwd, check)

    monkeypatch.setattr(eval_sync, "_git", failing_git)
    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 1
    assert len(pushes) == eval_sync.MAX_UPLOAD_ATTEMPTS
    assert "failed to upload" in capsys.readouterr().out


def test_upload_replaces_existing_readme(repo, remote, tmp_path):
    """A project README on the branch is replaced by the canonical eval-data README."""
    push_orphan_branch(repo, tmp_path, {"README.md": "# project readme\n"}, "seed-readme")

    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 0
    assert git("show", "eval-data:README.md", cwd=remote).stdout == eval_sync.README_TEXT


def test_upload_rejects_disallowed_branch_paths(repo, remote, tmp_path, capsys):
    """An upload against a branch with stray files fails without moving the branch."""
    push_orphan_branch(repo, tmp_path, {"visuals.json": "{}"}, "seed-bad")
    tip = git("rev-parse", "eval-data", cwd=remote).stdout.strip()

    assert eval_sync.upload("eval-data", make_results(tmp_path, "run-a"), "run-a") == 1
    assert "outside the allowed layout" in capsys.readouterr().out
    assert "visuals.json" in git("ls-tree", "-r", "--name-only", "eval-data", cwd=remote).stdout
    assert git("rev-parse", "eval-data", cwd=remote).stdout.strip() == tip


def test_upload_rejects_record_missing_keys(repo, remote, tmp_path, capsys):
    """A run record missing a producer key is rejected before anything is pushed."""
    results = make_results(tmp_path, "run-a")
    record = json.loads((results / "runs.json").read_text())["runs"][0]
    del record["resolved_models"]
    (results / "runs.json").write_text(json.dumps({"schema_version": 1, "runs": [record]}))

    assert eval_sync.upload("eval-data", results, "run-a") == 1
    assert "missing required keys" in capsys.readouterr().out
    assert git("ls-remote", "--heads", str(remote), "eval-data", cwd=tmp_path).stdout == ""


def test_upload_rejects_history_row_missing_keys(repo, remote, tmp_path, capsys):
    """A history row missing a producer key is rejected before anything is pushed."""
    results = make_results(tmp_path, "run-a")
    row = json.loads((results / "history_summary.json").read_text())["rows"][0]
    del row["anonymous"]
    (results / "history_summary.json").write_text(json.dumps({"schema_version": 1, "rows": [row]}))

    assert eval_sync.upload("eval-data", results, "run-a") == 1
    assert "anonymous" in capsys.readouterr().out
    assert git("ls-remote", "--heads", str(remote), "eval-data", cwd=tmp_path).stdout == ""


def test_producer_records_pass_the_check(tmp_path):
    """Records from aggregate_metrics satisfy the required keys, guarding schema drift."""
    summary = {"queries": {"q": {"models": {"m": {"with_skills": {"tokens_output": 1}}}}}}
    created_at = "2026-01-01T00:00:00+00:00"
    record = aggregate_metrics._build_run_record(
        run_id="run-a",
        created_at=created_at,
        summary=summary,
        run_metadata={},
        snapshot_dir=tmp_path / "runs" / "run-a",
    )
    rows = aggregate_metrics._flatten_history_rows(summary, "run-a", created_at)

    assert rows
    assert eval_sync._record_errors([record], rows) == []


def test_pull_empty_branch_succeeds(repo, remote, tmp_path, capsys):
    """Pulling a branch with empty registries reports zero runs and exits cleanly."""
    push_orphan_branch(
        repo,
        tmp_path,
        {
            "runs.json": json.dumps({"schema_version": 1, "run_count": 0, "runs": []}),
            "history_summary.json": json.dumps({"schema_version": 1, "row_count": 0, "rows": []}),
        },
        "seed-empty",
    )

    assert eval_sync.pull("eval-data", tmp_path / "out") == 0
    assert "Merged 0 run record(s)" in capsys.readouterr().out
