"""Generate docs/skills/*.md pages from SKILL.md files in the repo root.

Each top-level directory in REPO_ROOT that is NOT in EXCLUDE_DIRS is scanned
recursively for SKILL.md files. For every SKILL.md found, a corresponding
Markdown page is written under docs/skills/ with front matter and HTML comments
stripped, so the rendered doc page shows only the human-facing content.

Run this before `zensical build` / `zensical serve`. The pixi tasks in
pixi.toml wire this up automatically.

This script is deliberately self-contained (stdlib only) so it runs in any
environment where Zensical runs.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT_DIR = DOCS_DIR / "skills"

# Skill source directories live at the repo root. We scan every top-level
# directory except these.
EXCLUDE_DIRS = {
    ".cache",
    ".git",
    ".github",
    ".pixi",
    "docs",
    "scripts",
    "site",
}

# Matches a YAML front matter block at the very start of a file:
#   ---
#   key: value
#   ---
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

# Matches an HTML comment block (non-greedy, multi-line).
HTML_COMMENT_RE = re.compile(r"<!--.*?-->\s*\n?", re.DOTALL)


def strip_frontmatter_and_comments(text: str) -> str:
    """Remove leading YAML front matter and any HTML comments."""
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = HTML_COMMENT_RE.sub("", text)
    return text.lstrip()


def find_skill_files(root: Path) -> list[Path]:
    """Find every SKILL.md under top-level dirs that aren't excluded."""
    skills: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in EXCLUDE_DIRS or child.name.startswith("."):
            continue
        skills.extend(sorted(child.rglob("SKILL.md")))
    return skills


def output_path_for(skill_md: Path) -> Path:
    """Map a SKILL.md source path to its docs/skills/<slug>.md destination.

    Example:
        developing-with-holoviz/create-custom-skill-template/SKILL.md
        -> docs/skills/create-custom-skill-template.md
    """
    slug = skill_md.parent.name
    return OUTPUT_DIR / f"{slug}.md"


def build() -> int:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    skills = find_skill_files(REPO_ROOT)
    if not skills:
        print("build_stubs: no SKILL.md files found — nothing to generate.")
        return 0

    seen_slugs: dict[str, Path] = {}
    for skill_md in skills:
        dest = output_path_for(skill_md)
        if dest.name in seen_slugs:
            print(
                f"build_stubs: ERROR — duplicate skill slug '{dest.stem}': "
                f"{seen_slugs[dest.name]} and {skill_md}",
                file=sys.stderr,
            )
            return 1
        seen_slugs[dest.name] = skill_md

        cleaned = strip_frontmatter_and_comments(skill_md.read_text(encoding="utf-8"))
        dest.write_text(cleaned, encoding="utf-8")
        rel_src = skill_md.relative_to(REPO_ROOT)
        rel_dst = dest.relative_to(REPO_ROOT)
        print(f"build_stubs: {rel_src}  ->  {rel_dst}")

    print(f"build_stubs: generated {len(skills)} page(s) in {OUTPUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
