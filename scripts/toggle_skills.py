#!/usr/bin/env python3
"""
Utility to toggle SKILL.md files on/off for evaluation purposes.

Disabling skills: renames AGENTS.md -> .AGENTS.md.disabled so the Copilot CLI
                  finds no custom instructions.
Enabling skills:  restores .AGENTS.md.disabled -> AGENTS.md.

SKILL.md files are also renamed to .SKILL.md.disabled when disabling, for
runtimes (e.g. OpenCode/Claude) that discover skills by that filename.
"""

from pathlib import Path

AGENTS_MD = "AGENTS.md"
AGENTS_MD_DISABLED = ".AGENTS.md.disabled"


def find_skill_files(root_dir: Path, enabled: bool = True) -> list[Path]:
    """
    Find all SKILL.md files (or .SKILL.md.disabled files) in the directory tree.

    Args:
        root_dir: Root directory to search from
        enabled: If True, search for SKILL.md files. If False, search for .SKILL.md.disabled

    Returns:
        List of Path objects for found files
    """
    pattern = "SKILL.md" if enabled else ".SKILL.md.disabled"

    exclude_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".cache",
        "site",
        "docs",
        ".venv",
        "venv",
        ".pixi",
    }

    skill_files = []
    for item in root_dir.rglob(pattern):
        if any(parent.name in exclude_dirs for parent in item.parents):
            continue
        if item.is_file():
            skill_files.append(item)

    return sorted(skill_files)


def disable_skills(root_dir: Path) -> list[tuple[Path, Path]]:
    """
    Disable skills for the without-skills eval condition:
    - Renames AGENTS.md -> .AGENTS.md.disabled (hides it from the Copilot CLI)
    - Renames SKILL.md -> .SKILL.md.disabled (hides from OpenCode/Claude runtimes)

    Args:
        root_dir: Root directory to search from

    Returns:
        List of (old_path, new_path) tuples for renamed SKILL.md files
    """
    # Disable AGENTS.md
    agents_md = root_dir / AGENTS_MD
    agents_md_disabled = root_dir / AGENTS_MD_DISABLED
    if agents_md.exists() and not agents_md_disabled.exists():
        agents_md.rename(agents_md_disabled)

    # Disable SKILL.md files
    renamed = []
    for skill_file in find_skill_files(root_dir, enabled=True):
        new_path = skill_file.parent / ".SKILL.md.disabled"
        if new_path.exists():
            continue
        skill_file.rename(new_path)
        renamed.append((skill_file, new_path))

    return renamed


def enable_skills(root_dir: Path) -> list[tuple[Path, Path]]:
    """
    Enable skills for the with-skills eval condition:
    - Restores .AGENTS.md.disabled -> AGENTS.md
    - Restores .SKILL.md.disabled -> SKILL.md

    Args:
        root_dir: Root directory to search from

    Returns:
        List of (old_path, new_path) tuples for restored SKILL.md files
    """
    # Restore AGENTS.md
    agents_md = root_dir / AGENTS_MD
    agents_md_disabled = root_dir / AGENTS_MD_DISABLED
    if agents_md_disabled.exists() and not agents_md.exists():
        agents_md_disabled.rename(agents_md)

    # Restore SKILL.md files
    renamed = []
    for disabled_file in find_skill_files(root_dir, enabled=False):
        new_path = disabled_file.parent / "SKILL.md"
        if new_path.exists():
            continue
        disabled_file.rename(new_path)
        renamed.append((disabled_file, new_path))

    return renamed


def get_skill_status(root_dir: Path) -> dict:
    """
    Get the current status of skill files.

    Returns:
        Dictionary with 'enabled' and 'disabled' lists of paths, and AGENTS.md state
    """
    enabled = find_skill_files(root_dir, enabled=True)
    disabled = find_skill_files(root_dir, enabled=False)
    agents_md_present = (root_dir / AGENTS_MD).exists()

    return {
        "enabled": enabled,
        "disabled": disabled,
        "total": len(enabled) + len(disabled),
        "agents_md": agents_md_present,
    }


def main():
    """Command-line interface for toggling skills."""
    import argparse

    parser = argparse.ArgumentParser(description="Toggle SKILL.md files for evaluation")
    parser.add_argument("action", choices=["disable", "enable", "status"], help="Action to perform")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd().parent if Path.cwd().name == "scripts" else Path.cwd(),
        help="Root directory to search (default: parent of current dir if in scripts/)",
    )

    args = parser.parse_args()

    if args.action == "disable":
        print(f"Disabling skills in {args.root}...")
        renamed = disable_skills(args.root)
        print(f"Disabled {len(renamed)} SKILL.md file(s) + AGENTS.md")
    elif args.action == "enable":
        print(f"Enabling skills in {args.root}...")
        renamed = enable_skills(args.root)
        print(f"Enabled {len(renamed)} SKILL.md file(s) + AGENTS.md")
    elif args.action == "status":
        status = get_skill_status(args.root)
        print(f"\nSkill Status in {args.root}:")
        print(f"  AGENTS.md: {'present' if status['agents_md'] else 'absent (disabled)'}")
        print(f"  SKILL.md enabled:  {len(status['enabled'])} file(s)")
        for path in status["enabled"]:
            print(f"    - {path.relative_to(args.root)}")
        print(f"  SKILL.md disabled: {len(status['disabled'])} file(s)")
        for path in status["disabled"]:
            print(f"    - {path.relative_to(args.root)}")


if __name__ == "__main__":
    main()
