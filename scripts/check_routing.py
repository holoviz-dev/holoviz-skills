#!/usr/bin/env python3
"""Check that every skill file an agent is pointed at exists and can be reached.

Agents find a sub-skill or reference only through a routing skill's Loading
Table or a link from another skill file, so a renamed file, or a new one that
nothing names, drops out without an error. This runs as a pre-commit hook over
tracked files and reports:

* a ``path.md`` in a routing skill's Loading Table that doesn't exist;
* a relative ``.md`` link in a skill file that doesn't resolve, using the same
  check the docs build warns with (``build_stubs.find_broken_links``);
* a sub-skill ``SKILL.md`` missing from its routing skill's Loading Table;
* any other ``.md`` under ``skills/`` that neither the Loading Table nor its
  sub-skill's ``SKILL.md`` names.

Exit status: 0 clean, 1 problems found. Stdlib-only, matching the other
scripts in this folder.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from build_stubs import find_broken_links

TABLE_PATH_RE = re.compile(r"`([^`\s]+\.md)`")


def tracked_files(root: Path) -> set[PurePosixPath]:
    out = subprocess.run(
        ["git", "--no-optional-locks", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
        cwd=root,
    ).stdout
    return {PurePosixPath(line) for line in out.splitlines()}


def loading_table_paths(skill_md: str) -> list[str]:
    match = re.search(r"^## Loading Table\n(.*?)(?=^## |\Z)", skill_md, re.MULTILINE | re.DOTALL)
    return TABLE_PATH_RE.findall(match.group(1)) if match else []


def owning_skill(path: PurePosixPath, tracked: set[PurePosixPath]) -> PurePosixPath | None:
    for parent in path.parents:
        candidate = parent / "SKILL.md"
        if candidate != path and candidate in tracked:
            return candidate
    return None


def check(root: Path) -> list[str]:
    tracked = tracked_files(root)
    skill_roots = {p.parts[0] for p in tracked if p.name == "SKILL.md" and len(p.parts) == 2}
    markdown = sorted(
        p
        for p in tracked
        if p.suffix == ".md" and p.parts[0] in skill_roots and (root / p).exists()
    )
    problems = []

    for path in markdown:
        text = (root / path).read_text(encoding="utf-8")
        for lineno, target in find_broken_links(text, Path(path), {}):
            problems.append(f"{path}:{lineno}: link to {target} doesn't resolve")

    routing_skills = [p for p in markdown if p.name == "SKILL.md" and len(p.parts) == 2]
    for routing in routing_skills:
        base = routing.parent
        text = (root / routing).read_text(encoding="utf-8")
        listed = {base / p for p in loading_table_paths(text)}
        for path in sorted(listed):
            if path not in tracked:
                problems.append(f"{routing}: Loading Table names {path}, which doesn't exist")

        for path in markdown:
            if base / "skills" not in path.parents or path in listed:
                continue
            if path.name == "SKILL.md":
                problems.append(f"{path}: not in the Loading Table of {routing}")
                continue
            owner = owning_skill(path, tracked)
            if owner == routing:
                problems.append(
                    f"{path}: not in the Loading Table of {routing}, and its folder has no SKILL.md"
                )
            elif path.name not in (root / owner).read_text(encoding="utf-8"):
                problems.append(
                    f"{path}: named in neither the Loading Table of {routing} nor {owner}"
                )

    return problems


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    problems = check(root)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
