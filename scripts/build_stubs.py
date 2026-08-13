"""Generate docs pages from SKILL.md files and update the nav.

Each top-level directory in REPO_ROOT that is NOT in EXCLUDE_DIRS is scanned
recursively for SKILL.md files.  Categories (dirs with sub-skills) get a
subdirectory under ``docs/`` with an auto-generated ``index.md`` and one stub
per sub-skill.  Standalone skills (a single SKILL.md, no children) get a flat
page under ``docs/``.

Sub-skills that have sibling ``.md`` files alongside their SKILL.md get a
nested subdirectory in docs: the SKILL.md becomes ``index.md`` and each
sibling ``.md`` file becomes a page.  Links like ``[name](foo.md)`` resolve
naturally within the nested docs directory.  ``.py`` files in an ``examples/``
or ``scripts/`` subdirectory become pages too, grouped under an "Examples" or
"Scripts" nav node.  ``test_*.py`` files are skipped: they exercise the
scripts rather than documenting them.

After generating pages, the ``nav`` array in ``zensical.toml`` is rewritten so
the site navigation always reflects the current repo contents.

Run this before ``zensical build`` / ``zensical serve``.  The pixi tasks in
pixi.toml wire this up automatically.

This script is deliberately self-contained (stdlib only) so it runs in any
environment where Zensical runs.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"
ZENSICAL_TOML = REPO_ROOT / "zensical.toml"

# Top-level directories to skip when scanning for skills.
#
# `holoviz_skills` matters even though it has no SKILL.md in a clean checkout:
# `holoviz_skills/skills/` is the wheel staging path (hatch force-include, see
# pyproject.toml). If a build leaves it behind, scanning it would emit a
# duplicate "Holoviz Skills" docs category and rewrite the nav. `artifacts`,
# `dist`, and `_build_plugin_tmp` are build outputs containing skill copies for
# the same reason.
EXCLUDE_DIRS = {
    ".cache",
    ".git",
    ".github",
    ".pixi",
    "_build_plugin_tmp",
    "artifacts",
    "dist",
    "docs",
    "holoviz_skills",
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
        "holoviews",
    ],
}

# Explicit reference order within a sub-skill.  Unlisted references are
# appended alphabetically after the listed ones.
REFERENCE_ORDER: dict[str, list[str]] = {
    "panel": [
        "iterating-on-panel-apps",
        "building-custom-components",
        "using-material-ui",
        "using-pytest-playwright",
        "reviewing-panel-apps",
    ],
}

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->\s*\n?", re.DOTALL)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
NAV_BLOCK_RE = re.compile(r"^nav\s*=\s*\[.*?^\]", re.MULTILINE | re.DOTALL)

# Used to find brackets the Markdown parser will try to resolve as a link.
FENCE_RE = re.compile(r"^(```|~~~)")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
# Full (``[text][id]``) and collapsed (``[text][]``) reference links — masked
# before the scan so neither half is mistaken for a stray bracket.
REF_LINK_RE = re.compile(r"\[[^\[\]]*\]\[[^\[\]]*\]")
# ``[text]`` not followed by ``(``, ``[`` or ``:`` — i.e. neither an inline link,
# nor a full/collapsed reference, nor a link definition. Markdown reads it as a
# shortcut reference and warns "unresolved link reference" at build time.
SHORTCUT_LINK_RE = re.compile(r"(?<!\\)\[([^\[\]]+)\](?![(\[:])")
# A bare ``some-reference.md`` inside Python source — docstrings and the doc
# pointers emitted in lint violation messages. The lookbehind keeps it off URL
# paths (``https://…/x.md``) and dotted names.
CODE_DOCREF_RE = re.compile(r"(?<![\w/.-])([a-z0-9][a-z0-9_-]*\.md)")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def strip_frontmatter_and_comments(text: str) -> str:
    """Remove leading YAML front matter and any HTML comments."""
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = HTML_COMMENT_RE.sub("", text)
    return text.lstrip()


def find_shortcut_links(text: str) -> list[tuple[int, str]]:
    """Return ``(lineno, inner)`` for brackets Markdown reads as link references.

    Prose like ``are: [...]`` or ``objects[0]`` outside a code span parses as a
    shortcut reference link, so the docs build emits "unresolved link
    reference". Fenced blocks and inline code are skipped — brackets there are
    literal. Scans raw file text so reported line numbers match the source.
    """
    hits: list[tuple[int, str]] = []
    in_fence = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(raw.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Blank out code spans and well-formed links, preserving offsets, so
        # only genuinely stray brackets survive to the scan.
        masked = raw
        for pattern in (INLINE_CODE_RE, MD_LINK_RE, REF_LINK_RE):
            masked = pattern.sub(lambda m: " " * len(m.group(0)), masked)
        hits.extend(
            (lineno, inner)
            for m in SHORTCUT_LINK_RE.finditer(masked)
            if (inner := m.group(1).strip())
        )
    return hits


def find_broken_links(
    text: str, source_rel: Path, path_map: dict[Path, Path]
) -> list[tuple[int, str]]:
    """Return ``(lineno, target)`` for relative ``.md`` links that point nowhere.

    ``rewrite_internal_links`` leaves an unresolvable target untouched rather
    than rewriting it, so a renamed or deleted reference silently becomes a dead
    docs link. Scans the whole text rather than line by line, because a link
    label may wrap across lines.
    """
    broken: list[tuple[int, str]] = []
    source_dir = source_rel.parent
    for m in MD_LINK_RE.finditer(text):
        target = m.group(2).split("#", 1)[0]
        if not target or target.startswith("http") or not target.endswith(".md"):
            continue
        resolved = (REPO_ROOT / source_dir / target).resolve()
        try:
            rel = resolved.relative_to(REPO_ROOT.resolve())
        except ValueError:
            continue
        if rel not in path_map and not resolved.is_file():
            broken.append((text.count("\n", 0, m.start()) + 1, m.group(2)))
    return broken


def find_broken_doc_refs(text: str, source_rel: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, filename)`` for ``*.md`` names in code that don't exist.

    Scripts and examples cite skill references in docstrings and in the doc
    pointers their violation messages print, so renaming a reference silently
    leaves an agent-facing dead pointer that no Markdown link check would see.

    A ``.py`` under ``scripts/`` or ``examples/`` cites its *skill's* references,
    not siblings in its own directory, so both are accepted. Only file existence
    is checked, not ``#anchors`` — anchor slugs would need a slug algorithm
    matched to the docs renderer, and a mismatch there produces false positives
    on every heading containing an identifier.
    """
    broken: list[tuple[int, str]] = []
    candidates = (REPO_ROOT / source_rel.parent, REPO_ROOT / source_rel.parent.parent)
    for m in CODE_DOCREF_RE.finditer(text):
        name = m.group(1)
        if any((base / name).is_file() for base in candidates):
            continue
        broken.append((text.count("\n", 0, m.start()) + 1, name))
    return broken


def build_path_map(
    categories: dict[str, Category],
    standalones: dict[str, Standalone],
) -> dict[Path, Path]:
    """Map every source .md/.py path (relative to REPO_ROOT) to its docs path."""
    mapping: dict[Path, Path] = {}
    for cat in categories.values():
        for child in cat.children:
            src = child.source.relative_to(REPO_ROOT)
            if child.references or child.examples or child.scripts:
                mapping[src] = Path(cat.dirname) / child.slug / "index.md"
            else:
                mapping[src] = Path(cat.dirname) / f"{child.slug}.md"
            for ref in child.references:
                rsrc = ref.source.relative_to(REPO_ROOT)
                mapping[rsrc] = Path(cat.dirname) / child.slug / f"{ref.slug}.md"
            for code in (*child.examples, *child.scripts):
                csrc = code.source.relative_to(REPO_ROOT)
                mapping[csrc] = Path(cat.dirname) / child.slug / f"{code.slug}.md"
    for st in standalones.values():
        mapping[st.source.relative_to(REPO_ROOT)] = Path(f"{st.slug}.md")
    return mapping


def rewrite_internal_links(
    text: str,
    source_path: Path,
    path_map: dict[Path, Path],
) -> str:
    """Rewrite all internal ``.md`` links to use correct docs-relative paths.

    Resolves each link target against the source file's directory, looks up the
    corresponding docs path in *path_map*, and emits the correct relative link
    from the current file's docs location.
    """
    source_rel = source_path.relative_to(REPO_ROOT)
    source_dir = source_rel.parent
    docs_path = path_map.get(source_rel)
    if docs_path is None:
        return text
    docs_dir = docs_path.parent

    def _replace(m: re.Match) -> str:
        label, raw_target = m.group(1), m.group(2)

        # Split anchor fragment.
        if "#" in raw_target:
            path_part, anchor = raw_target.split("#", 1)
            anchor = "#" + anchor
        else:
            path_part, anchor = raw_target, ""

        # Only rewrite relative .md links.
        if not path_part.endswith(".md") or path_part.startswith("http"):
            return m.group(0)

        # Resolve against source directory.
        target_abs = (REPO_ROOT / source_dir / path_part).resolve()
        try:
            target_rel = target_abs.relative_to(REPO_ROOT.resolve())
        except ValueError:
            return m.group(0)

        target_docs = path_map.get(target_rel)
        if target_docs is None:
            return m.group(0)

        rel = Path(os.path.relpath(target_docs, docs_dir))
        return f"[{label}]({rel.as_posix()}{anchor})"

    return MD_LINK_RE.sub(_replace, text)


def inject_source_meta(text: str, source_rel: str) -> str:
    """Prepend a hidden element with the SKILL.md source path.

    The companion ``copy-markdown.js`` script reads this to construct the
    raw GitHub URL for the "Copy Markdown" button.
    """
    meta = f'<div data-skill-source="{source_rel}" ' f'style="display:none"></div>\n\n'
    return meta + text


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


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


def extract_version(text: str) -> str | None:
    """Return ``metadata.version`` from a SKILL.md's front matter, if present.

    Scoped to the leading front-matter block so an illustrative ``version:`` in
    the body (e.g. a code example) is never picked up.
    """
    fm = FRONT_MATTER_RE.match(text)
    block = fm.group(0) if fm else ""
    m = re.search(r'^\s+version:\s*["\']?([0-9][0-9.]*)["\']?\s*$', block, re.MULTILINE)
    return m.group(1) if m else None


def inject_version_note(text: str, version: str | None) -> str:
    """Insert an italic ``*Skill version X.Y.Z*`` line just after the first H1."""
    if not version:
        return text
    note = f"*Skill version {version}*"
    lines = text.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            lines[i + 1 : i + 1] = ["", note]
            return "\n".join(lines)
    return note + "\n\n" + text


def generate_example_md(example: Example, source_rel: str, screenshot_path: str | None) -> str:
    """Generate markdown content for a Python example or script."""
    lines = [f"# {example.title}", ""]
    if screenshot_path:
        lines.extend([f"![{example.title}]({screenshot_path})", ""])
    lines.extend(
        [
            "```python",
            example.code,
            "```",
            "",
        ]
    )
    meta = f'<div data-skill-source="{source_rel}" ' f'style="display:none"></div>\n\n'
    return meta + "\n".join(lines)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def find_skill_files(root: Path) -> list[Path]:
    """Find every SKILL.md under top-level dirs that aren't excluded."""
    skills: list[Path] = []
    for child in sorted(root.iterdir()):
        if (
            not child.is_dir()
            or child.name in EXCLUDE_DIRS
            or child.name.startswith(".")
            or child.name.startswith("_")
        ):
            continue
        skills.extend(sorted(child.rglob("SKILL.md")))
    return skills


def find_references(skill_md: Path) -> list[Path]:
    """Find sibling .md files alongside a SKILL.md (excluding SKILL.md itself)."""
    return sorted(p for p in skill_md.parent.glob("*.md") if p.name != "SKILL.md")


def find_examples(skill_md: Path) -> list[Path]:
    """Find .py files in an examples/ subdirectory alongside a SKILL.md."""
    examples_dir = skill_md.parent / "examples"
    if not examples_dir.is_dir():
        return []
    return sorted(examples_dir.glob("*.py"))


def find_scripts(skill_md: Path) -> list[Path]:
    """Find .py files in a scripts/ subdirectory alongside a SKILL.md.

    Skips ``test_*.py`` and dunder files: the tests document the scripts' own
    correctness, not how an agent uses them, and publishing them doubles the
    page count for no reader benefit.
    """
    scripts_dir = skill_md.parent / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(p for p in scripts_dir.glob("*.py") if not p.name.startswith(("test_", "_")))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class Example:
    """A Python file in an examples/ or scripts/ subdirectory."""

    def __init__(self, slug: str, title: str, source: Path, code: str):
        self.slug = slug
        self.title = title
        self.source = source
        self.code = code


class Reference:
    """A reference document alongside a sub-skill."""

    def __init__(
        self, slug: str, title: str, source: Path, cleaned: str, version: str | None = None
    ):
        self.slug = slug
        self.title = title
        self.source = source
        self.cleaned = cleaned
        self.version = version  # inherited from the owning sub-skill


class SubSkill:
    """A single sub-skill within a category."""

    def __init__(
        self, slug: str, title: str, source: Path, cleaned: str, version: str | None = None
    ):
        self.slug = slug
        self.title = title
        self.source = source
        self.cleaned = cleaned
        self.version = version
        self.references: list[Reference] = []
        self.examples: list[Example] = []
        self.scripts: list[Example] = []


class Category:
    """A top-level directory containing a routing SKILL.md and sub-skills."""

    def __init__(self, dirname: str, title: str, description: str, version: str | None = None):
        self.dirname = dirname
        self.title = title
        self.description = description
        self.version = version
        self.children: list[SubSkill] = []


class Standalone:
    """A top-level directory with only a single SKILL.md (no sub-skills)."""

    def __init__(
        self, slug: str, title: str, source: Path, cleaned: str, version: str | None = None
    ):
        self.slug = slug
        self.title = title
        self.source = source
        self.cleaned = cleaned
        self.version = version


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


def ordered_references(skill: SubSkill) -> list[Reference]:
    """Return *skill.references* in the preferred order."""
    explicit = REFERENCE_ORDER.get(skill.slug, [])
    rank = {slug: i for i, slug in enumerate(explicit)}
    fallback = len(explicit)
    return sorted(
        skill.references,
        key=lambda r: (rank.get(r.slug, fallback), r.title.lower()),
    )


def ordered_examples(skill: SubSkill) -> list[Example]:
    """Return *skill.examples* alphabetically by title."""
    return sorted(skill.examples, key=lambda e: e.title.lower())


def ordered_scripts(skill: SubSkill) -> list[Example]:
    """Return *skill.scripts* alphabetically by title."""
    return sorted(skill.scripts, key=lambda s: s.title.lower())


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
        if child.references or child.examples or child.scripts:
            lines.append(f"| [{child.title}]({child.slug}/index.md) | {desc} |")
        else:
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
                if child.references or child.examples or child.scripts:
                    # Nested sub-section for skill + references/examples/scripts.
                    lines.append(f'    {{ "{child.title}" = [')
                    lines.append(f'      "{section.dirname}/{child.slug}/index.md",')
                    for ref in ordered_references(child):
                        lines.append(
                            f'      {{ "{ref.title}" = '
                            f'"{section.dirname}/{child.slug}/{ref.slug}.md" }},'
                        )
                    examples = ordered_examples(child)
                    if examples:
                        # Group example pages under a single "Examples" node so
                        # they don't sit flat alongside the reference pages.
                        lines.append('      { "Examples" = [')
                        for ex in examples:
                            lines.append(
                                f'        {{ "{ex.title}" = '
                                f'"{section.dirname}/{child.slug}/{ex.slug}.md" }},'
                            )
                        lines.append("      ] },")
                    scripts = ordered_scripts(child)
                    if scripts:
                        # Same grouping for runnable tooling the agent invokes.
                        lines.append('      { "Scripts" = [')
                        for sc in scripts:
                            lines.append(
                                f'        {{ "{sc.title}" = '
                                f'"{section.dirname}/{child.slug}/{sc.slug}.md" }},'
                            )
                        lines.append("      ] },")
                    lines.append("    ] },")
                else:
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
# Screenshot generation
# ---------------------------------------------------------------------------


def generate_example_screenshots(examples: list[Example], skill_dir: Path) -> dict[str, str]:
    """Serve examples and capture screenshots using Playwright.

    Returns a mapping from example slug to the relative path of the screenshot
    (relative to the skill's docs directory).
    """
    if not examples:
        return {}

    # Check if playwright is available.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("build_stubs: playwright not installed — skipping screenshots")
        return {}

    # Collect .py files to serve.
    example_files = [ex.source for ex in examples]
    examples_dir = example_files[0].parent

    # Start panel server.
    cmd = [
        sys.executable,
        "-m",
        "panel",
        "serve",
        *[str(f) for f in example_files],
        "--port",
        "5099",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(examples_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for server to be ready (poll until connection succeeds).
    import socket

    for _ in range(30):  # up to 30 seconds
        time.sleep(1)
        try:
            with socket.create_connection(("localhost", 5099), timeout=1):
                break
        except (TimeoutError, ConnectionRefusedError, OSError):
            pass
    else:
        print("build_stubs: WARNING — panel server did not start in time")
        proc.terminate()
        return {}

    screenshots: dict[str, str] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 900})

            for ex in examples:
                url = f"http://localhost:5099/{ex.slug}"
                try:
                    page.goto(url, timeout=10000)
                    page.wait_for_timeout(3000)

                    # Save screenshot to docs/assets/examples/
                    screenshot_dir = ASSETS_DIR / "examples"
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_file = screenshot_dir / f"{ex.slug}.png"
                    page.screenshot(path=str(screenshot_file))

                    # Return path relative to skill docs dir
                    # (e.g., ../../assets/examples/dashboard.png)
                    rel_path = os.path.relpath(screenshot_file, skill_dir)
                    screenshots[ex.slug] = rel_path
                    print(f"build_stubs: screenshot {ex.slug}.png")
                except Exception as e:
                    print(f"build_stubs: WARNING — failed to screenshot {ex.slug}: {e}")

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    return screenshots


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

            cat = Category(tld, title, desc, extract_version(root_raw))

            for child_md in children:
                raw = child_md.read_text(encoding="utf-8")
                cleaned = strip_frontmatter_and_comments(raw)
                slug = child_md.parent.name
                child_title = extract_h1_title(cleaned) or slug_to_title(slug)
                child_version = extract_version(raw)

                # Discover sibling .md files (references) — they inherit the
                # owning sub-skill's version.
                ref_paths = find_references(child_md)
                refs: list[Reference] = []
                for ref_path in ref_paths:
                    ref_raw = ref_path.read_text(encoding="utf-8")
                    ref_cleaned = strip_frontmatter_and_comments(ref_raw)
                    ref_slug = ref_path.stem
                    ref_title = extract_h1_title(ref_cleaned) or slug_to_title(ref_slug)
                    refs.append(
                        Reference(ref_slug, ref_title, ref_path, ref_cleaned, child_version)
                    )

                # Discover .py files in examples/ and scripts/ subdirectories.
                example_paths = find_examples(child_md)
                examples: list[Example] = []
                for ex_path in example_paths:
                    ex_code = ex_path.read_text(encoding="utf-8")
                    ex_slug = ex_path.stem
                    ex_title = slug_to_title(ex_slug)
                    examples.append(Example(ex_slug, ex_title, ex_path, ex_code))

                script_paths = find_scripts(child_md)
                scripts: list[Example] = []
                for sc_path in script_paths:
                    sc_code = sc_path.read_text(encoding="utf-8")
                    sc_slug = sc_path.stem
                    sc_title = slug_to_title(sc_slug)
                    scripts.append(Example(sc_slug, sc_title, sc_path, sc_code))

                skill = SubSkill(slug, child_title, child_md, cleaned, child_version)
                skill.references = refs
                skill.examples = examples
                skill.scripts = scripts

                # References, examples and scripts all flatten into one docs
                # directory, so equal stems would silently overwrite a page.
                slugs = [r.slug for r in refs] + [c.slug for c in (*examples, *scripts)]
                dupes = {s for s in slugs if slugs.count(s) > 1}
                if dupes:
                    print(
                        f"build_stubs: WARNING — {slug} has colliding page names "
                        f"{sorted(dupes)}; rename one so both are published.",
                        file=sys.stderr,
                    )

                cat.children.append(skill)

            categories[tld] = cat
        elif roots:
            # Standalone skill.
            raw = roots[0].read_text(encoding="utf-8")
            cleaned = strip_frontmatter_and_comments(raw)
            title = extract_h1_title(cleaned) or slug_to_title(tld)
            standalones[tld] = Standalone(tld, title, roots[0], cleaned, extract_version(raw))

    # ---- Rewrite internal links ----
    path_map = build_path_map(categories, standalones)

    # ---- Warn about brackets the docs build can't resolve as links ----
    for src_rel in sorted(path_map):
        raw = (REPO_ROOT / src_rel).read_text(encoding="utf-8")
        if src_rel.suffix == ".py":
            for lineno, name in find_broken_doc_refs(raw, src_rel):
                print(
                    f"build_stubs: WARNING — {src_rel}:{lineno} — cites {name!r}, "
                    "which does not exist (renamed or deleted reference?).",
                    file=sys.stderr,
                )
            continue
        if src_rel.suffix != ".md":
            continue
        for lineno, inner in find_shortcut_links(raw):
            print(
                f"build_stubs: WARNING — {src_rel}:{lineno} — [{inner}] parses as a "
                "link reference; wrap it in backticks or escape the brackets.",
                file=sys.stderr,
            )
        for lineno, target in find_broken_links(raw, src_rel, path_map):
            print(
                f"build_stubs: WARNING — {src_rel}:{lineno} — link target "
                f"{target!r} does not exist.",
                file=sys.stderr,
            )

    for cat in categories.values():
        for child in cat.children:
            child.cleaned = rewrite_internal_links(
                child.cleaned,
                child.source,
                path_map,
            )
            for ref in child.references:
                ref.cleaned = rewrite_internal_links(
                    ref.cleaned,
                    ref.source,
                    path_map,
                )

    for st in standalones.values():
        st.cleaned = rewrite_internal_links(st.cleaned, st.source, path_map)

    # ---- Write output files ----
    page_count = 0

    for cat in categories.values():
        out_dir = DOCS_DIR / cat.dirname
        out_dir.mkdir(parents=True, exist_ok=True)

        # Section index page (docs-facing, not the routing skill).
        index_md = inject_source_meta(
            inject_version_note(generate_index_md(cat), cat.version), f"{cat.dirname}/SKILL.md"
        )
        (out_dir / "index.md").write_text(index_md, encoding="utf-8")
        print(f"build_stubs: {cat.dirname}/  ->  docs/{cat.dirname}/index.md")
        page_count += 1

        for child in cat.children:
            rel_src = child.source.relative_to(REPO_ROOT)

            if child.references or child.examples or child.scripts:
                # Nested directory: skill index + reference/example/script pages.
                skill_dir = out_dir / child.slug
                skill_dir.mkdir(parents=True, exist_ok=True)

                dest = skill_dir / "index.md"
                content = inject_source_meta(
                    inject_version_note(child.cleaned, child.version), str(rel_src)
                )
                dest.write_text(content, encoding="utf-8")
                print(f"build_stubs: {rel_src}  ->  docs/{cat.dirname}/{child.slug}/index.md")
                page_count += 1

                for ref in child.references:
                    ref_dest = skill_dir / f"{ref.slug}.md"
                    ref_rel_src = ref.source.relative_to(REPO_ROOT)
                    ref_content = inject_source_meta(
                        inject_version_note(ref.cleaned, ref.version), str(ref_rel_src)
                    )
                    ref_dest.write_text(ref_content, encoding="utf-8")
                    print(
                        f"build_stubs: {ref_rel_src}  ->  "
                        f"docs/{cat.dirname}/{child.slug}/{ref.slug}.md"
                    )
                    page_count += 1

                # Generate screenshots for examples.
                screenshots = generate_example_screenshots(child.examples, skill_dir)

                for ex in child.examples:
                    ex_dest = skill_dir / f"{ex.slug}.md"
                    ex_rel_src = ex.source.relative_to(REPO_ROOT)
                    screenshot_path = screenshots.get(ex.slug)
                    ex_content = generate_example_md(ex, str(ex_rel_src), screenshot_path)
                    ex_dest.write_text(ex_content, encoding="utf-8")
                    print(
                        f"build_stubs: {ex_rel_src}  ->  "
                        f"docs/{cat.dirname}/{child.slug}/{ex.slug}.md"
                    )
                    page_count += 1

                # Scripts get no screenshot — they're CLI tooling, not apps.
                for sc in child.scripts:
                    sc_dest = skill_dir / f"{sc.slug}.md"
                    sc_rel_src = sc.source.relative_to(REPO_ROOT)
                    sc_content = generate_example_md(sc, str(sc_rel_src), None)
                    sc_dest.write_text(sc_content, encoding="utf-8")
                    print(
                        f"build_stubs: {sc_rel_src}  ->  "
                        f"docs/{cat.dirname}/{child.slug}/{sc.slug}.md"
                    )
                    page_count += 1
            else:
                # Flat page (no references or examples).
                dest = out_dir / f"{child.slug}.md"
                content = inject_source_meta(
                    inject_version_note(child.cleaned, child.version), str(rel_src)
                )
                dest.write_text(content, encoding="utf-8")
                print(f"build_stubs: {rel_src}  ->  docs/{cat.dirname}/{child.slug}.md")
                page_count += 1

    for st in standalones.values():
        dest = DOCS_DIR / f"{st.slug}.md"
        rel_src = st.source.relative_to(REPO_ROOT)
        content = inject_source_meta(inject_version_note(st.cleaned, st.version), str(rel_src))
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
