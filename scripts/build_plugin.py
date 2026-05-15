"""Build the Claude Cowork plugin and per-skill zip archives.

Outputs written to ``assets/``:

* ``holoviz-skills.plugin``  — all skills bundled for Claude Desktop / Cowork
* ``<skill>.zip``            — one zip per sub-skill (e.g. ``hvplot.zip``)
* ``<category>.zip``         — one zip per top-level category
  (e.g. ``developing-with-holoviz.zip``)

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
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "assets"
PLUGIN_NAME = "holoviz-skills"
PLUGIN_OUTPUT = ASSETS_DIR / f"{PLUGIN_NAME}.plugin"

# Sub-skill directory name (one level below a category SKILL.md).
SUBSKILLS_DIRNAME = "skills"

PLUGIN_JSON: dict = {
    "name": PLUGIN_NAME,
    "version": "0.1.0",
    "description": (
        "A curated collection of skills for the HoloViz ecosystem — "
        "Panel, hvPlot, HoloViews, Param, and more."
    ),
    "author": {"name": "HoloViz"},
    "homepage": "https://holoviz-dev.github.io/holoviz-skills/",
    "repository": "https://github.com/holoviz-dev/holoviz-skills",
    "license": "BSD",
    "keywords": ["holoviz", "panel", "hvplot", "holoviews", "param", "dataviz"],
}

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


def build_plugin(stage: bool = False) -> list[Path]:
    """Package all skill dirs into ``assets/holoviz-skills.plugin``.

    Returns the list of output paths written.
    """
    skill_dirs = find_skill_dirs(REPO_ROOT)
    if not skill_dirs:
        print("build_plugin: no skill directories found — nothing to build.", file=sys.stderr)
        return []

    print(f"build_plugin: packaging {len(skill_dirs)} skill(s): {[d.name for d in skill_dirs]}")

    with tempfile.TemporaryDirectory() as _tmp:
        tmp_dir = Path(_tmp)

        # Manifest.
        manifest_dir = tmp_dir / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps(PLUGIN_JSON, indent=2) + "\n", encoding="utf-8"
        )

        # Skills.
        skills_out = tmp_dir / "skills"
        skills_out.mkdir()
        for skill_dir in skill_dirs:
            shutil.copytree(skill_dir, skills_out / skill_dir.name, ignore=_ignore)
            print(f"build_plugin:   + {skill_dir.name}/")

        # Write plugin zip then move into place atomically.
        ASSETS_DIR.mkdir(exist_ok=True)
        tmp_zip = Path(_tmp) / f"{PLUGIN_NAME}.plugin"
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(tmp_dir.rglob("*")):
                if _should_skip(path) or path == tmp_zip:
                    continue
                zf.write(path, path.relative_to(tmp_dir))
        shutil.copy2(tmp_zip, PLUGIN_OUTPUT)

    size_kb = PLUGIN_OUTPUT.stat().st_size // 1024
    print(f"build_plugin: wrote {PLUGIN_OUTPUT.relative_to(REPO_ROOT)}  ({size_kb} KB)")

    outputs = [PLUGIN_OUTPUT]
    if stage:
        _git_stage(PLUGIN_OUTPUT)
        print(f"build_plugin: staged {PLUGIN_OUTPUT.relative_to(REPO_ROOT)}")

    return outputs


# ---------------------------------------------------------------------------
# Zip builds
# ---------------------------------------------------------------------------


def build_zips(stage: bool = False) -> list[Path]:
    """Build per-skill and per-category zip archives into ``assets/``.

    Layout mirrors the repo structure::

        assets/
          holoviz-skills.zip                   ← all skills, any tool
          <category>/
            <category>.zip                     ← whole category
            <sub-skill>.zip                    ← individual sub-skill

    Returns the list of output paths written.
    """
    skill_dirs = find_skill_dirs(REPO_ROOT)
    if not skill_dirs:
        print("build_zips: no skill directories found.", file=sys.stderr)
        return []

    ASSETS_DIR.mkdir(exist_ok=True)
    outputs: list[Path] = []

    for cat_dir in skill_dirs:
        sub_dirs = find_sub_skill_dirs(cat_dir)
        cat_assets = ASSETS_DIR / cat_dir.name
        cat_assets.mkdir(exist_ok=True)

        # Category-level zip.
        cat_zip = cat_assets / f"{cat_dir.name}.zip"
        _write_zip(cat_dir, cat_dir.name, cat_zip)
        size_kb = cat_zip.stat().st_size // 1024
        print(f"build_zips:   {cat_zip.relative_to(REPO_ROOT)}  ({size_kb} KB)")
        outputs.append(cat_zip)

        # Per-sub-skill zips.
        for sub_dir in sub_dirs:
            sub_zip = cat_assets / f"{sub_dir.name}.zip"
            _write_zip(sub_dir, sub_dir.name, sub_zip)
            size_kb = sub_zip.stat().st_size // 1024
            print(f"build_zips:     {sub_zip.relative_to(REPO_ROOT)}  ({size_kb} KB)")
            outputs.append(sub_zip)

    # All-skills zip: every category together, no plugin manifest.
    # This is the generic download for any AI tool (not Claude-specific).
    all_zip = ASSETS_DIR / f"{PLUGIN_NAME}.zip"
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
    print(f"\nbuild_plugin: done — {total} file(s) written to assets/")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    stage = "--stage" in sys.argv
    sys.exit(main(stage=stage))
