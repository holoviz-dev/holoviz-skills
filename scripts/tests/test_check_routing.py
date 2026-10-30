"""Tests for the size checks in check_routing.py: the row budget and the file-size warnings."""

import subprocess

import check_routing


def make_repo(root, files):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


def test_size_warnings_flag_only_files_over_their_guideline(tmp_path, monkeypatch):
    """A SKILL.md and a reference each get their own limit."""
    monkeypatch.setattr(check_routing, "SKILL_MD_WARN_CHARS", 100)
    monkeypatch.setattr(check_routing, "REFERENCE_WARN_CHARS", 200)
    make_repo(
        tmp_path,
        {
            "cat/SKILL.md": "x" * 150,
            "cat/skills/a/SKILL.md": "x" * 50,
            "cat/skills/a/short.md": "x" * 150,
            "cat/skills/a/long.md": "x" * 250,
        },
    )
    warned = [w.split()[1] for w in check_routing.size_warnings(tmp_path)]
    assert warned == ["cat/SKILL.md", "cat/skills/a/long.md"]


def test_row_over_budget_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(check_routing, "ROW_BUDGET_CHARS", 100)
    router = "## Loading Table\n\n| Need | Files |\n|---|---|\n| Plot | `skills/a/SKILL.md` |\n"
    make_repo(tmp_path, {"cat/SKILL.md": router, "cat/skills/a/SKILL.md": "x" * 100})

    problems = check_routing.check(tmp_path)

    assert problems == [
        f"cat/SKILL.md: Loading Table row 'Plot' loads {len(router) + 100:,} chars, "
        "over the 100 budget"
    ]
