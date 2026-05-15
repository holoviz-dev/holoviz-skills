"""CLI for installing HoloViz Agent Skills into AI coding tools.

Usage::

    holoviz-skills install                # auto-detect all tools
    holoviz-skills install --claude-code  # ~/.claude/skills/
    holoviz-skills install --copilot      # .github/instructions/
    holoviz-skills install --cursor       # .cursor/rules/
    holoviz-skills install --windsurf     # .windsurf/skills/
    holoviz-skills install --cline        # .cline/skills/
    holoviz-skills install --continue     # .continue/rules/
    holoviz-skills install --gemini-cli   # .gemini/skills/
    holoviz-skills list                   # show what's installed where
    holoviz-skills uninstall --claude-code
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def _skills_root() -> Path:
    """Locate the skill directories, whether installed or running from source."""
    # Installed package: skills bundled inside the package as data.
    pkg_skills = Path(__file__).parent / "skills"
    if pkg_skills.is_dir():
        return pkg_skills
    # Development / editable install: skills live at the repo root.
    repo_root = Path(__file__).parent.parent
    if (repo_root / "developing-with-holoviz" / "SKILL.md").exists():
        return repo_root
    raise RuntimeError(
        "Cannot locate HoloViz skill files. "
        "Re-install the package or run from the repository root."
    )


def _find_skill_dirs(root: Path) -> list[Path]:
    """Return top-level skill directories (contain a SKILL.md)."""
    return sorted(
        d
        for d in root.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and not d.name.startswith("_")
        and (d / "SKILL.md").exists()
    )


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1).lstrip()


def _read_skill(skill_md: Path) -> str:
    return _strip_frontmatter(skill_md.read_text(encoding="utf-8"))


def _iter_flat_units(skill_dir: Path) -> list[tuple[str, str]]:
    """Yield (output-stem, content) for every installable unit in a top-level skill.

    Rules:
    - If the skill has sub-skills (a ``skills/`` subdirectory), recurse into
      each sub-skill; skip the top-level routing SKILL.md entirely (it only
      instructs agents to read sub-files on demand, which is meaningless for
      flat-file tools).
    - Each leaf skill produces one unit: its SKILL.md body only (no references
      concatenated in, so the main file stays small).
    - Each reference ``.md`` file inside a leaf skill directory (at any depth,
      but not inside a nested ``skills/`` dir) produces its own unit named
      ``{category}-{sub-skill}-{stem}`` so agents can selectively apply them.
    """
    results: list[tuple[str, str]] = []

    def _walk(prefix: str, directory: Path) -> None:
        skill_md = directory / "SKILL.md"
        if not skill_md.exists():
            return
        # Emit the leaf SKILL.md as the primary unit.
        results.append((prefix, _read_skill(skill_md)))
        # Emit each direct-child reference .md file as its own unit.
        # We intentionally use glob("*.md") — not rglob — so that subdirectories
        # like references/ (which mirror top-level files for Claude Code routing)
        # are excluded and don't produce duplicates.
        for ref in sorted(directory.glob("*.md")):
            if ref.name == "SKILL.md":
                continue
            results.append((f"{prefix}-{ref.stem}", _read_skill(ref)))

    sub_root = skill_dir / "skills"
    if sub_root.is_dir():
        for sub in sorted(sub_root.iterdir()):
            if sub.is_dir() and (sub / "SKILL.md").exists():
                _walk(f"{skill_dir.name}-{sub.name}", sub)
    else:
        _walk(skill_dir.name, skill_dir)

    return results


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


class Tool:
    """Represents one AI coding tool and how to install skills into it."""

    def __init__(
        self,
        key: str,
        name: str,
        scope: str,  # "global" or "project"
        install_path: Path,
        detect_fn,
        install_fn,
    ):
        self.key = key
        self.name = name
        self.scope = scope
        self.install_path = install_path
        self.detect_fn = detect_fn
        self.install_fn = install_fn

    def detected(self) -> bool:
        try:
            return bool(self.detect_fn())
        except Exception:
            return False

    def is_installed(self) -> bool:
        return self.install_path.exists() and any(self.install_path.iterdir())

    def install(self, skill_dirs: list[Path], verbose: bool = True) -> int:
        return self.install_fn(skill_dirs, self.install_path, verbose)

    def uninstall(self, verbose: bool = True) -> int:
        if not self.install_path.exists():
            print(f"  {self.name}: nothing to remove")
            return 0
        shutil.rmtree(self.install_path)
        if verbose:
            print(f"  {self.name}: removed {self.install_path}")
        return 1


# ---- Install strategies ----


def _install_dirs(skill_dirs: list[Path], dest: Path, verbose: bool) -> int:
    """Copy full skill directory trees (Claude Code style)."""
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for skill_dir in skill_dirs:
        target = dest / skill_dir.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            skill_dir,
            target,
            ignore=shutil.ignore_patterns(".DS_Store", ".gitkeep", "__pycache__"),
        )
        if verbose:
            print(f"    + {skill_dir.name}/")
        count += 1
    return count


def _install_flat_files(ext: str, frontmatter: str = ""):
    """Factory: write one focused flat file per leaf skill unit.

    Top-level routing skills are expanded into one file per sub-skill;
    reference ``.md`` files inside a sub-skill each get their own output file.
    The top-level routing SKILL.md is skipped (it only tells agents to read
    sub-files on demand, which is meaningless for flat-file tools).

    ``frontmatter`` is optional YAML front-matter (including ``---`` delimiters)
    prepended to every output file, e.g. an ``applyTo`` field for Copilot.
    """

    def _install(skill_dirs: list[Path], dest: Path, verbose: bool) -> int:
        dest.mkdir(parents=True, exist_ok=True)
        count = 0
        for skill_dir in skill_dirs:
            for stem, content in _iter_flat_units(skill_dir):
                if frontmatter:
                    content = frontmatter + "\n\n" + content
                out = dest / f"{stem}.{ext}"
                out.write_text(content, encoding="utf-8")
                if verbose:
                    print(f"    + {out.name}")
                count += 1
        return count

    return _install


def _make_tools() -> dict[str, Tool]:
    home = Path.home()
    cwd = Path.cwd()

    tools: list[Tool] = [
        Tool(
            key="claude-code",
            name="Claude Code / Cowork",
            scope="global",
            install_path=home / ".claude" / "skills",
            detect_fn=lambda: shutil.which("claude") or (home / ".claude").exists(),
            install_fn=_install_dirs,
        ),
        Tool(
            key="copilot",
            name="GitHub Copilot",
            scope="project",
            install_path=cwd / ".github" / "instructions",
            detect_fn=lambda: shutil.which("code") or (cwd / ".github").exists(),
            install_fn=_install_flat_files("instructions.md"),
        ),
        Tool(
            key="cursor",
            name="Cursor",
            scope="project",
            install_path=cwd / ".cursor" / "rules",
            detect_fn=lambda: shutil.which("cursor") or (cwd / ".cursor").exists(),
            install_fn=_install_flat_files("mdc"),
        ),
        Tool(
            key="windsurf",
            name="Windsurf",
            scope="project",
            install_path=cwd / ".windsurf" / "skills",
            detect_fn=lambda: shutil.which("windsurf") or (cwd / ".windsurf").exists(),
            install_fn=_install_dirs,
        ),
        Tool(
            key="cline",
            name="Cline",
            scope="project",
            install_path=cwd / ".cline" / "skills",
            detect_fn=lambda: (cwd / ".cline").exists(),
            install_fn=_install_dirs,
        ),
        Tool(
            key="continue",
            name="Continue",
            scope="project",
            install_path=cwd / ".continue" / "rules",
            detect_fn=lambda: (cwd / ".continue").exists(),
            install_fn=_install_flat_files("md"),
        ),
        Tool(
            key="gemini-cli",
            name="Gemini CLI",
            scope="project",
            install_path=cwd / ".gemini" / "skills",
            detect_fn=lambda: shutil.which("gemini") or (cwd / ".gemini").exists(),
            install_fn=_install_dirs,
        ),
    ]
    return {t.key: t for t in tools}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# argparse cannot use 'continue' as an attribute name (Python keyword), so
# that flag is stored as 'continue_'.  Map all tool keys to their actual attr.
_KEY_TO_ATTR: dict[str, str] = {"continue": "continue_"}


def _key_attr(key: str) -> str:
    """Return the argparse Namespace attribute name for a tool key."""
    return _KEY_TO_ATTR.get(key, key.replace("-", "_"))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_install(args: argparse.Namespace) -> int:
    tools = _make_tools()
    skill_dirs = _find_skill_dirs(_skills_root())

    # Which tools to install for.
    requested = [key for key in tools if getattr(args, _key_attr(key), False)]
    if not requested:
        # Auto-detect.
        requested = [key for key, tool in tools.items() if tool.detected()]
        if not requested:
            print("No supported AI tools detected. Run with a specific flag:")
            for key, tool in tools.items():
                scope = "(project)" if tool.scope == "project" else "(global)"
                print(f"  --{key:20s}  {tool.name} {scope}")
            return 1
        print(f"Detected: {', '.join(tools[k].name for k in requested)}\n")

    total = 0
    for key in requested:
        tool = tools[key]
        scope = (
            f"(project: {tool.install_path})"
            if tool.scope == "project"
            else f"(global: {tool.install_path})"
        )
        print(f"Installing into {tool.name} {scope}")
        count = tool.install(skill_dirs)
        print(f"  → {count} skill(s) installed\n")
        total += count

    print(f"Done — {total} installation(s) complete.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    tools = _make_tools()
    skill_dirs = _find_skill_dirs(_skills_root())

    print(f"Available skills ({len(skill_dirs)}): {', '.join(d.name for d in skill_dirs)}\n")
    print("Installations:")

    any_found = False
    for tool in tools.values():
        detected = "✓ detected" if tool.detected() else "  not detected"
        scope = f"project ({Path.cwd().name})" if tool.scope == "project" else "global"
        if tool.is_installed():
            installed = sorted(p.name for p in tool.install_path.iterdir())
            print(f"  {tool.name} [{scope}] — {detected}")
            print(f"    {tool.install_path}")
            for name in installed:
                print(f"      · {name}")
            any_found = True
        else:
            print(f"  {tool.name} [{scope}] — {detected}, not installed")

    if not any_found:
        print("\n  Nothing installed yet. Run: holoviz-skills install")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    tools = _make_tools()

    requested = [key for key in tools if getattr(args, _key_attr(key), False)]
    if not requested:
        print("Specify at least one tool flag, e.g. --claude-code")
        return 1

    for key in requested:
        tools[key].uninstall()
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="holoviz-skills",
        description="Install HoloViz Agent Skills into AI coding tools.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    def _add_tool_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--claude-code", action="store_true", help="~/.claude/skills/  (global)")
        p.add_argument("--copilot", action="store_true", help=".github/instructions/  (project)")
        p.add_argument("--cursor", action="store_true", help=".cursor/rules/  (project)")
        p.add_argument("--windsurf", action="store_true", help=".windsurf/skills/  (project)")
        p.add_argument("--cline", action="store_true", help=".cline/skills/  (project)")
        p.add_argument(
            "--continue", action="store_true", dest="continue_", help=".continue/rules/  (project)"
        )
        p.add_argument("--gemini-cli", action="store_true", help=".gemini/skills/  (project)")

    # install
    p_install = sub.add_parser(
        "install", help="Install skills (auto-detects tools if no flag given)"
    )
    _add_tool_flags(p_install)

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove installed skills")
    _add_tool_flags(p_uninstall)

    # list
    sub.add_parser("list", help="Show installed skills and detected tools")

    args = parser.parse_args(argv)

    if args.command == "install":
        return cmd_install(args)
    elif args.command == "uninstall":
        return cmd_uninstall(args)
    elif args.command == "list":
        return cmd_list(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
