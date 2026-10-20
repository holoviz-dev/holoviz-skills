"""CLI for installing HoloViz Agent Skills into AI coding tools.

Usage::

    uvx holoviz-skills install              # auto-detect tools, nothing to pre-install
    holoviz-skills install --help           # show all tool flags
    holoviz-skills install --global         # install to global (~/) paths
    holoviz-skills install developing --claude-code  # one skill (name or prefix)
    holoviz-skills list                     # show what's installed where, and if it's current
    holoviz-skills update                   # re-install what's installed, showing what changed
    holoviz-skills doctor                   # stale copies, library versions, compatibility
    holoviz-skills uninstall --claude-code
    holoviz-skills --version                # show the installed version
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from holoviz_skills import __version__

_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_VERSION_RE = re.compile(r'^\s+version:\s*["\']?([0-9][0-9.]*)["\']?\s*$', re.MULTILINE)
_COMPATIBILITY_RE = re.compile(r"^compatibility:\s*(.+)$", re.MULTILINE)
_REQUIREMENT_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_.-]*)\s*(>=|<=|==|!=|>|<)\s*([0-9][0-9.]*)")

# Libraries the skills teach; doctor reports their versions in the user's env.
LIBRARIES = (
    "panel",
    "panel-material-ui",
    "holoviews",
    "hvplot",
    "param",
    "bokeh",
    "datashader",
    "geoviews",
    "lumen",
)

# Runs in the project's interpreter, which may not have this package installed.
_VERSIONS_SNIPPET = """
import importlib.metadata as md, json, sys
found = {}
for name in sys.argv[1:]:
    try:
        found[name] = md.version(name)
    except md.PackageNotFoundError:
        found[name] = None
print(json.dumps(found))
"""


@dataclass
class Tool:
    """One AI coding tool: where its skills go, and how to tell it's on this machine."""

    key: str
    name: str
    scope: str  # "project" or "global"
    install_path: Path
    detect_fn: Callable[[], str]

    def detect_reason(self) -> str:
        """What showed the tool is on this machine, or "" if nothing did."""
        try:
            return self.detect_fn()
        except OSError as e:
            # A config dir we can't stat (e.g. PermissionError) shouldn't abort the
            # install, but say so rather than silently reporting "not detected".
            print(f"warning: couldn't check for {self.name}: {e}", file=sys.stderr)
            return ""

    def is_installed(self, skill_names: list[str]) -> bool:
        """True only if our skills are there, not merely a non-empty directory.

        Several tools share ``~/.agents/skills``, so unrelated skills there mustn't
        count as an install.
        """
        return bool(_skill_entries(self.install_path, skill_names))

    def install(self, skill_dirs: list[Path]) -> int:
        return _install_dirs(skill_dirs, self.install_path)

    def uninstall(self, skill_names: list[str]) -> int:
        """Remove our skills, leaving unrelated content in a shared directory.

        The install directory goes too if that leaves it empty.
        """
        entries = _skill_entries(self.install_path, skill_names)
        if not entries:
            print(f"  {self.name}: nothing to remove")
            return 0
        for entry in entries:
            entry.unlink() if entry.is_symlink() or not entry.is_dir() else shutil.rmtree(entry)
            print(f"    - {entry.name}")
        if not any(self.install_path.iterdir()):
            self.install_path.rmdir()
        print(f"  {self.name}: removed {len(entries)} skill(s) from {self.install_path}")
        return len(entries)


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def _is_repo_checkout(path: Path) -> bool:
    """True if ``path`` is a holoviz-skills source checkout (not just any repo)."""
    return (path / "developing-with-holoviz" / "SKILL.md").exists() and (
        path / "pyproject.toml"
    ).exists()


def _skills_root() -> Path:
    """Locate the skill directories, whether installed or running from source.

    A source checkout wins over skills bundled in an installed package. Without
    this, running from a checkout while the package is also pip-installed
    silently installs the *released* skills instead of the working tree: the
    console script does not put the cwd on ``sys.path``, so it imports the
    site-packages copy, whose bundled ``skills/`` would otherwise be preferred.
    """
    # Source checkout containing this module (editable install or repo run).
    repo_root = Path(__file__).parent.parent
    if _is_repo_checkout(repo_root):
        return repo_root
    # Source checkout we were invoked from, even if we imported an installed copy.
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if _is_repo_checkout(candidate):
            return candidate
    # Installed package: skills bundled inside the package as data.
    pkg_skills = Path(__file__).parent / "skills"
    if pkg_skills.is_dir():
        return pkg_skills
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


def _select_skills(skill_dirs: list[Path], names: list[str]) -> list[Path] | None:
    """Filter ``skill_dirs`` to ``names``, matching full names or unique prefixes
    (``developing`` → ``developing-with-holoviz``); all if empty, None on a bad name."""
    if not names:
        return skill_dirs
    available = {d.name: d for d in skill_dirs}
    selected: dict[str, Path] = {}
    bad: list[str] = []
    for name in names:
        matches = [n for n in available if n == name] or [
            n for n in available if n.startswith(name)
        ]
        if len(matches) == 1:
            selected[matches[0]] = available[matches[0]]
        else:
            bad.append(f"{name} ({'ambiguous' if matches else 'unknown'})")
    if bad:
        print(f"Bad skill name(s): {', '.join(bad)}", file=sys.stderr)
        print(f"Available: {', '.join(available)}", file=sys.stderr)
        return None
    return list(selected.values())


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------


def _frontmatter(skill_md: Path) -> str:
    if not skill_md.is_file():
        return ""
    m = _FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
    return m.group(0) if m else ""


def _versions(skill_dir: Path) -> dict[str, str | None]:
    """``metadata.version`` of every SKILL.md in a skill tree, keyed by skill name.

    Each sub-skill is versioned on its own, so the routing skill's version alone
    can't say whether an installed copy is current.
    """
    versions: dict[str, str | None] = {}
    for skill_md in sorted(skill_dir.rglob("SKILL.md")):
        m = _VERSION_RE.search(_frontmatter(skill_md))
        versions[skill_md.parent.name] = m.group(1) if m else None
    return versions


def _version_changes(old: dict[str, str | None], new: dict[str, str | None]) -> list[str]:
    """``"panel 2026.09.28 → 2026.10.15"`` for each skill whose version differs."""
    return [
        f"{name} {old.get(name) or '—'} → {new.get(name) or 'removed'}"
        for name in sorted(old.keys() | new.keys())
        if old.get(name) != new.get(name)
    ]


def _requirements(skill_dir: Path) -> list[tuple[str, str, str, str]]:
    """``(skill, package, op, version)`` from every ``compatibility:`` field in a tree."""
    found = []
    for skill_md in sorted(skill_dir.rglob("SKILL.md")):
        m = _COMPATIBILITY_RE.search(_frontmatter(skill_md))
        if m:
            name = skill_md.parent.name
            found.extend((name, *req) for req in _REQUIREMENT_RE.findall(m.group(1)))
    return found


# ---------------------------------------------------------------------------
# Installing
# ---------------------------------------------------------------------------


def _skill_entries(path: Path, skill_names: list[str]) -> list[Path]:
    """Entries under ``path`` that belong to the given HoloViz skills.

    Used to detect and remove only our own skills, leaving unrelated content in
    a shared standard dir (e.g. ``~/.agents/skills``, shared by the Agent and
    Codex tools) untouched.

    Every tool now installs directory copies (``developing-with-holoviz/``), but
    the name matching also covers the flat-file layout that older versions wrote
    (``developing-with-holoviz-panel.md``, ``creating-custom-holoviz-skills.md``)
    so ``uninstall`` still cleans up after them.
    """
    if not path.exists():
        return []
    return [
        p
        for p in sorted(path.iterdir())
        if any(
            p.name == name or p.name.startswith(f"{name}-") or p.name.startswith(f"{name}.")
            for name in skill_names
        )
    ]


def _install_dirs(skill_dirs: list[Path], dest: Path) -> int:
    """Copy full skill directory trees, reporting which skills changed in each."""
    dest.mkdir(parents=True, exist_ok=True)
    for skill_dir in skill_dirs:
        target = dest / skill_dir.name
        old = _versions(target) if target.is_dir() else {}
        # `npx skills` installs symlinks to its own copy: replace the link, not what it
        # points to (rmtree refuses symlinks anyway).
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            skill_dir,
            target,
            ignore=shutil.ignore_patterns(".DS_Store", ".gitkeep", "__pycache__", "test_*.py"),
        )
        changes = _version_changes(old, _versions(target))
        status = "new" if not old else "; ".join(changes) or "unchanged"
        print(f"    + {skill_dir.name}/  ({status})")
    return len(skill_dirs)


def _installed_locations(skill_dirs: list[Path]) -> list[tuple[str, Path, list[Path]]]:
    """``(tool names, install path, our copies there)`` for each path holding any.

    Keyed by path, not tool, because several tools share ``.agents/skills``. A
    symlinked skill belongs to whatever made the link, like ``npx skills``, so
    ``list``, ``update`` and ``doctor`` leave it out.
    """
    found: dict[Path, tuple[list[str], list[Path]]] = {}
    for use_global in (False, True):
        for tool in _make_tools(use_global=use_global).values():
            path = tool.install_path
            copies = [c for d in skill_dirs if (c := path / d.name).is_dir() and not c.is_symlink()]
            if copies:
                names, _ = found.setdefault(path, ([], copies))
                if tool.name not in names:
                    names.append(tool.name)
    return [(", ".join(names), path, copies) for path, (names, copies) in found.items()]


def _print_installed(locations: list[tuple[str, Path, list[Path]]], skill_dirs: list[Path]) -> int:
    """Print each installed copy against this release; return how many differ."""
    if not locations:
        return 0
    source = {d.name: d for d in skill_dirs}
    differing = 0
    print("Installed copies, compared with this release:")
    for names, path, copies in locations:
        print(f"  {path}  [{names}]")
        for copy in copies:
            changes = _version_changes(_versions(copy), _versions(source[copy.name]))
            differing += bool(changes)
            state = "differs: " + "; ".join(changes) if changes else "up to date"
            print(f"    {copy.name}: {state}")
    print()
    return differing


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _check(*conditions: tuple[bool, str]) -> str:
    """Return a comma-separated string of reasons for matched conditions."""
    return ", ".join(label for matched, label in conditions if matched)


def _make_tools(*, use_global: bool = False) -> dict[str, Tool]:
    home = Path.home()
    cwd = Path.cwd()
    scope = "global" if use_global else "project"

    def tool(key: str, name: str, project: Path, global_: Path, detect_fn) -> Tool:
        return Tool(key, name, scope, global_ if use_global else project, detect_fn)

    tools = [
        tool(
            "claude-code",
            "Claude Code / Cowork",
            cwd / ".claude" / "skills",
            home / ".claude" / "skills",
            lambda: _check(
                (bool(shutil.which("claude")), "claude binary"),
                ((home / ".claude").exists(), "~/.claude exists"),
            ),
        ),
        tool(
            "agent",
            "Cross-tool standard",
            cwd / ".agents" / "skills",
            home / ".agents" / "skills",
            lambda: "",
        ),
        tool(
            "codex",
            "OpenAI Codex",
            cwd / ".agents" / "skills",
            home / ".agents" / "skills",
            lambda: _check(
                (bool(shutil.which("codex")), "codex binary"),
                ((cwd / ".codex").exists(), ".codex exists"),
                ((home / ".codex").exists(), "~/.codex exists"),
            ),
        ),
        tool(
            "copilot",
            "GitHub Copilot",
            cwd / ".github" / "skills",
            home / ".copilot" / "skills",
            lambda: _check(
                (bool(shutil.which("code")), "code binary"),
                ((cwd / ".github").exists(), ".github exists"),
            ),
        ),
        tool(
            "cursor",
            "Cursor",
            cwd / ".cursor" / "skills",
            home / ".cursor" / "skills",
            lambda: _check(
                (bool(shutil.which("cursor")), "cursor binary"),
                ((cwd / ".cursor").exists(), ".cursor exists"),
            ),
        ),
        tool(
            "windsurf",
            "Windsurf",
            cwd / ".windsurf" / "skills",
            home / ".codeium" / "windsurf" / "skills",
            lambda: _check(
                (bool(shutil.which("windsurf")), "windsurf binary"),
                ((cwd / ".windsurf").exists(), ".windsurf exists"),
            ),
        ),
        tool(
            "cline",
            "Cline",
            cwd / ".cline" / "skills",
            home / ".cline" / "skills",
            lambda: _check(
                ((cwd / ".cline").exists(), ".cline exists"),
                ((home / ".cline").exists(), "~/.cline exists"),
            ),
        ),
        tool(
            "jetbrains",
            "JetBrains (Junie)",
            cwd / ".junie" / "skills",
            home / ".junie" / "skills",
            lambda: _check(
                ((cwd / ".junie").exists(), ".junie exists"),
                ((home / ".junie").exists(), "~/.junie exists"),
            ),
        ),
        tool(
            "gemini-cli",
            "Gemini CLI",
            cwd / ".gemini" / "skills",
            home / ".gemini" / "skills",
            lambda: _check(
                (bool(shutil.which("gemini")), "gemini binary"),
                ((cwd / ".gemini").exists(), ".gemini exists"),
            ),
        ),
        tool(
            "antigravity",
            "Google Antigravity",
            cwd / ".agents" / "skills",
            home / ".gemini" / "antigravity" / "skills",
            lambda: _check(
                (bool(shutil.which("antigravity")), "antigravity binary"),
                ((home / ".gemini" / "antigravity").exists(), "~/.gemini/antigravity exists"),
            ),
        ),
        tool(
            "kiro",
            "Kiro",
            cwd / ".kiro" / "skills",
            home / ".kiro" / "skills",
            lambda: _check(
                (bool(shutil.which("kiro")), "kiro binary"),
                ((cwd / ".kiro").exists(), ".kiro exists"),
                ((home / ".kiro").exists(), "~/.kiro exists"),
            ),
        ),
        tool(
            "kilo-code",
            "Kilo Code",
            cwd / ".kilo" / "skills",
            home / ".kilo" / "skills",
            lambda: _check(
                (bool(shutil.which("kilo")), "kilo binary"),
                ((cwd / ".kilo").exists(), ".kilo exists"),
                ((home / ".kilo").exists(), "~/.kilo exists"),
            ),
        ),
        tool(
            "mistral-vibe",
            "Mistral Vibe",
            cwd / ".vibe" / "skills",
            home / ".vibe" / "skills",
            lambda: _check(
                ((cwd / ".vibe").exists(), ".vibe exists"),
                ((home / ".vibe").exists(), "~/.vibe exists"),
            ),
        ),
    ]
    return {t.key: t for t in tools}


def _requested(args: argparse.Namespace, tools: dict[str, Tool]) -> list[str]:
    """Keys of the tools whose flag was passed (``--claude-code`` → ``claude_code``)."""
    return [key for key in tools if getattr(args, key.replace("-", "_"), False)]


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


def _project_python(explicit: str | None) -> str:
    """The interpreter of the user's project rather than the one running this CLI.

    Under ``uvx`` this CLI runs in a throwaway environment without the user's
    libraries, so an activated virtualenv or conda env wins, then ``python`` on PATH.
    """
    if explicit:
        return explicit
    for var in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        prefix = os.environ.get(var)
        if not prefix or Path(prefix).resolve() == Path(sys.prefix).resolve():
            continue
        for rel in ("bin/python", "Scripts/python.exe", "python.exe"):
            if (Path(prefix) / rel).exists():
                return str(Path(prefix) / rel)
    return shutil.which("python3") or shutil.which("python") or sys.executable


def _library_versions(python: str, names: list[str]) -> dict[str, str | None]:
    result = subprocess.run(
        [python, "-c", _VERSIONS_SNIPPET, *names],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def _show_versions(python: str) -> str:
    """``hv.show_versions()`` run in the project's interpreter, indented for the report."""
    result = subprocess.run(
        [python, "-c", "import holoviews as hv; hv.show_versions()"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return textwrap.indent(result.stdout.rstrip(), "  ")


def _satisfies(found: str, op: str, wanted: str) -> bool:
    def numbers(version: str) -> tuple[int, ...]:
        m = re.match(r"\d+(?:\.\d+)*", version)
        return tuple(int(x) for x in m.group(0).split(".")) if m else ()

    a, b = numbers(found), numbers(wanted)
    width = max(len(a), len(b))
    a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return {">=": a >= b, "<=": a <= b, "==": a == b, "!=": a != b, ">": a > b, "<": a < b}[op]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_install(args: argparse.Namespace) -> int:
    tools = _make_tools(use_global=args.use_global)
    skills_root = _skills_root()
    skill_dirs = _select_skills(_find_skill_dirs(skills_root), args.skills)
    if skill_dirs is None:
        return 2
    print(f"Source: {skills_root}\n")

    requested = _requested(args, tools)
    if not requested:
        reasons = {key: tool.detect_reason() for key, tool in tools.items()}
        requested = [key for key, reason in reasons.items() if reason]
        if not requested:
            print("No supported AI tools detected. Run with a specific flag:")
            for key, tool in tools.items():
                print(f"  --{key:20s}  {tool.name} ({tool.scope})")
            return 1
        print(f"Detected: {', '.join(tools[k].name for k in requested)}\n")
        for key in requested:
            print(f"  {tools[key].name}: {reasons[key]}")
        print()

    total = 0
    for key in requested:
        tool = tools[key]
        print(f"Installing into {tool.name} ({tool.scope}: {tool.install_path})")
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

    rows: list[tuple[str, str, str, str]] = []
    for key, pt in project_tools.items():
        gt = global_tools[key]
        shared = gt.install_path == pt.install_path
        installed_where = []
        if pt.is_installed(skill_names):
            installed_where.append("project")
        if not shared and gt.is_installed(skill_names):
            installed_where.append("global")
        if installed_where:
            status = f"✓ installed ({', '.join(installed_where)})"
        elif pt.detect_reason():
            status = "✓ detected"
        else:
            status = "—"
        glob_path = "—" if shared else str(gt.install_path)
        rows.append((pt.name, str(pt.install_path), glob_path, status))

    header = ("Tool", "Project path", "Global path", "Status")
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(header)]
    for row in (header, tuple("─" * w for w in widths), *rows):
        print("  " + "  ".join(f"{cell:<{w}}" for cell, w in zip(row, widths)).rstrip())

    print()
    if _print_installed(_installed_locations(skill_dirs), skill_dirs):
        print("Run `holoviz-skills update` to bring these in line with this release.\n")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    tools = _make_tools(use_global=args.use_global)
    skill_dirs = _select_skills(_find_skill_dirs(_skills_root()), args.skills)
    if skill_dirs is None:
        return 2
    skill_names = [d.name for d in skill_dirs]

    requested = _requested(args, tools)
    if not requested:
        print("Specify at least one tool flag, e.g. --claude-code")
        return 1

    for key in requested:
        tools[key].uninstall(skill_names)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    skill_dirs = _select_skills(_find_skill_dirs(_skills_root()), args.skills)
    if skill_dirs is None:
        return 2
    source = {d.name: d for d in skill_dirs}
    tools = _make_tools(use_global=args.use_global)
    only = {tools[key].install_path for key in _requested(args, tools)}

    total = 0
    for names, path, copies in _installed_locations(skill_dirs):
        if only and path not in only:
            continue
        print(f"Updating {path}  [{names}]")
        total += _install_dirs([source[c.name] for c in copies], path)
        print()
    if not total:
        print("No installed HoloViz skills to update. Install some first, e.g.")
        print("  holoviz-skills install developing --claude-code")
        return 1
    print(f"Done — {total} skill(s) refreshed from holoviz-skills {__version__}.")
    print("For the newest release instead: uvx holoviz-skills@latest update")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    skill_dirs = _find_skill_dirs(_skills_root())
    print(f"holoviz-skills {__version__}\n")

    locations = _installed_locations(skill_dirs)
    problems = _print_installed(locations, skill_dirs)
    if not locations:
        print("No HoloViz skills installed. Run `holoviz-skills install`; it detects your tools.\n")
        problems += 1
    elif problems:
        print("Run `holoviz-skills update` to refresh the copies that differ.\n")

    trees = [copy for _, _, copies in locations for copy in copies] or skill_dirs
    requirements = list(dict.fromkeys(r for tree in trees for r in _requirements(tree)))
    names = list(dict.fromkeys([*LIBRARIES, *(pkg for _, pkg, _, _ in requirements)]))
    python = _project_python(args.python)
    print(f"Libraries in {python} (pass --python to check another):")
    try:
        versions = _library_versions(python, names)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"  couldn't query {python}: {e}")
        return 1
    listed = ", ".join(f"{n} {v}" for n, v in versions.items() if v)
    print(f"  {listed}" if listed else "  none of the HoloViz libraries are installed")

    if versions.get("holoviews"):
        print("\nhv.show_versions(), to paste into a HoloViz issue:")
        # Informational only, so a failure here doesn't fail the check.
        try:
            print(_show_versions(python))
        except (OSError, subprocess.SubprocessError) as e:
            print(f"  couldn't run it: {e}")

    print("\nCompatibility:")
    if not requirements:
        print("  no skill declares a `compatibility` requirement")
    for skill, pkg, op, wanted in requirements:
        found = versions.get(pkg)
        if found is None:
            print(f"  skip {skill} needs {pkg}{op}{wanted}; {pkg} isn't installed")
            continue
        ok = _satisfies(found, op, wanted)
        problems += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {skill} needs {pkg}{op}{wanted}, found {found}")
    return 1 if problems else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="holoviz-skills",
        description="Install HoloViz Agent Skills into AI coding tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    def add_tool_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "skills",
            nargs="*",
            metavar="SKILL",
            help="Skill(s) to act on by name or unique prefix, e.g. developing, "
            "contributing (default: all; see `holoviz-skills list`)",
        )
        p.add_argument(
            "--global",
            action="store_true",
            dest="use_global",
            help="Use global (home directory) paths instead of project paths",
        )
        cwd = Path.cwd()
        for key, tool in _make_tools().items():
            path = tool.install_path.relative_to(cwd)
            p.add_argument(f"--{key}", action="store_true", help=f"{path}/  ({tool.name})")

    add_tool_flags(
        sub.add_parser("install", help="Install skills (auto-detects tools if no flag given)")
    )
    add_tool_flags(sub.add_parser("uninstall", help="Remove installed skills"))
    sub.add_parser("list", help="Show installed skills, detected tools, and stale copies")
    add_tool_flags(
        sub.add_parser("update", help="Re-install the skills you have installed, showing changes")
    )
    p_doctor = sub.add_parser(
        "doctor", help="Check installed skills against your HoloViz library versions"
    )
    p_doctor.add_argument(
        "--python", help="Interpreter of the project to check (default: the active environment)"
    )

    args = parser.parse_args(argv)

    commands = {
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "list": cmd_list,
        "update": cmd_update,
        "doctor": cmd_doctor,
    }
    if args.command not in commands:
        parser.print_help()
        return 0
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
