#!/usr/bin/env python3
"""Auto-bump the ``metadata.version`` of any skill that changed in a commit.

Used as a pre-commit hook (see ``.pre-commit-config.yaml``). pre-commit passes
the staged filenames; this script maps each one to the *owning* skill (the
nearest ancestor directory containing a ``SKILL.md``) and patch-bumps that
skill's ``metadata.version`` in its frontmatter, then re-stages the SKILL.md.

Design notes
------------
* Source of truth is the **tracked** top-level skill tree
  (``developing-with-holoviz/``, ``contributing-to-holoviz/``,
  ``creating-custom-holoviz-skills/``). The ``holoviz_skills/skills/``,
  ``.claude/skills`` and ``.agents/skills`` copies are generated/gitignored,
  so the hook never touches them.
* Idempotent: the bump only happens when the SKILL.md's version still matches
  HEAD. Once bumped (staged version != HEAD version) a re-run is a no-op, so
  re-committing after pre-commit re-stages does not double-bump.
* Brand-new skills (SKILL.md not yet in HEAD) keep their authored version.
* Skills with no ``metadata.version`` get one seeded at ``0.1.0`` on first edit.
* Stdlib-only, matching the convention of the other scripts in this folder.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Tracked skill roots (the source of truth). Files outside these are ignored.
SKILL_ROOTS = (
    "developing-with-holoviz",
    "contributing-to-holoviz",
    "creating-custom-holoviz-skills",
)

SEED_VERSION = "0.1.0"

# Matches an indented ``version: "x.y.z"`` line inside the metadata block.
VERSION_RE = re.compile(
    r'^(?P<indent>\s+)version:\s*(?P<q>["\']?)(?P<maj>\d+)\.(?P<min>\d+)\.(?P<pat>\d+)(?P=q)\s*$'
)
METADATA_RE = re.compile(r"^metadata:\s*$")


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def git_head_text(relpath: str) -> str | None:
    """Return the content of ``relpath`` at HEAD, or None if not tracked there."""
    res = subprocess.run(
        ["git", "show", f"HEAD:{relpath}"],
        capture_output=True,
        text=True,
    )
    return res.stdout if res.returncode == 0 else None


def split_frontmatter(text: str) -> tuple[list[str], int, int] | None:
    """Return (lines, start_idx, end_idx) for the frontmatter block.

    ``start_idx``/``end_idx`` are the line indices of the opening and closing
    ``---`` fences. Returns None if there is no leading frontmatter.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines, 0, i
    return None


def find_version(lines: list[str], start: int, end: int):
    for i in range(start + 1, end):
        m = VERSION_RE.match(lines[i].rstrip("\n"))
        if m:
            return i, m
    return None


def version_string(text: str) -> str | None:
    fm = split_frontmatter(text)
    if not fm:
        return None
    lines, start, end = fm
    found = find_version(lines, start, end)
    if not found:
        return None
    _, m = found
    return f"{m['maj']}.{m['min']}.{m['pat']}"


def bump_text(text: str) -> str | None:
    """Return ``text`` with the skill version patch-bumped (or seeded).

    Returns None if the file has no frontmatter at all (cannot version it).
    """
    fm = split_frontmatter(text)
    if not fm:
        return None
    lines, start, end = fm

    found = find_version(lines, start, end)
    if found:
        idx, m = found
        newver = f'{m["maj"]}.{m["min"]}.{int(m["pat"]) + 1}'
        q = m["q"] or '"'
        nl = "\n" if lines[idx].endswith("\n") else ""
        lines[idx] = f'{m["indent"]}version: {q}{newver}{q}{nl}'
        return "".join(lines)

    # No version yet -> seed one, under an existing metadata: block if present.
    seed_line = f'  version: "{SEED_VERSION}"\n'
    for i in range(start + 1, end):
        if METADATA_RE.match(lines[i].rstrip("\n")):
            lines.insert(i + 1, seed_line)
            return "".join(lines)
    # No metadata block either -> create one just before the closing fence.
    lines.insert(end, "metadata:\n")
    lines.insert(end + 1, seed_line)
    return "".join(lines)


def owning_skill_md(path: Path, root: Path) -> Path | None:
    """Nearest ancestor SKILL.md for ``path`` (a changed file)."""
    p = path if path.is_dir() else path.parent
    while True:
        candidate = p / "SKILL.md"
        if candidate.exists():
            return candidate
        if p == root or p.parent == p:
            return None
        p = p.parent


def main(argv: list[str]) -> int:
    root = repo_root()
    changed = [Path(a) for a in argv]

    # Collect the unique set of owning SKILL.md files for changed paths that
    # live under a tracked skill root.
    skill_mds: set[Path] = set()
    for f in changed:
        abs = (root / f).resolve()
        try:
            rel_parts = abs.relative_to(root).parts
        except ValueError:
            continue
        if not rel_parts or rel_parts[0] not in SKILL_ROOTS:
            continue
        owner = owning_skill_md(abs, root)
        if owner is not None:
            skill_mds.add(owner)

    bumped: list[str] = []
    for md in sorted(skill_mds):
        rel = md.relative_to(root).as_posix()
        head_text = git_head_text(rel)
        if head_text is None:
            # New skill not in HEAD yet — keep the authored version.
            continue

        current_text = md.read_text(encoding="utf-8")
        head_ver = version_string(head_text)
        cur_ver = version_string(current_text)

        # Idempotency / respect manual bumps: only act when the staged version
        # still matches HEAD's. Once it differs — because we already bumped it in
        # this commit, the author bumped it by hand, or it was seeded where HEAD
        # had none (None != "x.y.z") — leave it alone. This makes re-running the
        # hook a no-op and prevents the bump-on-every-commit loop.
        if cur_ver != head_ver:
            continue

        new_text = bump_text(current_text)
        if new_text is None or new_text == current_text:
            continue

        md.write_text(new_text, encoding="utf-8")
        subprocess.run(["git", "add", rel], check=True)
        bumped.append(f"{rel}: {cur_ver or '(none)'} -> {version_string(new_text)}")

    if bumped:
        print("Bumped skill version(s):")
        for line in bumped:
            print(f"  {line}")
        # Non-zero so pre-commit reports the modification; re-commit applies it.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
