#!/usr/bin/env python3
"""
Utility to toggle SKILL.md files on/off for evaluation purposes.

Disabling skills: SKILL.md -> .SKILL.md.disabled
Enabling skills: .SKILL.md.disabled -> SKILL.md
"""

from pathlib import Path


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

    # Exclude certain directories
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
        # Skip if any parent directory is in exclude list
        if any(parent.name in exclude_dirs for parent in item.parents):
            continue
        if item.is_file():
            skill_files.append(item)

    return sorted(skill_files)


def disable_skills(root_dir: Path) -> list[tuple[Path, Path]]:
    """
    Disable all SKILL.md files by renaming them to .SKILL.md.disabled

    Args:
        root_dir: Root directory to search from

    Returns:
        List of (old_path, new_path) tuples for renamed files
    """
    skill_files = find_skill_files(root_dir, enabled=True)
    renamed = []

    for skill_file in skill_files:
        new_path = skill_file.parent / ".SKILL.md.disabled"
        if new_path.exists():
            continue
        skill_file.rename(new_path)
        renamed.append((skill_file, new_path))

    return renamed


def enable_skills(root_dir: Path) -> list[tuple[Path, Path]]:
    """
    Enable all disabled skill files by renaming them back to SKILL.md

    Args:
        root_dir: Root directory to search from

    Returns:
        List of (old_path, new_path) tuples for renamed files
    """
    disabled_files = find_skill_files(root_dir, enabled=False)
    renamed = []

    for disabled_file in disabled_files:
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
        Dictionary with 'enabled' and 'disabled' lists of paths
    """
    enabled = find_skill_files(root_dir, enabled=True)
    disabled = find_skill_files(root_dir, enabled=False)

    return {"enabled": enabled, "disabled": disabled, "total": len(enabled) + len(disabled)}


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
        print(f"Disabling SKILL.md files in {args.root}...")
        renamed = disable_skills(args.root)
        print(f"\nDisabled {len(renamed)} skill file(s)")
    elif args.action == "enable":
        print(f"Enabling SKILL.md files in {args.root}...")
        renamed = enable_skills(args.root)
        print(f"\nEnabled {len(renamed)} skill file(s)")
    elif args.action == "status":
        status = get_skill_status(args.root)
        print(f"\nSkill Status in {args.root}:")
        print(f"  Enabled:  {len(status['enabled'])} file(s)")
        for path in status["enabled"]:
            print(f"    - {path.relative_to(args.root)}")
        print(f"  Disabled: {len(status['disabled'])} file(s)")
        for path in status["disabled"]:
            print(f"    - {path.relative_to(args.root)}")
        print(f"  Total:    {status['total']} skill file(s)")


if __name__ == "__main__":
    main()
