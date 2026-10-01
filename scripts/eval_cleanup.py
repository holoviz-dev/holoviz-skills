#!/usr/bin/env python3
"""Check whether the cleanup skill catches the slop in a known change.

The fixture in ``eval_fixtures/cleanup_review/`` is a tiny package whose
``pkg/query.py`` is the opening snippet of "Deslop AI Slop Part 2: Code". This
asks Kilo to clean that file up against the rest of the package, with and
without skills, and grades the returned file on the six findings from the post:

1. comments and docstrings that repeat the names are gone
2. no module-level constant used only once
3. no import inside a function, and classes come after functions
4. no blind ``except Exception`` and no timeout turned into ``None``
5. the existing ``pkg.utils.with_timeout`` is reused
6. the existing ``pkg.sources.duckdb.missing_table_name`` is reused

Usage:
  python scripts/eval_cleanup.py                       # both conditions, default model
  python scripts/eval_cleanup.py --models kilo/kilo-auto/free --skills with
  python scripts/eval_cleanup.py --grade path/to/query.py  # grade a file, no Kilo run

Responses land in ``eval_results/cleanup_review/<model>/<condition>/``.
"""

import argparse
import ast
import json
import sys
from pathlib import Path

from eval import (
    CODE_OUTPUT_INSTRUCTION,
    DEFAULT_MODEL,
    REPO_ROOT,
    KiloResponse,
    model_to_slug,
    run_kilo_query,
)
from toggle_skills import disable_skills, enable_skills

FIXTURE = Path("scripts/eval_fixtures/cleanup_review")

PROMPT = f"""\
The repository in {FIXTURE}/ is a small Python package. A pull request adds
{FIXTURE}/pkg/query.py. Review that change against the rest of the package and
clean it up. Don't edit any files; respond with the full revised pkg/query.py.
"""

RESTATING = (
    "Seconds to wait before giving up on a query",
    "Run a coroutine with a timeout.",
    "Return the name of the missing table from an error.",
)


def _names(tree: ast.AST) -> set[str]:
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {alias.name for alias in node.names}
    return names


def _no_restating_comments(source: str, tree: ast.AST) -> bool:
    return not any(text in source for text in RESTATING)


def _no_single_use_constants(source: str, tree: ast.AST) -> bool:
    loads = [
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    ]
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        for target in targets:
            single_use = loads.count(getattr(target, "id", "")) <= 1
            if isinstance(target, ast.Name) and target.id.isupper() and single_use:
                return False
    return True


def _imports_and_order(source: str, tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if any(isinstance(n, ast.Import | ast.ImportFrom) for n in ast.walk(node)):
                return False
    seen_class = False
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            seen_class = True
        elif seen_class and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Assign):
            return False
    return True


def _no_hiding_guards(source: str, tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        caught = node.type.id if isinstance(node.type, ast.Name) else None
        if node.type is None or caught in ("Exception", "BaseException"):
            return False
        returns_none = (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Return)
            and (node.body[0].value is None or ast.unparse(node.body[0].value) == "None")
        )
        if caught == "TimeoutError" and returns_none:
            return False
    return True


def _reuses_with_timeout(source: str, tree: ast.AST) -> bool:
    return "with_timeout" in _names(tree) and "wait_for" not in _names(tree)


def _reuses_duckdb_parser(source: str, tree: ast.AST) -> bool:
    return "missing_table_name" in _names(tree) and "Table with name" not in source


CHECKS = {
    "restating comments removed": _no_restating_comments,
    "no single-use constant": _no_single_use_constants,
    "imports at top, classes last": _imports_and_order,
    "no guard that hides a failure": _no_hiding_guards,
    "reuses with_timeout": _reuses_with_timeout,
    "reuses missing_table_name": _reuses_duckdb_parser,
}


def grade(source: str) -> dict[str, bool]:
    """Return each check's result. Code that doesn't parse fails every check."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return dict.fromkeys(CHECKS, False)
    return {name: check(source, tree) for name, check in CHECKS.items()}


def print_grade(label: str, results: dict[str, bool]) -> None:
    print(f"{label}: {sum(results.values())}/{len(results)}")
    for name, passed in results.items():
        print(f"  {'✓' if passed else '✗'} {name}")


def run_condition(model: str | None, skills: bool, output_dir: Path) -> dict[str, bool]:
    prompt = PROMPT + CODE_OUTPUT_INSTRUCTION
    if not skills:
        disable_skills(REPO_ROOT)
    try:
        raw_output, exec_time, events, returncode = run_kilo_query(prompt, model=model)
    finally:
        if not skills:
            enable_skills(REPO_ROOT)
    response = KiloResponse(
        raw_output,
        prompt,
        exec_time,
        model=model or DEFAULT_MODEL,
        events=events,
        returncode=returncode,
    )
    code = response.get_primary_code() or ""

    condition = "with_skills" if skills else "without_skills"
    result_dir = output_dir / model_to_slug(model) / condition
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "response.txt").write_text(raw_output)
    (result_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (result_dir / "query.py").write_text(code)
    results = grade(code)
    (result_dir / "grade.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=[None], metavar="MODEL")
    parser.add_argument("--skills", choices=["both", "with", "without"], default="both")
    parser.add_argument("--grade", nargs="+", type=Path, metavar="FILE")
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "eval_results" / "cleanup_review"
    )
    args = parser.parse_args()

    if args.grade:
        for path in args.grade:
            print_grade(str(path), grade(path.read_text()))
        return 0

    conditions = {"both": [False, True], "with": [True], "without": [False]}[args.skills]
    for model in args.models:
        for skills in conditions:
            label = f"{model or 'default'} {'with' if skills else 'without'} skills"
            print_grade(label, run_condition(model, skills, args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
