#!/usr/bin/env python3
"""Auto-stamp the ``metadata.version`` of any skill that changed on a branch.

Used as a pre-commit hook (see ``.pre-commit-config.yaml``). The script derives
the changed skills from the working-tree diff against the base branch and sets
each changed skill's ``metadata.version`` (in its nearest ancestor ``SKILL.md``)
to today's date in ``YYYY.MM.DD`` form, then re-stages the SKILL.md. Deriving
from the diff rather than the filenames pre-commit passes matters because the
lint task runs ``pre-commit run --all-files``, which passes *every* skill file —
stamping by filename would bump skills that never changed.

Design notes
------------
* Versions are **CalVer**: the value is the date the skill last changed, not a
  semantic version. A date cannot express severity, so a typo fix and a
  reversed recommendation stamp identically — record the *why* in
  ``CHANGELOG.md``, not in the version.
* Source of truth is the **tracked** top-level skill tree
  (``developing-with-holoviz/``, ``contributing-to-holoviz/``,
  ``creating-custom-holoviz-skills/``). The ``holoviz_skills/skills/``,
  ``.claude/skills``, ``.agents/skills`` and ``.github/skills`` copies are
  generated/gitignored (see the ``.*/skills/*`` rule in ``.gitignore``), so the
  hook never touches them.
* One stamp per branch: the eligible skills come from the working-tree diff
  against the merge-base with the base branch (``origin/main`` by default;
  override with the ``SKILL_VERSION_BASE_REF`` env var), and the working version
  is compared against that same merge-base, so a skill is stamped at most once
  across a whole PR no matter how many commits touch it. Falls back to ``HEAD``
  (the original per-commit behavior, driven by the filenames pre-commit passes)
  when no base branch can be resolved — detached HEAD, no ``main``, or a
  shallow clone that lacks it.
* Idempotent / respects manual edits: once the staged version differs from the
  baseline (already stamped on this branch, hand-edited, or freshly seeded), a
  re-run is a no-op. A second edit on the same day is therefore also a no-op —
  the date is already correct.
* Brand-new skills (SKILL.md not yet in HEAD) keep their authored version.
* Skills with no ``metadata.version`` get today's date seeded on first edit.
* Stdlib-only, matching the convention of the other scripts in this folder.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# Tracked skill roots (the source of truth). Files outside these are ignored.
SKILL_ROOTS = (
    "developing-with-holoviz",
    "contributing-to-holoviz",
    "creating-custom-holoviz-skills",
)

SEED_VERSION = None  # unused: new skills are seeded with today's date

# Env var to override the base ref used for version comparison.
BASE_REF_ENV = "SKILL_VERSION_BASE_REF"
# Tried in order when no override is set; first that exists wins.
DEFAULT_BASE_CANDIDATES = ("origin/main", "origin/master", "main", "master")

# Matches an indented ``version: "..."`` line inside the metadata block.
# Permissive on the value so both the legacy ``x.y.z`` and CalVer ``YYYY.MM.DD``
# parse — the migration lands over several commits and the hook must not choke
# on whichever form it meets.
VERSION_RE = re.compile(r'^(?P<indent>\s+)version:\s*(?P<q>["\']?)(?P<ver>[0-9][0-9.]*)(?P=q)\s*$')
METADATA_RE = re.compile(r"^metadata:\s*$")


def today() -> str:
    """Today's date as ``YYYY.MM.DD``."""
    return date.today().strftime("%Y.%m.%d")


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _ref_exists(ref: str) -> bool:
    return _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]).returncode == 0


def baseline_ref() -> str:
    """Resolve the ref to compare skill versions against.

    Prefer the merge-base with the branch's base branch, so a whole PR/branch
    bumps a given skill at most once no matter how many commits touch it. Honor
    the ``SKILL_VERSION_BASE_REF`` env override, else try the default base
    candidates. Fall back to ``HEAD`` (the original per-commit behavior) when no
    base can be resolved — detached HEAD, no ``main``, or a shallow clone.
    """
    env = os.environ.get(BASE_REF_ENV, "").strip()
    candidates = [env] if env else list(DEFAULT_BASE_CANDIDATES)
    for ref in candidates:
        if not ref or not _ref_exists(ref):
            continue
        mb = _git(["merge-base", ref, "HEAD"])
        if mb.returncode == 0 and mb.stdout.strip():
            return mb.stdout.strip()
    return "HEAD"


def git_show_text(ref: str, relpath: str) -> str | None:
    """Return the content of ``relpath`` at ``ref``, or None if not tracked there."""
    res = _git(["show", f"{ref}:{relpath}"])
    return res.stdout if res.returncode == 0 else None


def changed_paths(ref: str) -> set[str]:
    """Return tracked paths changed from ``ref`` in the working tree."""
    res = _git(["diff", "--name-only", ref])
    if res.returncode != 0:
        return set()
    return set(res.stdout.splitlines())


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
    return m["ver"]


def bump_text(text: str) -> str | None:
    """Return ``text`` with the skill version stamped to today's date.

    Returns None if the file has no frontmatter at all (cannot version it).
    """
    fm = split_frontmatter(text)
    if not fm:
        return None
    lines, start, end = fm

    found = find_version(lines, start, end)
    if found:
        idx, m = found
        q = m["q"] or '"'
        nl = "\n" if lines[idx].endswith("\n") else ""
        lines[idx] = f"{m['indent']}version: {q}{today()}{q}{nl}"
        return "".join(lines)

    # No version yet -> seed today's date, under an existing metadata: block.
    seed_line = f'  version: "{today()}"\n'
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


def skill_owners(root: Path, paths: list[str]) -> set[Path]:
    """Unique owning SKILL.md files for ``paths`` under a tracked skill root."""
    owners: set[Path] = set()
    for f in paths:
        abs = (root / f).resolve()
        try:
            rel_parts = abs.relative_to(root).parts
        except ValueError:
            continue
        if not rel_parts or rel_parts[0] not in SKILL_ROOTS:
            continue
        owner = owning_skill_md(abs, root)
        if owner is not None:
            owners.add(owner)
    return owners


def main(argv: list[str]) -> int:
    root = repo_root()
    changed = [Path(a) for a in argv]

    # Compare against the branch base (merge-base with main), not HEAD, so a
    # skill bumps at most once per branch/PR regardless of commit count. Falls
    # back to "HEAD" — the original per-commit behavior — when unresolvable.
    base = baseline_ref()
    if base == "HEAD":
        # Fallback (detached HEAD, no base branch): derive the changed skills
        # from the staged files pre-commit passes in argv.
        candidates = skill_owners(root, changed)
    else:
        # One stamp per branch: derive the changed skills from the working-tree
        # diff against the base. This survives `pre-commit run --all-files`,
        # which passes every skill file (stamping all of them otherwise), and
        # only bumps the skill whose tree actually changed, not relatives that
        # share a directory prefix with it.
        candidates = skill_owners(root, sorted(changed_paths(base)))

    bumped: list[str] = []
    for md in sorted(candidates):
        rel = md.relative_to(root).as_posix()
        base_text = git_show_text(base, rel)
        if base_text is None:
            # Skill not present at the base ref (new on this branch) — keep the
            # authored version.
            continue

        current_text = md.read_text(encoding="utf-8")
        base_ver = version_string(base_text)
        cur_ver = version_string(current_text)

        # Idempotency / respect manual bumps: only act when the staged version
        # still matches the base's. Once it differs — already bumped on this
        # branch, hand-edited, or seeded where the base had none
        # (None != "x.y.z") — leave it alone. This makes re-running the hook a
        # no-op and prevents bump-on-every-commit across a branch.
        if cur_ver != base_ver:
            continue

        new_text = bump_text(current_text)
        if new_text is None or new_text == current_text:
            continue

        md.write_text(new_text, encoding="utf-8")
        subprocess.run(["git", "add", rel], check=True)
        bumped.append(f"{rel}: {cur_ver or '(none)'} -> {version_string(new_text)}")

    if bumped:
        print("Stamped skill version(s):")
        for line in bumped:
            print(f"  {line}")
        # Non-zero so pre-commit reports the modification; re-commit applies it.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
