#!/usr/bin/env python3
"""One-off migration of skill ``metadata.version`` from semver to CalVer.

Rewrites every tracked skill's ``metadata.version`` to ``YYYY.MM.DD``, using the
date of the last commit that touched that skill's directory — so the stamp
carries real information instead of flattening everything to today.

    python scripts/migrate_to_calver.py            # dry run, prints the plan
    python scripts/migrate_to_calver.py --apply    # write the files

Delete this script once the migration has landed; ``bump_skill_version.py``
maintains the dates from then on.

Stdlib-only, matching the other scripts in this folder.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

SKILL_ROOTS = (
    "developing-with-holoviz",
    "contributing-to-holoviz",
    "creating-custom-holoviz-skills",
)

# Deliberately permissive: matches the semver we're migrating *from* and the
# CalVer we're migrating *to*, so re-running is a no-op rather than an error.
VERSION_RE = re.compile(r'^(?P<indent>\s+)version:\s*(?P<q>["\']?)(?P<ver>[0-9][0-9.]*)(?P=q)\s*$')
CALVER_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def last_commit_date(path: Path, root: Path) -> str:
    """``YYYY-MM-DD`` of the last commit touching *path*, or today if untracked."""
    rel = path.relative_to(root).as_posix()
    res = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", rel],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    stamp = res.stdout.strip()
    return stamp if res.returncode == 0 and stamp else date.today().isoformat()


def split_frontmatter(text: str) -> tuple[list[str], int, int] | None:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines, 0, i
    return None


def rewrite(text: str, calver: str) -> tuple[str, str] | None:
    """Return ``(new_text, old_version)``, or None if nothing to change."""
    fm = split_frontmatter(text)
    if not fm:
        return None
    lines, start, end = fm
    for i in range(start + 1, end):
        m = VERSION_RE.match(lines[i].rstrip("\n"))
        if not m:
            continue
        old = m["ver"]
        if CALVER_RE.match(old):
            return None  # already migrated
        q = m["q"] or '"'
        nl = "\n" if lines[i].endswith("\n") else ""
        lines[i] = f'{m["indent"]}version: {q}{calver}{q}{nl}'
        return "".join(lines), old
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args(argv)

    root = repo_root()
    skill_mds = sorted(md for r in SKILL_ROOTS for md in (root / r).rglob("SKILL.md"))
    if not skill_mds:
        print("No SKILL.md files found — run from inside the repo.", file=sys.stderr)
        return 1

    planned = 0
    for md in skill_mds:
        calver = last_commit_date(md.parent, root).replace("-", ".")
        result = rewrite(md.read_text(encoding="utf-8"), calver)
        rel = md.relative_to(root).as_posix()
        if result is None:
            print(f"  skip  {rel}")
            continue
        new_text, old = result
        planned += 1
        print(f"  {'write' if args.apply else 'plan '} {rel}: {old} -> {calver}")
        if args.apply:
            md.write_text(new_text, encoding="utf-8")

    verb = "Migrated" if args.apply else "Would migrate"
    print(f"\n{verb} {planned} skill version(s).")
    if not args.apply and planned:
        print("Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
