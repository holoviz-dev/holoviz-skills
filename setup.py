"""Custom build step: stage top-level skill directories into the package.

The skill content (developing-with-holoviz/, contributing-to-holoviz/, etc.)
lives at the repo root for a friendly contributor experience, but must be
copied into ``holoviz_skills/skills/`` so that ``pip install`` bundles them
as package data and the CLI can locate them at runtime.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

REPO_ROOT = Path(__file__).parent
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


def _stage_skills() -> None:
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


class build_py(_build_py):
    def run(self) -> None:
        _stage_skills()
        super().run()


setup(cmdclass={"build_py": build_py})
