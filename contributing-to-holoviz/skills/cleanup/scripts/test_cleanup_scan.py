"""Tests for cleanup_scan.py.

The first two cases are the WRONG/CORRECT pair in the cleanup skill's Errors and
Guards section, so a rule that misses its own documented WRONG example, or fires
on the CORRECT one, is a bug in the rule.

Run from this directory: `python test_cleanup_scan.py`, or `pytest test_cleanup_scan.py`.
"""

from __future__ import annotations

import sys

from cleanup_scan import scan_sources

SKILL_WRONG = '''
def missing_table(error: Exception) -> str | None:
    """Return the name of the missing table from an error."""
    import re

    try:
        match = re.search(r"Table with name\\s(\\S+)", str(error))
        return match.group(1) if match else None
    except Exception:
        return None
'''

SKILL_CORRECT = """
import re

def missing_table(error: Exception) -> str | None:
    match = re.search(r"Table with name\\s(\\S+)", str(error))
    return match.group(1) if match else None
"""


def rules(source: str) -> set[str]:
    return {h.rule for h in scan_sources({"mod.py": source})}


def test_skill_wrong_example():
    expected = {"restating-docstring", "deferred-stdlib-import", "blind-except", "silent-except"}
    assert rules(SKILL_WRONG) == expected


def test_skill_correct_example():
    assert rules(SKILL_CORRECT) == set()


def test_single_use_constant_only_where_the_parameter_names_it():
    assert rules("QUERY_TIMEOUT = 60\ndef run(timeout=QUERY_TIMEOUT): ...\n") == {
        "single-use-constant"
    }
    assert rules("LIMIT = 60\ndef run(n): return n > LIMIT\n") == set()
    assert rules("T = 60\ndef a(t=T): ...\ndef b(t=T): ...\n") == set()
    assert rules("import re\nPAT = re.compile('x')\ndef f(s): return PAT.match(s)\n") == set()


def test_single_use_counts_reads_across_files():
    sources = {
        "a.py": "TIMEOUT = 60\n",
        "b.py": "from a import TIMEOUT\ndef run(t=TIMEOUT): ...\n",
    }
    assert [h.rule for h in scan_sources(sources)] == ["single-use-constant"]


def test_file_order():
    assert rules("class A: ...\ndef f(): ...\n") == {"file-order"}
    assert rules("def f(): ...\nX = 1\n") == {"file-order"}
    # A record type that signatures refer to, and a constant built from a
    # function above it, both belong where they are.
    record = "from dataclasses import dataclass\n@dataclass\nclass A: ...\ndef f(): ...\n"
    assert rules(record) == set()
    assert rules("def f(): ...\nHANDLERS = {'f': f}\n") == set()


def test_silent_except_sees_none_defaults():
    source = (
        "async def with_timeout(coro, timeout_seconds=10, default_value=None):\n"
        "    try:\n"
        "        return await coro\n"
        "    except TimeoutError:\n"
        "        return default_value\n"
    )
    assert rules(source) == {"silent-except"}
    reraised = (
        "def f():\n    try:\n        g()\n    except KeyError:\n"
        "        raise ValueError from None\n"
    )
    assert rules(reraised) == set()


def test_blind_except_that_reraises_is_fine():
    source = "def f():\n    try:\n        g()\n    except Exception:\n        log()\n        raise"
    assert rules(source) == set()


def test_docstring_that_adds_information():
    source = 'def run_with_timeout(coro, timeout):\n    """Cancel coro after timeout seconds."""\n'
    assert rules(source) == set()


def test_ignore_comment():
    source = (
        "def f():\n    try:\n        g()\n"
        "    except KeyError:  # cleanup: ignore[silent-except] a miss is expected\n"
        "        pass\n"
    )
    assert rules(source) == set()


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
