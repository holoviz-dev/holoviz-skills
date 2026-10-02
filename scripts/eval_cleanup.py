#!/usr/bin/env python3
"""Check whether the cleanup skill catches the slop in a known change.

Each fixture under ``eval_fixtures/`` is a tiny package with one sloppy change,
and the helpers that change rewrites already live elsewhere in the package.
``cleanup_review`` is the opening snippet of "Deslop AI Slop Part 2: Code". The
cleanup skill quotes part of it, so read its with-skills score as a smoke test.
``cleanup_holdout`` plants the same six findings in code the skills never show.

Each run copies the fixture's ``pkg/`` into a fresh temporary directory, adds
the skills for the with-skills condition, and asks Kilo to clean the change up.
Kilo works in that directory, so it can't read this file, the fixture READMEs
or the CHANGELOG, all of which describe the answers. CI denies Kilo edits, so
the revised files come from the response; a local run that edits in place is
graded from disk instead. The checks, numbered as in the post:

1. docstrings and comments that only repeat a name are gone
2. no module-level constant is read once as a value its parameter name explains
3. standard-library imports sit at the top, in the skill's file order
4. blind excepts and handlers that turn a failure into None are gone, from the
   change and from the helper it should reuse
5. the change calls the package's existing helper instead of rewriting it
6. it calls the existing parser instead of copying its regex

Checks 1-4 are ``cleanup_scan.py`` rules, so the eval grades with the same
rules the skill tells agents to run.

Usage:
  python scripts/eval_cleanup.py                          # every fixture, both conditions
  python scripts/eval_cleanup.py --fixtures cleanup_holdout --repeat 5
  python scripts/eval_cleanup.py --models kilo/kilo-auto/free --skills with
  python scripts/eval_cleanup.py --fixtures cleanup_holdout --grade DIR   # grade DIR/pkg, no Kilo

Each run lands in ``eval_results/cleanup/<fixture>/<model>/<condition>/run-<n>/``.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from eval import DEFAULT_MODEL, REPO_ROOT, KiloResponse, model_to_slug, run_kilo_query

FIXTURES_DIR = REPO_ROOT / "scripts" / "eval_fixtures"
SKILL_ROOTS = (
    "developing-with-holoviz",
    "contributing-to-holoviz",
    "creating-custom-holoviz-skills",
)
FILE_MARKER_RE = re.compile(r"\A#\s*file:\s*(\S+)\s*\n")
SCAN_CHECKS = {
    "restating comments removed": {"restating-docstring"},
    "no single-use constant": {"single-use-constant"},
    "imports at top, file order": {"deferred-stdlib-import", "file-order"},
    "no guard that hides a failure": {"blind-except", "silent-except"},
}

PROMPT = """\
This directory holds a small Python package, pkg/. A pull request adds {change}.
Review that change against the rest of the package and clean it up. Don't edit
any files. Respond with the full revised contents of every file you would
change, each in its own ```python block whose first line is `# file: <path>`.
"""

# cleanup_scan.py lives with the skill it serves, outside scripts/.
_spec = importlib.util.spec_from_file_location(
    "cleanup_scan",
    REPO_ROOT / "contributing-to-holoviz" / "skills" / "cleanup" / "scripts" / "cleanup_scan.py",
)
cleanup_scan = importlib.util.module_from_spec(_spec)
sys.modules["cleanup_scan"] = cleanup_scan  # dataclasses look their module up here
_spec.loader.exec_module(cleanup_scan)


@dataclass(frozen=True)
class Fixture:
    change: str
    helper: str
    restating_comments: tuple[str, ...]
    reuse: dict[str, Callable[[str, ast.Module], bool]]


def names(tree: ast.Module) -> set[str]:
    found = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    found |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found |= {alias.name for alias in node.names}
    return found


def reuses_with_timeout(source: str, tree: ast.Module) -> bool:
    return "with_timeout" in names(tree) and "wait_for" not in names(tree)


def reuses_missing_table_name(source: str, tree: ast.Module) -> bool:
    return "missing_table_name" in names(tree) and "Table with name" not in source


def reuses_retry(source: str, tree: ast.Module) -> bool:
    loops = (n for n in ast.walk(tree) if isinstance(n, ast.For | ast.While))
    retries_in_a_loop = any(isinstance(n, ast.Try) for loop in loops for n in ast.walk(loop))
    return "retry" in names(tree) and not retries_in_a_loop


def reuses_scan_time(source: str, tree: ast.Module) -> bool:
    return "scan_time" in names(tree) and "%Y%m%d" not in source


FIXTURES = {
    "cleanup_review": Fixture(
        change="pkg/query.py",
        helper="pkg/utils.py",
        restating_comments=("Seconds to wait before giving up on a query",),
        reuse={
            "reuses with_timeout": reuses_with_timeout,
            "reuses missing_table_name": reuses_missing_table_name,
        },
    ),
    "cleanup_holdout": Fixture(
        change="pkg/loader.py",
        helper="pkg/utils.py",
        restating_comments=("Number of times to retry a download",),
        reuse={"reuses retry": reuses_retry, "reuses scan_time": reuses_scan_time},
    ),
}


def grade(fixture: Fixture, files: dict[str, str]) -> dict[str, bool]:
    """Grade ``{path: source}`` for the whole package. A file that doesn't parse fails."""
    checks = [*SCAN_CHECKS, *fixture.reuse]
    change = files.get(fixture.change, "")
    try:
        hits = cleanup_scan.scan_sources(files)
        tree = ast.parse(change)
    except SyntaxError:
        return dict.fromkeys(checks, False)

    def hit(rules: set[str], *paths: str) -> bool:
        return any(h.rule in rules and h.path in paths for h in hits)

    results = {name: not hit(rules, fixture.change) for name, rules in SCAN_CHECKS.items()}
    results["restating comments removed"] &= not any(
        text in change for text in fixture.restating_comments
    )
    guard_rules = SCAN_CHECKS["no guard that hides a failure"]
    results["no guard that hides a failure"] = not hit(guard_rules, fixture.change, fixture.helper)
    results |= {name: check(change, tree) for name, check in fixture.reuse.items()}
    return results


def read_package(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text()
        for path in sorted((root / "pkg").rglob("*.py"))
    }


def revised_files(response: KiloResponse, change: str) -> dict[str, str]:
    """Return ``{path: source}`` from the response's code blocks.

    A block without a ``# file:`` first line is taken as the change itself.
    """
    files = {}
    for block in response.code_blocks:
        match = FILE_MARKER_RE.match(block)
        path = PurePosixPath(match.group(1) if match else change)
        if path.parts[:1] != ("pkg",):
            path = "pkg" / path
        # Only .py paths inside pkg/ are kept, since each is written to disk.
        if path.suffix != ".py" or ".." in path.parts:
            continue
        files[path.as_posix()] = block[match.end() :] if match else block
    return files


def make_workspace(fixture_name: str, skills: bool) -> Path:
    workspace = Path(tempfile.mkdtemp(prefix=f"{fixture_name}-"))
    shutil.copytree(FIXTURES_DIR / fixture_name / "pkg", workspace / "pkg")
    if skills:
        # Skip dot directories, which can hold stale worktrees with old SKILL.md copies.
        ignore = shutil.ignore_patterns(".*", "__pycache__")
        for root in SKILL_ROOTS:
            shutil.copytree(REPO_ROOT / root, workspace / root, ignore=ignore)
        shutil.copy2(REPO_ROOT / "AGENTS.md", workspace / "AGENTS.md")
    return workspace


def run_once(
    fixture_name: str, model: str | None, skills: bool, timeout: int, result_dir: Path
) -> dict[str, bool]:
    fixture = FIXTURES[fixture_name]
    workspace = make_workspace(fixture_name, skills)
    try:
        before = read_package(workspace)
        prompt = PROMPT.format(change=fixture.change)
        raw_output, exec_time, events, returncode = run_kilo_query(
            prompt, model=model, timeout=timeout, cwd=workspace
        )
        on_disk = read_package(workspace)
    finally:
        shutil.rmtree(workspace)

    response = KiloResponse(
        raw_output,
        prompt,
        exec_time,
        model=model or DEFAULT_MODEL,
        events=events,
        returncode=returncode,
    )
    revised = revised_files(response, fixture.change)
    if revised:
        files, source = before | revised, "response"
    else:
        files, source = on_disk, "disk" if on_disk != before else "unchanged"

    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "response.txt").write_text(raw_output)
    (result_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    for path, text in files.items():
        (result_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (result_dir / path).write_text(text)
    results = grade(fixture, files)
    record = {"graded_from": source, "returncode": returncode, "checks": results}
    (result_dir / "grade.json").write_text(json.dumps(record, indent=2) + "\n")
    return results


def print_summary(label: str, runs: list[dict[str, bool]]) -> None:
    mean = sum(sum(r.values()) for r in runs) / len(runs)
    print(f"{label}: {mean:.1f}/{len(runs[0])}, over {len(runs)} run(s)")
    for name in runs[0]:
        print(f"  {sum(r[name] for r in runs)}/{len(runs)}  {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", nargs="+", choices=list(FIXTURES), default=list(FIXTURES))
    parser.add_argument("--models", nargs="+", default=[None], metavar="MODEL")
    parser.add_argument("--skills", choices=["both", "with", "without"], default="both")
    parser.add_argument("--repeat", type=int, default=1, metavar="N")
    parser.add_argument("--timeout", type=int, default=300, metavar="SECONDS")
    parser.add_argument("--grade", type=Path, metavar="DIR", help="grade DIR/pkg, no Kilo run")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "eval_results" / "cleanup")
    args = parser.parse_args()

    if args.grade:
        if len(args.fixtures) != 1:
            parser.error("--grade needs exactly one --fixtures name")
        fixture = FIXTURES[args.fixtures[0]]
        print_summary(str(args.grade), [grade(fixture, read_package(args.grade))])
        return 0

    conditions = {"both": [False, True], "with": [True], "without": [False]}[args.skills]
    for fixture_name in args.fixtures:
        for model in args.models:
            for skills in conditions:
                condition = "with_skills" if skills else "without_skills"
                base = args.output / fixture_name / model_to_slug(model) / condition
                runs = [
                    run_once(fixture_name, model, skills, args.timeout, base / f"run-{n}")
                    for n in range(1, args.repeat + 1)
                ]
                label = f"{fixture_name}  {model or 'default'}  {condition.replace('_', ' ')}"
                print_summary(label, runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
