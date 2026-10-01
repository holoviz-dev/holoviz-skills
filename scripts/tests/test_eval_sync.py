"""Tests for eval_sync.py against a local bare repo standing in for `origin`."""

import argparse
import json
import subprocess
from pathlib import Path

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


def make_results(root: Path, run_id: str) -> Path:
    """Write a minimal local eval_results dir containing one run."""
    results = root / f"results-{run_id}"
    snapshot = results / "runs" / run_id
    snapshot.mkdir(parents=True)
    (snapshot / "run_metadata.json").write_text(json.dumps({"run_id": run_id}))
    record = {"run_id": run_id, "created_at": f"2026-01-01T00:00:0{len(run_id) % 10}+00:00"}
    (results / "runs.json").write_text(json.dumps({"runs": [record]}))
    row = {
        "run_id": run_id,
        "created_at": record["created_at"],
        "query_id": "q",
        "model": "m",
        "condition": "with_skills",
    }
    (results / "history_summary.json").write_text(json.dumps({"rows": [row]}))
    return results


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
    (other / "other.txt").write_text("competing commit")
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
    assert "other.txt" in git("ls-tree", "-r", "--name-only", "eval-data", cwd=remote).stdout


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
