"""CLI for installing HoloViz Agent Skills into AI coding tools.

Usage::

    holoviz-skills install --help           # show all tool flags
    holoviz-skills install                  # auto-detect tools
    holoviz-skills install --global         # install to global (~/) paths
    holoviz-skills list                     # show what's installed where
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

    def detect_reason(self) -> str:
        """Return a human-readable string of what triggered detection."""
        try:
            return self.detect_fn() or ""
        except Exception:
            return ""

    def is_installed(self, skill_names: list[str]) -> bool:
        """True only if the HoloViz skills themselves are present at the install path.

        Checks for the specific skill units rather than merely a non-empty
        directory, so unrelated content in a shared standard dir (e.g.
        ``~/.agents/skills``, used by both the Agent and Codex tools) is not
        mistaken for an install. Handles both layouts: directory copies
        (``developing-with-holoviz/``) and flat files
        (``developing-with-holoviz-panel.md``, ``creating-custom-holoviz-skills.md``).
        """
        if not self.install_path.exists():
            return False
        entries = [p.name for p in self.install_path.iterdir()]
        return any(
            entry == name  # directory install
            or entry.startswith(f"{name}-")  # flat sub-skill file
            or entry.startswith(f"{name}.")  # flat single-file skill
            for name in skill_names
            for entry in entries
        )

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


def _check(*conditions: tuple[bool, str]) -> str:
    """Return a comma-separated string of reasons for matched conditions."""
    return ", ".join(label for matched, label in conditions if matched)


def _make_tools(*, use_global: bool = False) -> dict[str, Tool]:
    home = Path.home()
    cwd = Path.cwd()

    def _g(project: Path, global_: Path) -> Path:
        return global_ if use_global else project

    def _scope() -> str:
        return "global" if use_global else "project"

    tools: list[Tool] = [
        # --- Anthropic ---
        Tool(
            key="claude-code",
            name="Claude Code / Cowork",
            scope=_scope(),
            install_path=_g(cwd / ".claude" / "skills", home / ".claude" / "skills"),
            detect_fn=lambda: _check(
                (bool(shutil.which("claude")), "claude binary"),
                ((home / ".claude").exists(), "~/.claude exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Cross-tool standard (.agents/skills/) ---
        Tool(
            key="agent",
            name="Agent skills (.agents/skills/)",
            scope=_scope(),
            install_path=_g(
                cwd / ".agents" / "skills",
                home / ".agents" / "skills",
            ),
            detect_fn=lambda: "",
            install_fn=_install_dirs,
        ),
        # --- OpenAI ---
        Tool(
            key="codex",
            name="OpenAI Codex",
            scope=_scope(),
            install_path=_g(cwd / ".agents" / "skills", home / ".agents" / "skills"),
            detect_fn=lambda: _check(
                (bool(shutil.which("codex")), "codex binary"),
                ((cwd / ".codex").exists(), ".codex exists"),
                ((home / ".codex").exists(), "~/.codex exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- GitHub ---
        Tool(
            key="copilot",
            name="GitHub Copilot",
            scope=_scope(),
            install_path=_g(
                cwd / ".github" / "skills",
                home / ".copilot" / "skills",
            ),
            detect_fn=lambda: _check(
                (bool(shutil.which("code")), "code binary"),
                ((cwd / ".github").exists(), ".github exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Cursor ---
        Tool(
            key="cursor",
            name="Cursor",
            scope=_scope(),
            install_path=_g(
                cwd / ".cursor" / "skills",
                home / ".cursor" / "skills",
            ),
            detect_fn=lambda: _check(
                (bool(shutil.which("cursor")), "cursor binary"),
                ((cwd / ".cursor").exists(), ".cursor exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Windsurf ---
        Tool(
            key="windsurf",
            name="Windsurf",
            scope=_scope(),
            install_path=_g(
                cwd / ".windsurf" / "skills",
                home / ".codeium" / "windsurf" / "skills",
            ),
            detect_fn=lambda: _check(
                (bool(shutil.which("windsurf")), "windsurf binary"),
                ((cwd / ".windsurf").exists(), ".windsurf exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Cline ---
        Tool(
            key="cline",
            name="Cline",
            scope=_scope(),
            install_path=_g(
                cwd / ".cline" / "skills",
                home / ".cline" / "skills",
            ),
            detect_fn=lambda: _check(
                ((cwd / ".cline").exists(), ".cline exists"),
                ((home / ".cline").exists(), "~/.cline exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- JetBrains (Junie) ---
        Tool(
            key="jetbrains",
            name="JetBrains (Junie)",
            scope=_scope(),
            install_path=_g(cwd / ".junie" / "skills", home / ".junie" / "skills"),
            detect_fn=lambda: _check(
                ((cwd / ".junie").exists(), ".junie exists"),
                ((home / ".junie").exists(), "~/.junie exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Google ---
        Tool(
            key="gemini-cli",
            name="Gemini CLI",
            scope=_scope(),
            install_path=_g(cwd / ".gemini" / "skills", home / ".gemini" / "skills"),
            detect_fn=lambda: _check(
                (bool(shutil.which("gemini")), "gemini binary"),
                ((cwd / ".gemini").exists(), ".gemini exists"),
            ),
            install_fn=_install_dirs,
        ),
        Tool(
            key="antigravity",
            name="Google Antigravity",
            scope=_scope(),
            install_path=_g(
                cwd / ".agents" / "skills",
                home / ".gemini" / "antigravity" / "skills",
            ),
            detect_fn=lambda: _check(
                (bool(shutil.which("antigravity")), "antigravity binary"),
                ((home / ".gemini" / "antigravity").exists(), "~/.gemini/antigravity exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Kiro ---
        Tool(
            key="kiro",
            name="Kiro",
            scope=_scope(),
            install_path=_g(cwd / ".kiro" / "skills", home / ".kiro" / "skills"),
            detect_fn=lambda: _check(
                (bool(shutil.which("kiro")), "kiro binary"),
                ((cwd / ".kiro").exists(), ".kiro exists"),
                ((home / ".kiro").exists(), "~/.kiro exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Kilo Code ---
        Tool(
            key="kilo-code",
            name="Kilo Code",
            scope=_scope(),
            install_path=_g(cwd / ".kilo" / "skills", home / ".kilo" / "skills"),
            detect_fn=lambda: _check(
                (bool(shutil.which("kilo")), "kilo binary"),
                ((cwd / ".kilo").exists(), ".kilo exists"),
                ((home / ".kilo").exists(), "~/.kilo exists"),
            ),
            install_fn=_install_dirs,
        ),
        # --- Mistral ---
        Tool(
            key="mistral-vibe",
            name="Mistral Vibe",
            scope=_scope(),
            install_path=_g(cwd / ".vibe" / "skills", home / ".vibe" / "skills"),
            detect_fn=lambda: _check(
                ((cwd / ".vibe").exists(), ".vibe exists"),
                ((home / ".vibe").exists(), "~/.vibe exists"),
            ),
            install_fn=_install_dirs,
        ),
    ]
    return {t.key: t for t in tools}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# argparse cannot use 'continue' as an attribute name (Python keyword), so
# that flag is stored as 'continue_'.  Map all tool keys to their actual attr.
_KEY_TO_ATTR: dict[str, str] = {}


def _key_attr(key: str) -> str:
    """Return the argparse Namespace attribute name for a tool key."""
    return _KEY_TO_ATTR.get(key, key.replace("-", "_"))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_install(args: argparse.Namespace) -> int:
    tools = _make_tools(use_global=args.use_global)
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
        for key in requested:
            reason = tools[key].detect_reason()
            if reason:
                print(f"  {tools[key].name}: {reason}")
        print()

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
    project_tools = _make_tools(use_global=False)
    global_tools = _make_tools(use_global=True)
    skill_dirs = _find_skill_dirs(_skills_root())

    skill_names = [d.name for d in skill_dirs]
    print(f"Available skills ({len(skill_dirs)}): {', '.join(skill_names)}\n")

    # Build rows: (name, project_path, global_path, status)
    rows: list[tuple[str, str, str, str]] = []
    for key, pt in project_tools.items():
        gt = global_tools[key]
        proj_path = str(pt.install_path)
        glob_path = str(gt.install_path) if gt.install_path != pt.install_path else "—"
        installed_where: list[str] = []
        if pt.is_installed(skill_names):
            installed_where.append("project")
        if gt.install_path != pt.install_path and gt.is_installed(skill_names):
            installed_where.append("global")
        if installed_where:
            status = "✓ installed (" + ", ".join(installed_where) + ")"
        elif pt.detected():
            status = "✓ detected"
        else:
            status = "—"
        rows.append((pt.name, proj_path, glob_path, status))

    # Column widths.
    name_w = max(len("Tool"), max(len(r[0]) for r in rows))
    proj_w = max(len("Project path"), max(len(r[1]) for r in rows))
    glob_w = max(len("Global path"), max(len(r[2]) for r in rows))
    stat_w = max(len("Status"), max(len(r[3]) for r in rows))

    print(
        f"  {'Tool':<{name_w}}  {'Project path':<{proj_w}}  "
        f"{'Global path':<{glob_w}}  {'Status':<{stat_w}}"
    )
    print(f"  {'─' * name_w}  {'─' * proj_w}  {'─' * glob_w}  {'─' * stat_w}")
    for name, proj, glob, status in rows:
        print(f"  {name:<{name_w}}  {proj:<{proj_w}}  {glob:<{glob_w}}  {status:<{stat_w}}")

    print()
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    tools = _make_tools(use_global=args.use_global)

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

    def _add_tool_flags(p: argparse.ArgumentParser, *, include_global: bool = False) -> None:
        if include_global:
            p.add_argument(
                "--global",
                action="store_true",
                dest="use_global",
                help="Install to global (home directory) paths instead of project",
            )
        p.add_argument("--claude-code", action="store_true", help=".claude/skills/")
        p.add_argument(
            "--agent",
            action="store_true",
            help=".agents/skills/  (cross-tool standard, commit to git)",
        )
        p.add_argument("--codex", action="store_true", help=".agents/skills/  (OpenAI Codex)")
        p.add_argument("--copilot", action="store_true", help=".github/skills/  (GitHub Copilot)")
        p.add_argument("--cursor", action="store_true", help=".cursor/skills/")
        p.add_argument("--windsurf", action="store_true", help=".windsurf/skills/")
        p.add_argument("--cline", action="store_true", help=".cline/skills/")
        p.add_argument("--jetbrains", action="store_true", help=".junie/skills/  (JetBrains/Junie)")
        p.add_argument("--gemini-cli", action="store_true", help=".gemini/skills/")
        p.add_argument(
            "--antigravity", action="store_true", help=".agents/skills/  (Google Antigravity)"
        )
        p.add_argument("--kiro", action="store_true", help=".kiro/skills/")
        p.add_argument("--kilo-code", action="store_true", help=".kilo/skills/  (Kilo Code)")
        p.add_argument("--mistral-vibe", action="store_true", help=".vibe/skills/  (Mistral Vibe)")

    # install
    p_install = sub.add_parser(
        "install", help="Install skills (auto-detects tools if no flag given)"
    )
    _add_tool_flags(p_install, include_global=True)

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove installed skills")
    _add_tool_flags(p_uninstall, include_global=True)

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
