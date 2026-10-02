"""Tests for the cleanup eval's grader, run without Kilo.

Each fixture should fail every check as committed and pass every check once
cleaned up the way the post describes, so a check that passes on the sloppy
change, or fails on the clean one, is a bug in the grader.
"""

import shutil

import eval_cleanup
import pytest
from eval import KiloResponse
from eval_cleanup import FIXTURES, FIXTURES_DIR, grade, read_package, revised_files

CLEAN = {
    "cleanup_review": {
        "pkg/query.py": """\
from pkg.sources.duckdb import missing_table_name
from pkg.utils import with_timeout


class QueryRunner:
    def __init__(self, source):
        self.source = source

    async def run(self, sql: str):
        try:
            return await with_timeout(self.source.execute(sql), timeout_seconds=60)
        except RuntimeError as e:
            table = missing_table_name(e)
            if table is None:
                raise
            raise ValueError(f"Unknown table {table!r}") from e
""",
        "pkg/utils.py": """\
import asyncio


async def with_timeout(coro, timeout_seconds: float = 10):
    return await asyncio.wait_for(coro, timeout_seconds)


def chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
""",
    },
    "cleanup_holdout": {
        "pkg/loader.py": """\
import urllib.request

from pkg.sources.nexrad import scan_time
from pkg.utils import retry


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


class ScanLoader:
    def __init__(self, source):
        self.source = source

    def load(self, filename: str) -> dict:
        data = retry(lambda: fetch(self.source.url(filename)))
        return {"time": scan_time(filename), "data": data}
""",
        "pkg/utils.py": """\
import time


def retry(fn, attempts: int = 3, delay_seconds: float = 1.0):
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(delay_seconds)


def chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
""",
    },
}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_committed_fixture_fails_every_check(name):
    results = grade(FIXTURES[name], read_package(FIXTURES_DIR / name))
    assert not any(results.values()), results


@pytest.mark.parametrize("name", list(FIXTURES))
def test_cleaned_fixture_passes_every_check(name):
    files = read_package(FIXTURES_DIR / name) | CLEAN[name]
    results = grade(FIXTURES[name], files)
    assert all(results.values()), results


def test_reusing_a_helper_without_fixing_it_still_hides_the_failure():
    files = read_package(FIXTURES_DIR / "cleanup_review")
    files["pkg/query.py"] = CLEAN["cleanup_review"]["pkg/query.py"]
    results = grade(FIXTURES["cleanup_review"], files)
    assert results["reuses with_timeout"]
    assert not results["no guard that hides a failure"]


def test_revised_files_keeps_only_package_sources():
    response = KiloResponse(
        "```python\n# file: pkg/utils.py\nX = 1\n```\n"
        "```python\n# file: ../../etc/evil.py\nX = 2\n```\n"
        "```python\n# file: notes.md\nhi\n```\n"
        "```python\nY = 3\n```\n",
        "prompt",
        0.0,
        model="default",
    )
    assert revised_files(response, "pkg/query.py") == {
        "pkg/utils.py": "X = 1\n",
        "pkg/query.py": "Y = 3\n",
    }


def test_workspace_holds_no_answer_key():
    workspace = eval_cleanup.make_workspace("cleanup_review", skills=False)
    try:
        assert sorted(p.name for p in workspace.iterdir()) == ["pkg"]
    finally:
        shutil.rmtree(workspace)
