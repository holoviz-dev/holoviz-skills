#!/usr/bin/env python3
"""Static lint for generated Panel/panel-material-ui app code.

Greps the mechanical anti-patterns already documented in reviewing-panel-apps.md
and troubleshooting.md, before the first `panel serve`. Cheap and deterministic —
run this before spending a screenshot on a visual check.

Usage:
    python preflight.py app.py [more_files.py ...]

Exits 0 with no output if clean. Exits 1 and prints one line per violation:
    file:line: [CHECK_ID] message (see reviewing-panel-apps.md#anchor)

All checks are AST-based (no source-text regexes), so they don't fire on
docstrings/comments/strings and aren't sensitive to line breaks inside a call.
Checks that walk a single function's body use `iter_own_scope`, which — unlike
`ast.walk` — does not descend into nested `def`/`lambda`/`class`, so a construct
inside a nested closure isn't misattributed to the enclosing method.

Known false-positive class: MISSING_HOLD has no cross-function call-graph
analysis, so a helper method that is only ever called from inside a caller's
own `with pn.io.hold():` block will still be flagged (hold is reentrant, so
that's fine as written) — read the flagged line before editing.
"""

from __future__ import annotations

import ast
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
RADIO_GROUP_NAMES = ("RadioBoxGroup", "RadioButtonGroup")
SLIDER_SUFFIX = "Slider"
SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
FuncDef = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass
class Violation:
    line: int
    check: str
    message: str
    doc: str

    def format(self, path: str) -> str:
        return f"{path}:{self.line}: [{self.check}] {self.message} (see {self.doc})"


def iter_own_scope(node: ast.AST):
    """DFS over *node*'s descendants, without crossing into a nested scope.

    Unlike `ast.walk`, which yields every descendant regardless of what the
    caller does with intermediate nodes, this stops descending the moment it
    hits a nested FunctionDef/AsyncFunctionDef/Lambda/ClassDef — so a `return`
    or a call inside a nested helper/closure is never attributed to the
    enclosing function.
    """
    stack = list(ast.iter_child_nodes(node))
    while stack:
        child = stack.pop()
        yield child
        if isinstance(child, SCOPE_NODES):
            continue
        stack.extend(ast.iter_child_nodes(child))


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


def _is_self_attr(node: ast.AST, name: str | None = None) -> bool:
    """True if *node* is `self.<attr>` (optionally a specific `name`)."""
    if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)):
        return False
    if node.value.id != "self":
        return False
    return name is None or node.attr == name


def _decorator_depends_call(dec: ast.AST) -> ast.Call | None:
    """Return the Call node if *dec* is a call to `depends` — matches
    `@param.depends(...)`, `@pn.depends(...)` (Panel's re-export), and a bare
    `@depends(...)` from `from param import depends`. Matched on the trailing
    attribute/name only, so any of those spellings qualify."""
    if isinstance(dec, ast.Call) and _call_name(dec) == "depends":
        return dec
    return None


def _kwarg_is(call: ast.Call, kwarg: str, value) -> bool:
    for kw in call.keywords:
        if kw.arg == kwarg and isinstance(kw.value, ast.Constant) and kw.value.value is value:
            return True
    return False


def _returns_layout_constructor(func: FuncDef) -> ast.Return | None:
    """Find a `return <LayoutConstructor(...)>` in *func*'s own scope (not a
    nested helper/closure)."""
    for node in iter_own_scope(func):
        if isinstance(node, ast.Return) and node.value is not None:
            if _call_name(node.value) in LAYOUT_CONSTRUCTOR_SUFFIXES:
                return node
    return None


def _returns_nonnull_value(func: FuncDef) -> ast.Return | None:
    for node in iter_own_scope(func):
        if isinstance(node, ast.Return) and node.value is not None:
            if not (isinstance(node.value, ast.Constant) and node.value.value is None):
                return node
    return None


def _find_super_init_line(func: FuncDef) -> int | None:
    for node in iter_own_scope(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "__init__"
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "super"
        ):
            return node.lineno
    return None


def _find_from_param_calls_before(func: FuncDef, boundary_line: int) -> list[int]:
    lines: list[int] = []
    for node in iter_own_scope(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_param"
            and node.lineno < boundary_line
        ):
            lines.append(node.lineno)
    return lines


def _is_redraw_write(stmt: ast.stmt) -> bool:
    """True if *stmt* is a property write Panel would redraw on: either
    `x.y = ...` where `x` is itself an attribute (e.g. `self._widget.value =`),
    or a `.update(...)` call on such an attribute (the Placeholder/pane idiom,
    e.g. `self._content.update(step)` — a method call, not an assignment, but
    the same redraw-per-call cost `pn.io.hold()` exists to batch)."""
    if isinstance(stmt, ast.Assign):
        return any(
            isinstance(t, ast.Attribute) and isinstance(t.value, ast.Attribute)
            for t in stmt.targets
        )
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        func = stmt.value.func
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "update"
            and isinstance(func.value, ast.Attribute)
        )
    return False


def _count_top_level_assigns_outside_hold(func: FuncDef) -> list[ast.stmt]:
    """Property writes (assignments or `.update()` calls, see `_is_redraw_write`)
    directly in the function body (not inside a `with pn.io.hold():` block),
    used to flag 3+ ungrouped writes."""
    hits: list[ast.stmt] = []

    def in_hold_with(node: ast.With) -> bool:
        return any(
            isinstance(item.context_expr, ast.Call) and _call_name(item.context_expr) == "hold"
            for item in node.items
        )

    def walk_body(body: list[ast.stmt], inside_hold: bool) -> None:
        for stmt in body:
            if isinstance(stmt, ast.With):
                walk_body(stmt.body, inside_hold or in_hold_with(stmt))
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
            if not inside_hold and _is_redraw_write(stmt):
                hits.append(stmt)

    walk_body(func.body, False)
    return hits


def check_function_level(tree: ast.Module) -> list[Violation]:
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        depends_call = next(
            (c for dec in node.decorator_list if (c := _decorator_depends_call(dec))), None
        )

        if depends_call is not None:
            has_watch = _kwarg_is(depends_call, "watch", True)
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
                ret = _returns_nonnull_value(node)
                if ret is not None:
                    violations.append(
                        Violation(
                            ret.lineno,
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
        else:
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


def check_dict_selector_objects(tree: ast.Module) -> list[Violation]:
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "objects":
                    violations.append(
                        Violation(
                            node.lineno,
                            "DICT_SELECTOR_OBJECTS",
                            "A dict assigned to a Selector's .objects — renders blank. Use a "
                            "list, or a dict passed to the Selector constructor's `objects=` "
                            "kwarg instead.",
                            "troubleshooting.md#select-renders-blank-after-setting-objects",
                        )
                    )
    return violations


def check_radio_default_none(tree: ast.Module) -> list[Violation]:
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) in RADIO_GROUP_NAMES:
            if _kwarg_is(node, "value", None) or _kwarg_is(node, "default", None):
                violations.append(
                    Violation(
                        node.lineno,
                        "RADIO_DEFAULT_NONE",
                        f"{_call_name(node)} constructed with a None default — the first "
                        "option can't be selected. Set an explicit non-None default.",
                        "troubleshooting.md#first-radio-option-cant-be-selected",
                    )
                )
    return violations


def check_mutating_params(tree: ast.Module) -> list[Violation]:
    """`.append()` / subscript-assignment / `+=` on `self.<name>` where `<name>`
    has no leading underscore — the naming heuristic this codebase already
    uses for "this is a param, not a private widget/pane" (see panel/SKILL.md's
    method/attribute naming conventions). A leading-underscore attribute is
    assumed to be private instance state, not a watched param, so it's
    excluded to keep this check's noise down.

    `dict.update()` (the third in-place form reviewing-panel-apps.md names)
    is deliberately NOT checked here: `.update()` on `self.<attr>` is also the
    idiom for pushing new content into a `pn.pane.Placeholder` (see
    `_is_redraw_write` above) and is extremely common in correct code, so a
    bare "any `.update()` call on `self.<attr>`" rule would be dominated by
    false positives from that idiom rather than actual dict mutation.
    """
    violations = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and _is_self_attr(node.func.value)
            and not node.func.value.attr.startswith("_")
        ):
            violations.append(
                Violation(
                    node.lineno,
                    "MUTATING_PARAM_LIST",
                    f"In-place `.append()` on `self.{node.func.value.attr}` — won't trigger "
                    "watchers if this is a param. Reassign the whole list instead: "
                    f"`self.{node.func.value.attr} = self.{node.func.value.attr} + [item]`.",
                    "reviewing-panel-apps.md#mutating-instead-of-reassigning",
                )
            )
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Subscript)
                    and _is_self_attr(target.value)
                    and not target.value.attr.startswith("_")
                ):
                    violations.append(
                        Violation(
                            node.lineno,
                            "MUTATING_PARAM_ITEM",
                            f"In-place item assignment on `self.{target.value.attr}` — won't "
                            "trigger watchers if this is a param. Reassign the whole object "
                            "instead.",
                            "reviewing-panel-apps.md#mutating-instead-of-reassigning",
                        )
                    )
        # `self.items += [x]` — list.__iadd__ mutates in place *and* rebinds
        # the same object, so the param may see old-is-new and skip watchers.
        # Scoped to a container-literal RHS (list/tuple/set/comprehension) so
        # ordinary numeric accumulators (`self.counter += 1`) aren't flagged —
        # this tool has no type info, so RHS shape is the only signal available.
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.op, ast.Add)
            and isinstance(node.target, ast.Attribute)
            and _is_self_attr(node.target)
            and not node.target.attr.startswith("_")
            and isinstance(node.value, (ast.List, ast.Tuple, ast.Set, ast.ListComp, ast.SetComp))
        ):
            violations.append(
                Violation(
                    node.lineno,
                    "MUTATING_PARAM_AUGASSIGN",
                    f"`self.{node.target.attr} += ...` against a list/tuple/set literal — "
                    "list.__iadd__ mutates in place and rebinds the same object, so the "
                    "param may not detect a change and skip watchers. Reassign instead: "
                    f"`self.{node.target.attr} = self.{node.target.attr} + [...]`.",
                    "reviewing-panel-apps.md#mutating-instead-of-reassigning",
                )
            )
    return violations


def check_throttled(tree: ast.Module) -> list[Violation]:
    has_slider = False
    has_throttled = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name and name.endswith(SLIDER_SUFFIX):
                has_slider = True
            if name == "extension" and _kwarg_is(node, "throttled", True):
                has_throttled = True
        # pn.config.throttled = True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "throttled"
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "config"
                    and isinstance(node.value, ast.Constant)
                    and node.value.value is True
                ):
                    has_throttled = True
    if has_slider and not has_throttled:
        return [
            Violation(
                1,
                "MISSING_THROTTLED",
                "Sliders are used but throttled mode isn't set (`pn.extension(throttled=True)` "
                "or `pn.config.throttled = True`) — every drag pixel fires a callback instead "
                "of only on release.",
                "panel/SKILL.md#widgets-and-extensions",
            )
        ]
    return []


def lint_file(path: str) -> list[Violation]:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        return [Violation(e.lineno or 1, "SYNTAX_ERROR", str(e), "-")]
    violations: list[Violation] = []
    violations += check_function_level(tree)
    violations += check_dict_selector_objects(tree)
    violations += check_radio_default_none(tree)
    violations += check_mutating_params(tree)
    violations += check_throttled(tree)
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
