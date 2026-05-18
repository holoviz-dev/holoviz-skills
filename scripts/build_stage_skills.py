"""Stage top-level skill directories into the package for building.

The skill content (developing-with-holoviz/, contributing-to-holoviz/, etc.)
lives at the repo root for a friendly contributor experience, but must be
copied into ``holoviz_skills/skills/`` so that ``pip install`` bundles them
as package data and the CLI can locate them at runtime.

Usage::

    python scripts/build_stage_skills.py   # copy skills into holoviz_skills/skills/
    python scripts/build_stage_skills.py --clean  # remove the staged directory
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGED_SKILLS = REPO_ROOT / "holoviz_skills" / "skills"


def _find_skill_dirs() -> list[Path]:
    """Return top-level directories that contain a SKILL.md."""
    return sorted(
        d
        for d in REPO_ROOT.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and not d.name.startswith("_")
        and d.name != "holoviz_skills"
        and (d / "SKILL.md").exists()
    )


def stage() -> None:
    """Copy skill directories into holoviz_skills/skills/."""
    if STAGED_SKILLS.exists():
        shutil.rmtree(STAGED_SKILLS)
    STAGED_SKILLS.mkdir(parents=True)

    for skill_dir in _find_skill_dirs():
        shutil.copytree(
            skill_dir,
            STAGED_SKILLS / skill_dir.name,
            ignore=shutil.ignore_patterns(
                ".DS_Store",
                ".gitkeep",
                "__pycache__",
            ),
        )
        print(f"  + {skill_dir.name}/")

    print(f"\nStaged {len(_find_skill_dirs())} skill(s) into {STAGED_SKILLS}")


def clean() -> None:
    """Remove the staged skills directory."""
    if STAGED_SKILLS.exists():
        shutil.rmtree(STAGED_SKILLS)
        print(f"Removed {STAGED_SKILLS}")
    else:
        print("Nothing to clean")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Remove staged skills")
    args = parser.parse_args()

    if args.clean:
        clean()
    else:
        stage()
