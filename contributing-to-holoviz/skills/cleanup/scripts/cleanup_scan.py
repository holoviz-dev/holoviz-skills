#!/usr/bin/env python3
"""Flag the code slop from the cleanup skill that a parser can find.

Usage:
    cleanup_scan.py PATH [PATH ...]    scan .py files (directories are walked)

Options:
    --only IDS       scan with only these rules (comma separated)
    --skip IDS       scan with every rule except these
    --json           emit JSON instead of a text report
    --list-rules     print the rule table and exit

Point it at the whole package rather than only the changed files, since
``single-use-constant`` counts reads across every file it's given.

The scan is the mechanical half of a review. It can't tell whether a guard can
fail, whether a helper already exists under another name, or whether a comment
is still true, so read the change as well (see the cleanup skill's Review
section). A hit that's right as written gets ``# cleanup: ignore[rule-id]`` on
its line, followed by the reason, the same way a ``# noqa`` should carry one.

Exit status: 0 clean, 1 hits found, 2 no file could be parsed.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass

RULES = {
    "file-order": "constant after a function or class, or function after a class",
    "single-use-constant": "module-level constant read only once",
    "deferred-stdlib-import": "standard-library import inside a function",
    "restating-docstring": "one-line docstring that only repeats the name and arguments",
    "blind-except": "bare except, or except Exception without re-raising",
    "silent-except": "handler that passes or returns None, so the caller can't see the failure",
}

IGNORE_RE = re.compile(r"#\s*cleanup:\s*ignore\[([a-z0-9,\s-]+)\]")
BROAD_EXCEPTIONS = {"Exception", "BaseException"}
# Data types that function signatures below them refer to, so they come first.
RECORD_BASES = {"Enum", "IntEnum", "NamedTuple", "Protocol", "StrEnum", "TypedDict"}
SKIP_DIRS = {"__pycache__", "node_modules"}

# Words a summary line needs for grammar, plus the verbs docstrings open with.
# What's left once these and the name's own words are removed is what the
# docstring adds.
FILLER = frozenset(
    "a an and as at by for from given if in into is it its of on or the this that to with "
    "check checks compute computes create creates get gets make makes return returns "
    "run runs".split()
)


@dataclass
class Hit:
    path: str
    line: int
    rule: str
    message: str


def name_words(name: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {w for w in spaced.lower().split("_") if w}


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def constant_names(node: ast.stmt) -> list[str]:
    """Return the UPPER_CASE names a module-level assignment binds."""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
    else:
        return []
    names = [t.id for t in targets if isinstance(t, ast.Name)]
    return [n for n in names if n.isupper() and not n.startswith("__")]


def _is_literal(value: ast.expr | None) -> bool:
    # A computed value, like a compiled regex, earns a name even when it's read
    # once. A literal read where a parameter name already explains it doesn't.
    try:
        ast.literal_eval(value)
    except (TypeError, ValueError, SyntaxError, RecursionError):
        return False
    return True


def _none_like(value: ast.expr | None, none_defaults: set[str]) -> bool:
    if value is None:
        return True
    if isinstance(value, ast.Constant) and value.value is None:
        return True
    return isinstance(value, ast.Name) and value.id in none_defaults


def _none_defaults(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    pairs = list(zip(positional[len(positional) - len(args.defaults) :], args.defaults))
    pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
    return {a.arg for a, d in pairs if isinstance(d, ast.Constant) and d.value is None}


def is_record_type(node: ast.ClassDef) -> bool:
    decorators = {ast.unparse(d).split("(")[0].split(".")[-1] for d in node.decorator_list}
    bases = {ast.unparse(b).split(".")[-1] for b in node.bases}
    return "dataclass" in decorators or bool(bases & RECORD_BASES)


def check_file_order(path: str, tree: ast.Module) -> list[Hit]:
    hits = []
    first_def = first_class = None
    defined: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if first_class:
                message = f"{node.name} is after class {first_class}"
                hits.append(Hit(path, node.lineno, "file-order", message))
            first_def = first_def or node.name
            defined.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if not is_record_type(node):
                first_class = first_class or node.name
            defined.add(node.name)
        elif names := constant_names(node):
            refs = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            earlier = first_def or first_class
            # A constant built from a function or class has to come after it.
            if earlier and not refs & defined:
                message = f"{', '.join(names)} is defined after {earlier}"
                hits.append(Hit(path, node.lineno, "file-order", message))
    return hits


def check_single_use_constants(
    path: str, tree: ast.Module, reads: Counter, named_reads: set[str]
) -> list[Hit]:
    hits = []
    for node in tree.body:
        if not _is_literal(getattr(node, "value", None)):
            continue
        for name in constant_names(node):
            # Only a read as a default or keyword value counts, since the
            # parameter's name already says what the value is there. Zero reads
            # is likely public API used outside the scanned files.
            if reads[name] == 1 and name in named_reads:
                message = f"{name} is read once, as a value the parameter name explains; inline it"
                hits.append(Hit(path, node.lineno, "single-use-constant", message))
    return hits


def check_function_bodies(path: str, tree: ast.Module) -> list[Hit]:
    hits = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        hits += _restating_docstring(path, func)
        if isinstance(func, ast.ClassDef):
            continue
        none_defaults = _none_defaults(func)
        for node in _own_nodes(func):
            if isinstance(node, ast.Import | ast.ImportFrom):
                hits += _deferred_stdlib_import(path, node)
            elif isinstance(node, ast.ExceptHandler):
                hits += _except_handler(path, node, none_defaults)
    return hits


def _own_nodes(func: ast.AST):
    """Yield the nodes in *func*'s body, not those of functions nested in it."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))


def _restating_docstring(path: str, node: ast.AST) -> list[Hit]:
    doc = ast.get_docstring(node)
    if not doc or "\n" in doc.strip():
        return []
    known = name_words(node.name)
    if not isinstance(node, ast.ClassDef):
        for arg in ast.walk(node.args):
            if isinstance(arg, ast.arg):
                known |= name_words(arg.arg)
    words = re.findall(r"[a-z0-9]+", doc.lower())
    extra = [w for w in words if w not in FILLER and w not in known and _singular(w) not in known]
    if len(extra) > 1:
        return []
    message = f"docstring of {node.name} repeats its name; cut it or say what the name can't"
    return [Hit(path, node.body[0].lineno, "restating-docstring", message)]


def _deferred_stdlib_import(path: str, node: ast.Import | ast.ImportFrom) -> list[Hit]:
    if isinstance(node, ast.ImportFrom):
        modules = [] if node.level else [node.module or ""]
    else:
        modules = [alias.name for alias in node.names]
    stdlib = [m for m in modules if m.split(".")[0] in sys.stdlib_module_names]
    if not stdlib or stdlib == ["__future__"]:
        return []
    message = f"import of {', '.join(stdlib)} belongs at the top of the file"
    return [Hit(path, node.lineno, "deferred-stdlib-import", message)]


def _except_handler(path: str, node: ast.ExceptHandler, none_defaults: set[str]) -> list[Hit]:
    hits = []
    caught = node.type
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    broad = caught is None or any(
        isinstance(n, ast.Name) and n.id in BROAD_EXCEPTIONS for n in names
    )
    reraises = any(isinstance(n, ast.Raise) for n in ast.walk(node))
    if broad and not reraises:
        what = "bare except" if caught is None else f"except {ast.unparse(caught)}"
        message = f"{what} also catches the bug you'd want to see; catch what can be raised"
        hits.append(Hit(path, node.lineno, "blind-except", message))

    silent = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
    returns_none = any(
        isinstance(n, ast.Return) and _none_like(n.value, none_defaults) for n in ast.walk(node)
    )
    if silent or returns_none:
        what = "passes" if silent else "returns None"
        message = f"handler {what}, so the caller can't tell the failure from a normal result"
        hits.append(Hit(path, node.lineno, "silent-except", message))
    return hits


def _read_name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return node.attr if isinstance(node, ast.Attribute) else None


def count_reads(trees: list[ast.Module]) -> tuple[Counter, set[str]]:
    """Count reads of each name, and collect those read as a default or keyword value."""
    reads: Counter = Counter()
    named: list[ast.expr | None] = []
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                reads[node.id] += 1
            elif isinstance(node, ast.Attribute):
                reads[node.attr] += 1
            if isinstance(node, ast.arguments):
                named += [*node.defaults, *node.kw_defaults]
            elif isinstance(node, ast.Call):
                named += [kw.value for kw in node.keywords]
    return reads, {name for value in named if (name := _read_name(value))}


def ignored(hit: Hit, lines: list[str]) -> bool:
    if not 0 < hit.line <= len(lines):
        return False
    match = IGNORE_RE.search(lines[hit.line - 1])
    return bool(match) and hit.rule in {r.strip() for r in match.group(1).split(",")}


def scan_sources(sources: dict[str, str], rules: set[str] | None = None) -> list[Hit]:
    """Scan ``{path: source}`` together. Raises SyntaxError if a source doesn't parse."""
    rules = set(RULES) if rules is None else rules
    trees = {path: ast.parse(source, filename=path) for path, source in sources.items()}
    reads, named_reads = count_reads(list(trees.values()))
    hits = []
    for path, tree in trees.items():
        found = (
            check_file_order(path, tree)
            + check_single_use_constants(path, tree, reads, named_reads)
            + check_function_bodies(path, tree)
        )
        lines = sources[path].splitlines()
        hits += [h for h in found if h.rule in rules and not ignored(h, lines)]
    return sorted(hits, key=lambda h: (h.path, h.line, h.rule))


def collect_paths(paths: list[str]) -> list[str]:
    found = []
    for path in paths:
        if not os.path.isdir(path):
            found.append(path)
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
            found += [os.path.join(root, f) for f in sorted(files) if f.endswith(".py")]
    return found


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", metavar="PATH")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-rules", action="store_true")
    args = ap.parse_args(argv)

    if args.list_rules:
        for rule, description in RULES.items():
            print(f"  {rule:24s} {description}")
        return 0
    if not args.paths:
        ap.error("no files given")

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown = (only | skip) - set(RULES)
    if unknown:
        ap.error(f"unknown rule(s): {', '.join(sorted(unknown))}")

    sources, errors = {}, []
    for path in collect_paths(args.paths):
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            ast.parse(source, filename=path)
        except (OSError, SyntaxError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        sources[path] = source
    for error in errors:
        print(error, file=sys.stderr)
    if not sources:
        return 2

    hits = scan_sources(sources, (only or set(RULES)) - skip)
    if args.json:
        print(json.dumps([asdict(h) for h in hits], indent=2))
    else:
        for h in hits:
            print(f"{h.path}:{h.line}: [{h.rule}] {h.message}")
        if hits:
            counts = Counter(h.rule for h in hits)
            print(f"\n{len(hits)} hits: " + ", ".join(f"{r} x{n}" for r, n in counts.items()))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
