"""Tests for the page sizes and Context cost tables that build_stubs.py adds to the docs."""

from build_stubs import generate_cost_md, inject_version_note, loading_table_rows, text_stats

ROUTER = """---
description: Route.
---

## Loading Table

| Need | Files |
|---|---|
| Plot | `skills/a.md` + `skills/b.md` |
| Moved | `skills/gone.md` |

## Skill Map

| [a](skills/a.md) | not a Loading Table row |
"""


def four_chars_per_token(text):
    return len(text) // 4


def test_text_stats_adds_tokens_only_with_a_counter():
    assert text_stats("one two three", None) == "13 chars · 3 words"
    assert text_stats("one two three", four_chars_per_token) == (
        "13 chars · 3 words · 3 estimated tokens"
    )


def test_version_note_carries_the_size():
    page = inject_version_note("# Title\n\nBody", "2026.10.20", "13 chars · 3 words")
    assert page.splitlines()[2] == "*Skill version 2026.10.20 · 13 chars · 3 words*"
    unversioned = inject_version_note("# Title\n\nBody", None, "13 chars · 3 words")
    assert unversioned.splitlines()[2] == "*13 chars · 3 words*"


def test_cost_row_counts_the_routing_file_plus_every_file_it_lists(tmp_path):
    """A row whose file is missing is left out; check_routing.py reports the missing file."""
    router = tmp_path / "SKILL.md"
    router.write_text(ROUTER)
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "a.md").write_text("aaaa")
    (tmp_path / "skills" / "b.md").write_text("bb")

    md = generate_cost_md(router, None)

    # The routing file and both files, joined by a newline each.
    expected = len(ROUTER) + 1 + len("aaaa") + 1 + len("bb")
    assert f"| Plot | 2 | {expected:,} chars" in md
    assert "Moved" not in md
    assert "not a Loading Table row" not in md


def test_loading_table_rows_pairs_each_need_with_its_files():
    assert loading_table_rows(ROUTER) == [
        ("Plot", ["skills/a.md", "skills/b.md"]),
        ("Moved", ["skills/gone.md"]),
    ]
