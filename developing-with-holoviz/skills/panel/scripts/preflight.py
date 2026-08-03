#!/usr/bin/env python3
"""Static lint for generated Panel/panel-material-ui app code.

Greps the mechanical anti-patterns already documented in reviewing-panel-apps.md
and troubleshooting.md, before the first `panel serve`. Cheap and deterministic —
run this before spending a screenshot on a visual check.

Usage:
    python preflight.py app.py [more_files.py ...]

Exits 0 with no output if clean. Exits 1 and prints one line per violation:
    file:line: [CHECK_ID] message (see reviewing-panel-apps.md#anchor)

Checks are per-function, with no cross-function call-graph analysis — most
notably, MISSING_HOLD can false-positive on a helper method that is only ever
called from inside a caller's own `with pn.io.hold():` block (hold is
reentrant, so that's fine as written). Read the flagged line before editing.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass

LAYOUT_CONSTRUCTOR_SUFFIXES = (
    "Column",
    "Row",
    "Paper",
    "Grid",
    "Container",
    "Card",
    "Tabs",
    "Accordion",
    "GridSpec",
    "GridBox",
    "FlexBox",
)


@dataclass
class Violation:
    line: int
    check: str
    message: str
    doc: str

    def format(self, path: str) -> str:
        return f"{path}:{self.line}: [{self.check}] {self.message} (see {self.doc})"


def _call_name(node: ast.AST) -> str | None:
    """Return the trailing name of a Call's func, e.g. 'pmui.Row(...)' -> 'Row'."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _decorator_calls_depends(dec: ast.AST) -> ast.Call | None:
    """Return the Call node if *dec* is (a call to) param.depends, else None."""
    if isinstance(dec, ast.Call):
        name = _call_name(dec)
        if name == "depends":
            return dec
    return None


def _depends_has_kwarg_true(call: ast.Call, kwarg: str) -> bool:
    for kw in call.keywords:
        if kw.arg == kwarg and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _returns_layout_constructor(func: ast.FunctionDef) -> ast.Return | None:
    """Find a `return <LayoutConstructor(...)>` anywhere directly in the function body
    (not nested in a helper def), skipping Placeholder (the correct idiom)."""
    for node in ast.walk(func):
        if isinstance(node, ast.FunctionDef) and node is not func:
            continue  # don't descend into nested function defs
        if isinstance(node, ast.Return) and node.value is not None:
            name = _call_name(node.value)
            if name in LAYOUT_CONSTRUCTOR_SUFFIXES:
                return node
    return None


def _find_super_init_line(func: ast.FunctionDef) -> int | None:
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "__init__" and isinstance(node.func.value, ast.Call):
                inner = node.func.value
                if isinstance(inner.func, ast.Name) and inner.func.id == "super":
                    return node.lineno
    return None


def _find_from_param_calls_before(func: ast.FunctionDef, boundary_line: int) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "from_param" and node.lineno < boundary_line:
                lines.append(node.lineno)
    return lines


def _count_top_level_assigns_outside_hold(func: ast.FunctionDef) -> list[ast.Assign]:
    """Attribute assignments (x.y = ...) directly in the function body (not inside
    a `with pn.io.hold():` block), used to flag 3+ ungrouped property writes."""
    hits: list[ast.Assign] = []

    def in_hold_with(node: ast.With) -> bool:
        for item in node.items:
            call = item.context_expr
            if isinstance(call, ast.Call):
                name = _call_name(call)
                if name == "hold":
                    return True
        return False

    def walk_body(body: list[ast.stmt], inside_hold: bool) -> None:
        for stmt in body:
            if isinstance(stmt, ast.With):
                nested_hold = inside_hold or in_hold_with(stmt)
                walk_body(stmt.body, nested_hold)
                continue
            if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
                for attr in ("body", "orelse", "finalbody", "handlers"):
                    sub = getattr(stmt, attr, None)
                    if not sub:
                        continue
                    if attr == "handlers":
                        for h in sub:
                            walk_body(h.body, inside_hold)
                    else:
                        walk_body(sub, inside_hold)
                continue
            if isinstance(stmt, ast.Assign) and not inside_hold:
                for target in stmt.targets:
                    if isinstance(target, ast.Attribute) and isinstance(
                        target.value, ast.Attribute
                    ):
                        # self._widget.value = ... — a property write on a
                        # sub-component, the pattern hold() batches.
                        hits.append(stmt)
                        break

    walk_body(func.body, False)
    return hits


def check_ast(tree: ast.Module) -> list[Violation]:
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        depends_call = None
        for dec in node.decorator_list:
            depends_call = _decorator_calls_depends(dec)
            if depends_call:
                break

        if depends_call is not None:
            has_watch = _depends_has_kwarg_true(depends_call, "watch")
            if not has_watch:
                ret = _returns_layout_constructor(node)
                if ret is not None:
                    violations.append(
                        Violation(
                            ret.lineno,
                            "FLICKER_RECREATED_LAYOUT",
                            f"`{node.name}` is @param.depends (no watch=True) and returns a "
                            "layout/widget constructor — recreates it on every dependency "
                            "change, causing flicker. Create once in __init__, update "
                            "properties or use pn.pane.Placeholder instead.",
                            "reviewing-panel-apps.md#flickering-from-recreated-components",
                        )
                    )
            else:
                # watch=True: side-effects only, should not return a value.
                for sub in ast.walk(node):
                    if isinstance(sub, ast.FunctionDef) and sub is not node:
                        continue
                    if (
                        isinstance(sub, ast.Return)
                        and sub.value is not None
                        and not (isinstance(sub.value, ast.Constant) and sub.value.value is None)
                    ):
                        violations.append(
                            Violation(
                                sub.lineno,
                                "WATCH_RETURNS_VALUE",
                                f"`{node.name}` is @param.depends(..., watch=True) but returns "
                                "a value — watch=True is for side effects (won't be displayed "
                                "anywhere); split into a watch=True updater plus a plain "
                                "@param.depends view method.",
                                "reviewing-panel-apps.md#watch-vs-depends-misuse",
                            )
                        )

        if node.name == "__init__":
            boundary = _find_super_init_line(node)
            if boundary is not None:
                for line in _find_from_param_calls_before(node, boundary):
                    violations.append(
                        Violation(
                            line,
                            "FROM_PARAM_BEFORE_SUPER",
                            ".from_param() widget created before super().__init__() — its "
                            "watchers/@param.depends will silently never fire. Move it after "
                            "super().__init__().",
                            "reviewing-panel-apps.md#from_param-widgets-created-before-super",
                        )
                    )

        # 3+ ungrouped property assignments — only meaningful inside watcher-ish
        # methods, but cheap enough to check any method.
        if node.name != "__init__":
            hits = _count_top_level_assigns_outside_hold(node)
            if len(hits) >= 3:
                violations.append(
                    Violation(
                        hits[0].lineno,
                        "MISSING_HOLD",
                        f"`{node.name}` makes {len(hits)} ungrouped widget/pane property "
                        "assignments — wrap in `with pn.io.hold(): ...` to batch into one "
                        "redraw. Known false-positive case: if every call site already wraps "
                        "the call to this method in `pn.io.hold()`, this is fine as-is (hold "
                        "is reentrant) — this check has no cross-function call-site analysis, "
                        "so verify the callers before editing.",
                        "panel/SKILL.md#performance",
                    )
                )

    return violations


REGEX_CHECKS: list[tuple[str, re.Pattern, str, str]] = [
    (
        "DICT_SELECTOR_OBJECTS",
        re.compile(r"\.objects\s*=\s*\{"),
        "A dict assigned to a Selector's .objects — renders blank. Use a list, or a "
        "dict passed to the Selector constructor's `objects=` kwarg instead.",
        "troubleshooting.md#select-renders-blank-after-setting-objects",
    ),
    (
        "MUTATING_PARAM_LIST",
        re.compile(r"self\.\w+\.append\("),
        "In-place `.append()` on what may be a param value — won't trigger watchers "
        "if so. Reassign the whole list/dict instead: `self.x = self.x + [item]`.",
        "reviewing-panel-apps.md#mutating-instead-of-reassigning",
    ),
    (
        "MUTATING_PARAM_ITEM",
        re.compile(r"self\.\w+\[[^\]]+\]\s*="),
        "In-place item assignment on what may be a param value — won't trigger "
        "watchers if so. Reassign the whole object instead.",
        "reviewing-panel-apps.md#mutating-instead-of-reassigning",
    ),
    (
        "RADIO_DEFAULT_NONE",
        re.compile(r"Radio(BoxGroup|ButtonGroup)\([^)]*(value|default)\s*=\s*None"),
        "RadioBoxGroup/RadioButtonGroup constructed with a None default — the first "
        "option can't be selected. Set an explicit non-None default.",
        "troubleshooting.md#first-radio-option-cant-be-selected",
    ),
]


def check_regex(source: str) -> list[Violation]:
    violations: list[Violation] = []
    lines = source.splitlines()
    for i, line in enumerate(lines, start=1):
        for check_id, pattern, message, doc in REGEX_CHECKS:
            if pattern.search(line):
                violations.append(Violation(i, check_id, message, doc))
    return violations


def check_throttled(source: str) -> list[Violation]:
    slider_pattern = re.compile(r"\b(Int|Float|Range|Date(Range)?)?Slider\(")
    has_slider = bool(slider_pattern.search(source))
    if not has_slider:
        return []
    ext_match = re.search(r"pn\.extension\(([^)]*)\)", source)
    if ext_match and "throttled=True" in ext_match.group(1):
        return []
    return [
        Violation(
            1,
            "MISSING_THROTTLED",
            "Sliders are used but pn.extension(throttled=True) isn't set — every "
            "drag pixel fires a callback instead of only on release.",
            "panel/SKILL.md#widgets-and-extensions",
        )
    ]


def lint_file(path: str) -> list[Violation]:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        return [Violation(e.lineno or 1, "SYNTAX_ERROR", str(e), "-")]
    violations = check_ast(tree)
    violations += check_regex(source)
    violations += check_throttled(source)
    violations.sort(key=lambda v: v.line)
    return violations


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python preflight.py app.py [more_files.py ...]", file=sys.stderr)
        return 2
    total = 0
    for path in argv:
        violations = lint_file(path)
        for v in violations:
            print(v.format(path))
        total += len(violations)
    if total == 0:
        print(f"preflight: clean ({len(argv)} file(s) checked)")
        return 0
    print(f"\npreflight: {total} violation(s) across {len(argv)} file(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
