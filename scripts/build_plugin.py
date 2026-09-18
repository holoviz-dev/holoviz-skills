"""Build Claude Cowork plugins and per-skill zip archives.

Outputs are written flat to ``artifacts/`` so they can be uploaded directly
as GitHub release assets (which cannot be nested in folders):

* ``<category>.plugin``            — one Claude Desktop / Cowork plugin per
  top-level category (e.g. ``developing-with-holoviz.plugin``)
* ``holoviz-skills.plugin``        — every category in one plugin
* ``holoviz-skills.zip``           — all skills together, any tool
* ``<category>.zip``               — one zip per top-level category
  (e.g. ``developing-with-holoviz.zip``)
* ``<category>-<sub-skill>.zip``   — one zip per sub-skill, prefixed with its
  category to keep names unique when flattened
  (e.g. ``developing-with-holoviz-hvplot.zip``)

Run directly::

    python scripts/build_plugin.py

Or via pixi::

    pixi run build-plugin

Pass ``--stage`` to auto-stage every output file with ``git add`` (used by
the pre-commit hook).

This script is deliberately stdlib-only so it runs without any extra
dependencies, matching the convention established by ``build_stubs.py``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
# Name shared by the all-skills zip and the all-categories plugin.
PLUGIN_NAME = "holoviz-skills"

# Sub-skill directory name (one level below a category SKILL.md).
SUBSKILLS_DIRNAME = "skills"

# Shared manifest fields; ``name``, ``description``, and ``version`` are filled
# in per category. ``version`` here is only a fallback when a SKILL.md has none.
PLUGIN_JSON_BASE: dict = {
    "version": "0.1.0",
    "author": {"name": "HoloViz"},
    "homepage": "https://holoviz-dev.github.io/holoviz-skills/",
    "repository": "https://github.com/holoviz-dev/holoviz-skills",
    "license": "BSD",
    "keywords": ["holoviz", "panel", "hvplot", "holoviews", "param", "dataviz"],
}


def _read_description(skill_md: Path) -> str | None:
    """Return the YAML ``description:`` value from a SKILL.md, if present."""
    if not skill_md.exists():
        return None
    m = re.search(r"^description:\s*(.+)$", skill_md.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else None


def _read_version(skill_md: Path) -> str | None:
    """Return ``metadata.version`` from a SKILL.md's front matter, if present."""
    if not skill_md.exists():
        return None
    fm = re.match(r"\A---\s*\n.*?\n---\s*\n", skill_md.read_text(encoding="utf-8"), re.DOTALL)
    block = fm.group(0) if fm else ""
    m = re.search(r'^\s+version:\s*["\']?([0-9][0-9.]*)["\']?\s*$', block, re.MULTILINE)
    return m.group(1) if m else None


def _repo_version() -> str | None:
    """Return the latest git tag as a bare version, e.g. ``v0.1.0`` -> ``0.1.0``.

    The all-categories plugin spans every skill, so there is no single SKILL.md
    to read a version from and the release tag is the only meaningful version
    for it. Best-effort: returns None outside a git checkout or before the first
    tag, leaving the ``PLUGIN_JSON_BASE`` fallback in place.
    """
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip().lstrip("v") or None


def _plugin_manifest(category_dir: Path) -> dict:
    """Build the plugin.json manifest for a single category."""
    name = category_dir.name
    skill_md = category_dir / "SKILL.md"
    description = _read_description(skill_md) or f"HoloViz skills for {name.replace('-', ' ')}."
    version = _read_version(skill_md)
    manifest = {"name": name, "description": description, **PLUGIN_JSON_BASE}
    if version:
        manifest["version"] = version  # override the fallback with the real skill version
    return manifest


def _combined_manifest(category_dirs: list[Path]) -> dict:
    """Build the plugin.json manifest for the all-categories plugin.

    The category list is rendered into the description rather than hard-coded so
    a newly added category appears without editing this script.
    """
    categories = ", ".join(d.name for d in category_dirs)
    manifest = {
        "name": PLUGIN_NAME,
        "description": (
            "Every HoloViz Agent Skill in one plugin — Panel, hvPlot, HoloViews, Param, and "
            f"more. Bundles {categories}."
        ),
        **PLUGIN_JSON_BASE,
    }
    version = _repo_version()
    if version:
        manifest["version"] = version
    return manifest


# Names to omit from every output archive.
EXCLUDE_NAMES: set[str] = {".DS_Store", ".gitkeep", "__pycache__"}
EXCLUDE_DIRS: set[str] = {".git", ".pixi", "__pycache__"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_skill_dirs(root: Path) -> list[Path]:
    """Return top-level directories that contain a SKILL.md, sorted by name."""
    return sorted(
        d
        for d in root.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and not d.name.startswith("_")
        and (d / "SKILL.md").exists()
    )


def find_sub_skill_dirs(category_dir: Path) -> list[Path]:
    """Return sub-skill directories inside a category (category/skills/*/SKILL.md)."""
    sub_root = category_dir / SUBSKILLS_DIRNAME
    if not sub_root.is_dir():
        return []
    return sorted(d for d in sub_root.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


def _ignore(directory: str, names: list[str]) -> list[str]:
    """shutil.copytree ignore callback — skip unwanted files/dirs."""
    return [n for n in names if n in EXCLUDE_NAMES]


def _should_skip(path: Path) -> bool:
    """Return True if *path* should be omitted from any output archive."""
    return path.name in EXCLUDE_NAMES or (path.is_dir() and path.name in EXCLUDE_DIRS)


def _write_zip(source_dir: Path, archive_root: str, output: Path) -> None:
    """Zip *source_dir* into *output*, storing paths under *archive_root*.

    Writes to a temp file in /tmp/ first so the output is never partially written.
    """
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        tmp = Path(f.name)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(source_dir.rglob("*")):
                if _should_skip(path):
                    continue
                arcname = archive_root + "/" + str(path.relative_to(source_dir))
                zf.write(path, arcname)
        shutil.copy2(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)


def _write_zip_multi(source_dirs: list[Path], output: Path) -> None:
    """Zip multiple *source_dirs* into one *output*, each rooted at its own name."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        tmp = Path(f.name)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for source_dir in source_dirs:
                for path in sorted(source_dir.rglob("*")):
                    if _should_skip(path):
                        continue
                    arcname = source_dir.name + "/" + str(path.relative_to(source_dir))
                    zf.write(path, arcname)
        shutil.copy2(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)


def _git_stage(path: Path) -> None:
    """Stage *path* with ``git add`` (best-effort; silently skipped outside a repo)."""
    try:
        subprocess.run(
            ["git", "add", str(path)],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


# ---------------------------------------------------------------------------
# Plugin build
# ---------------------------------------------------------------------------


def _write_plugin(output: Path, manifest: dict, category_dirs: list[Path]) -> None:
    """Zip a ``.claude-plugin/plugin.json`` + ``skills/<category>/`` tree into *output*.

    Assembled in a temp dir and copied into place so *output* is never partially
    written. Shared by the per-category and all-categories builds — the only
    difference between them is how many *category_dirs* are passed.
    """
    with tempfile.TemporaryDirectory() as _tmp:
        tmp_dir = Path(_tmp)

        manifest_dir = tmp_dir / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        # Each category, with its nested sub-skills, under skills/.
        skills_out = tmp_dir / "skills"
        skills_out.mkdir()
        for cat_dir in category_dirs:
            shutil.copytree(cat_dir, skills_out / cat_dir.name, ignore=_ignore)

        tmp_zip = tmp_dir / output.name
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(tmp_dir.rglob("*")):
                if _should_skip(path) or path == tmp_zip:
                    continue
                zf.write(path, path.relative_to(tmp_dir))
        shutil.copy2(tmp_zip, output)


def build_plugin(stage: bool = False) -> list[Path]:
    """Build one ``artifacts/<category>.plugin`` per category, plus a combined one.

    Each per-category plugin bundles a single category (its routing SKILL.md plus
    any nested sub-skills) for Claude Desktop / Cowork. ``holoviz-skills.plugin``
    bundles every category, for installing the whole collection at once.

    Returns the list of output paths written.
    """
    skill_dirs = find_skill_dirs(REPO_ROOT)
    if not skill_dirs:
        print("build_plugin: no skill directories found — nothing to build.", file=sys.stderr)
        return []

    names = [d.name for d in skill_dirs]
    print(f"build_plugin: packaging {len(skill_dirs) + 1} plugin(s): {names} + {PLUGIN_NAME}")

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    builds = [(ARTIFACTS_DIR / f"{d.name}.plugin", _plugin_manifest(d), [d]) for d in skill_dirs]
    builds.append(
        (ARTIFACTS_DIR / f"{PLUGIN_NAME}.plugin", _combined_manifest(skill_dirs), skill_dirs)
    )

    outputs: list[Path] = []
    for output, manifest, category_dirs in builds:
        _write_plugin(output, manifest, category_dirs)
        size_kb = output.stat().st_size // 1024
        print(f"build_plugin: wrote {output.relative_to(REPO_ROOT)}  ({size_kb} KB)")
        outputs.append(output)
        if stage:
            _git_stage(output)

    if stage:
        print(f"build_plugin: staged {len(outputs)} plugin(s)")

    return outputs


# ---------------------------------------------------------------------------
# Zip builds
# ---------------------------------------------------------------------------


def build_zips(stage: bool = False) -> list[Path]:
    """Build per-skill and per-category zip archives into ``artifacts/``.

    All archives are written flat so they can be uploaded directly as GitHub
    release assets (which cannot be nested in folders). Sub-skill zips are
    prefixed with their category to keep filenames unique::

        artifacts/
          holoviz-skills.zip                   ← all skills, any tool
          <category>.zip                       ← whole category
          <category>-<sub-skill>.zip           ← individual sub-skill

    The folder *inside* each archive is still named after the skill itself
    (e.g. ``hvplot/``), so only the output filename carries the prefix.

    Returns the list of output paths written.
    """
    skill_dirs = find_skill_dirs(REPO_ROOT)
    if not skill_dirs:
        print("build_zips: no skill directories found.", file=sys.stderr)
        return []

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    outputs: list[Path] = []

    for cat_dir in skill_dirs:
        sub_dirs = find_sub_skill_dirs(cat_dir)

        # Category-level zip.
        cat_zip = ARTIFACTS_DIR / f"{cat_dir.name}.zip"
        _write_zip(cat_dir, cat_dir.name, cat_zip)
        size_kb = cat_zip.stat().st_size // 1024
        print(f"build_zips:   {cat_zip.relative_to(REPO_ROOT)}  ({size_kb} KB)")
        outputs.append(cat_zip)

        # Per-sub-skill zips, prefixed with the category name.
        for sub_dir in sub_dirs:
            sub_zip = ARTIFACTS_DIR / f"{cat_dir.name}-{sub_dir.name}.zip"
            _write_zip(sub_dir, sub_dir.name, sub_zip)
            size_kb = sub_zip.stat().st_size // 1024
            print(f"build_zips:     {sub_zip.relative_to(REPO_ROOT)}  ({size_kb} KB)")
            outputs.append(sub_zip)

    # All-skills zip: every category together, no plugin manifest.
    # This is the generic download for any AI tool (not Claude-specific).
    all_zip = ARTIFACTS_DIR / f"{PLUGIN_NAME}.zip"
    _write_zip_multi(skill_dirs, all_zip)

    size_kb = all_zip.stat().st_size // 1024
    print(f"build_zips:   {all_zip.relative_to(REPO_ROOT)}  ({size_kb} KB)  [all skills]")
    outputs.append(all_zip)

    if stage:
        for out in outputs:
            _git_stage(out)
        print(f"build_zips: staged {len(outputs)} file(s)")

    return outputs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(stage: bool = False) -> int:
    plugin_out = build_plugin(stage=stage)
    zip_out = build_zips(stage=stage)
    total = len(plugin_out) + len(zip_out)
    print(f"\nbuild_plugin: done — {total} file(s) written to artifacts/")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    stage = "--stage" in sys.argv
    sys.exit(main(stage=stage))
