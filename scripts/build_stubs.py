"""Generate docs pages from SKILL.md files and update the nav.

Each top-level directory in REPO_ROOT that is NOT in EXCLUDE_DIRS is scanned
recursively for SKILL.md files.  Categories (dirs with sub-skills) get a
subdirectory under ``docs/`` with an auto-generated ``index.md`` and one stub
per sub-skill.  Standalone skills (a single SKILL.md, no children) get a flat
page under ``docs/``.

After generating pages, the ``nav`` array in ``zensical.toml`` is rewritten so
the site navigation always reflects the current repo contents.

Run this before ``zensical build`` / ``zensical serve``.  The pixi tasks in
pixi.toml wire this up automatically.

This script is deliberately self-contained (stdlib only) so it runs in any
environment where Zensical runs.
"""

from __future__ import annotations

import re
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ZENSICAL_TOML = REPO_ROOT / "zensical.toml"

# Top-level directories to skip when scanning for skills.
EXCLUDE_DIRS = {
    ".cache",
    ".git",
    ".github",
    ".pixi",
    "docs",
    "scripts",
    "site",
}

# Explicit section order.  Categories listed here appear in this order;
# any unlisted ones are appended alphabetically at the end.
SECTION_ORDER: list[str] = [
    "developing-with-holoviz",
    "contributing-to-holoviz",
]

# Explicit sub-skill order within a category.  Unlisted sub-skills are
# appended alphabetically after the listed ones.
SUBSKILL_ORDER: dict[str, list[str]] = {
    "developing-with-holoviz": [
        "param",
        "hvplot",
        "panel",
        "panel-material-ui",
        "panel-holoviews",
        "panel-custom-components",
        "panel-pytest-playwright",
    ],
}

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->\s*\n?", re.DOTALL)
SKILL_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(([^\)]*?/?([\w][\w-]*)/SKILL\.md)\)",
)
NAV_BLOCK_RE = re.compile(r"^nav\s*=\s*\[.*?^\]", re.MULTILINE | re.DOTALL)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def strip_frontmatter_and_comments(text: str) -> str:
    """Remove leading YAML front matter and any HTML comments."""
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = HTML_COMMENT_RE.sub("", text)
    return text.lstrip()


def rewrite_skill_links(text: str) -> str:
    """Rewrite ``[name](…/slug/SKILL.md)`` → ``[name](slug.md)``."""
    return SKILL_LINK_RE.sub(r"[\1](\3.md)", text)


def inject_source_meta(text: str, source_rel: str) -> str:
    """Prepend a hidden element with the SKILL.md source path.

    The companion ``copy-markdown.js`` script reads this to construct the
    raw GitHub URL for the "Copy Markdown" button.
    """
    meta = (
        f'<div data-skill-source="{source_rel}" '
        f'style="display:none"></div>\n\n'
    )
    return meta + text


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").title()


def extract_h1_title(text: str) -> str | None:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s.lstrip("# ").strip()
    return None


def extract_description(text: str) -> str | None:
    """Return the YAML ``description:`` value from raw SKILL.md text."""
    m = re.search(r"^description:\s*(.+)", text, re.MULTILINE)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_skill_files(root: Path) -> list[Path]:
    """Find every SKILL.md under top-level dirs that aren't excluded."""
    skills: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in EXCLUDE_DIRS or child.name.startswith("."):
            continue
        skills.extend(sorted(child.rglob("SKILL.md")))
    return skills


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class SubSkill:
    """A single sub-skill within a category."""

    def __init__(self, slug: str, title: str, source: Path, cleaned: str):
        self.slug = slug
        self.title = title
        self.source = source
        self.cleaned = cleaned


class Category:
    """A top-level directory containing a routing SKILL.md and sub-skills."""

    def __init__(self, dirname: str, title: str, description: str):
        self.dirname = dirname
        self.title = title
        self.description = description
        self.children: list[SubSkill] = []


class Standalone:
    """A top-level directory with only a single SKILL.md (no sub-skills)."""

    def __init__(self, slug: str, title: str, source: Path, cleaned: str):
        self.slug = slug
        self.title = title
        self.source = source
        self.cleaned = cleaned


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def ordered_children(cat: Category) -> list[SubSkill]:
    """Return *cat.children* in the preferred order."""
    explicit = SUBSKILL_ORDER.get(cat.dirname, [])
    rank = {slug: i for i, slug in enumerate(explicit)}
    fallback = len(explicit)
    return sorted(
        cat.children,
        key=lambda c: (rank.get(c.slug, fallback), c.title.lower()),
    )


def ordered_sections(
    categories: dict[str, Category],
    standalones: dict[str, Standalone],
) -> list[Category | Standalone]:
    """Return all sections in the preferred display order."""
    seen: set[str] = set()
    result: list[Category | Standalone] = []

    # Explicit order first.
    for dirname in SECTION_ORDER:
        if dirname in categories:
            result.append(categories[dirname])
            seen.add(dirname)
        elif dirname in standalones:
            result.append(standalones[dirname])
            seen.add(dirname)

    # Remaining categories (alphabetical).
    for dirname in sorted(categories):
        if dirname not in seen:
            result.append(categories[dirname])
            seen.add(dirname)

    # Remaining standalones (alphabetical).
    for dirname in sorted(standalones):
        if dirname not in seen:
            result.append(standalones[dirname])

    return result


# ---------------------------------------------------------------------------
# Index page generation
# ---------------------------------------------------------------------------

def generate_index_md(cat: Category) -> str:
    """Create a docs-facing index page for a category section."""
    children = ordered_children(cat)
    lines = [
        f"# {cat.title}",
        "",
        cat.description,
        "",
        "| Skill | Description |",
        "|---|---|",
    ]
    for child in children:
        # Use the first non-empty paragraph after the H1 as a short description.
        desc = _first_paragraph(child.cleaned)
        lines.append(f"| [{child.title}]({child.slug}.md) | {desc} |")
    lines.append("")
    return "\n".join(lines)


def _first_paragraph(text: str) -> str:
    """Extract the first non-heading, non-empty paragraph from *text*."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Truncate long lines.
        if len(stripped) > 120:
            return stripped[:117] + "..."
        return stripped
    return ""


# ---------------------------------------------------------------------------
# Nav generation
# ---------------------------------------------------------------------------

def build_nav_toml(
    sections: list[Category | Standalone],
) -> str:
    lines = ["nav = [", '  { "Home" = "index.md" },']

    for section in sections:
        if isinstance(section, Standalone):
            lines.append(f'  {{ "{section.title}" = "{section.slug}.md" }},')
        else:
            lines.append(f'  {{ "{section.title}" = [')
            lines.append(f'    "{section.dirname}/index.md",')
            for child in ordered_children(section):
                lines.append(
                    f'    {{ "{child.title}" = "{section.dirname}/{child.slug}.md" }},'
                )
            lines.append("  ] },")

    lines.append("]")
    return "\n".join(lines)


def update_zensical_nav(nav_toml: str) -> None:
    if not ZENSICAL_TOML.exists():
        print("build_stubs: zensical.toml not found — skipping nav update.")
        return

    original = ZENSICAL_TOML.read_text(encoding="utf-8")
    updated, count = NAV_BLOCK_RE.subn(nav_toml, original, count=1)
    if count == 0:
        print(
            "build_stubs: WARNING — could not locate nav block in zensical.toml; "
            "nav was NOT updated.",
            file=sys.stderr,
        )
        return
    ZENSICAL_TOML.write_text(updated, encoding="utf-8")
    print("build_stubs: updated nav in zensical.toml")


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build() -> int:
    # Clean previous output — remove any generated directories/files under
    # docs/ except index.md and assets/.
    for child in DOCS_DIR.iterdir():
        if child.name in ("index.md", "assets"):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    all_skills = find_skill_files(REPO_ROOT)
    if not all_skills:
        print("build_stubs: no SKILL.md files found — nothing to generate.")
        return 0

    # ---- Classify each SKILL.md ----
    # First pass: figure out which top-level dirs have sub-skills.
    tld_skills: dict[str, list[Path]] = OrderedDict()
    for skill_md in all_skills:
        rel = skill_md.relative_to(REPO_ROOT)
        tld = rel.parts[0]
        tld_skills.setdefault(tld, []).append(skill_md)

    categories: dict[str, Category] = {}
    standalones: dict[str, Standalone] = {}

    for tld, members in tld_skills.items():
        roots = [m for m in members if len(m.relative_to(REPO_ROOT).parts) == 2]
        children = [m for m in members if len(m.relative_to(REPO_ROOT).parts) > 2]

        if children:
            # Category with sub-skills.
            root_raw = roots[0].read_text(encoding="utf-8") if roots else ""
            root_cleaned = strip_frontmatter_and_comments(root_raw) if root_raw else ""
            title = extract_h1_title(root_cleaned) or slug_to_title(tld)
            desc = extract_description(root_raw) or ""

            cat = Category(tld, title, desc)

            for child_md in children:
                raw = child_md.read_text(encoding="utf-8")
                cleaned = strip_frontmatter_and_comments(raw)
                cleaned = rewrite_skill_links(cleaned)
                slug = child_md.parent.name
                child_title = extract_h1_title(cleaned) or slug_to_title(slug)
                cat.children.append(SubSkill(slug, child_title, child_md, cleaned))

            categories[tld] = cat
        elif roots:
            # Standalone skill.
            raw = roots[0].read_text(encoding="utf-8")
            cleaned = strip_frontmatter_and_comments(raw)
            cleaned = rewrite_skill_links(cleaned)
            title = extract_h1_title(cleaned) or slug_to_title(tld)
            standalones[tld] = Standalone(tld, title, roots[0], cleaned)

    # ---- Write output files ----
    page_count = 0

    for cat in categories.values():
        out_dir = DOCS_DIR / cat.dirname
        out_dir.mkdir(parents=True, exist_ok=True)

        # Section index page (docs-facing, not the routing skill).
        index_md = generate_index_md(cat)
        (out_dir / "index.md").write_text(index_md, encoding="utf-8")
        print(f"build_stubs: {cat.dirname}/  ->  docs/{cat.dirname}/index.md")
        page_count += 1

        for child in cat.children:
            dest = out_dir / f"{child.slug}.md"
            rel_src = child.source.relative_to(REPO_ROOT)
            content = inject_source_meta(child.cleaned, str(rel_src))
            dest.write_text(content, encoding="utf-8")
            print(f"build_stubs: {rel_src}  ->  docs/{cat.dirname}/{child.slug}.md")
            page_count += 1

    for st in standalones.values():
        dest = DOCS_DIR / f"{st.slug}.md"
        rel_src = st.source.relative_to(REPO_ROOT)
        content = inject_source_meta(st.cleaned, str(rel_src))
        dest.write_text(content, encoding="utf-8")
        print(f"build_stubs: {rel_src}  ->  docs/{st.slug}.md")
        page_count += 1

    # ---- Update nav ----
    sections = ordered_sections(categories, standalones)
    nav_toml = build_nav_toml(sections)
    update_zensical_nav(nav_toml)

    print(f"build_stubs: generated {page_count} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
