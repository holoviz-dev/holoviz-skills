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
analysis, so a helper method only ever called from inside a caller's own
`with pn.io.hold():` block is still flagged (hold is reentrant, so that's fine
as written) — read the flagged line before editing.
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
WITH_NODES = (ast.With, ast.AsyncWith)
BRANCHING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.TryStar)
MIN_UNGROUPED_WRITES = 3  # below this, batching under pn.io.hold() isn't worth it
FuncDef = ast.FunctionDef | ast.AsyncFunctionDef
CONTAINER_LITERAL_NODES = ast.List | ast.Tuple | ast.Set | ast.ListComp | ast.SetComp


@dataclass
class Violation:
    line: int
    check: str
    message: str
    doc: str

    def format(self, path: str) -> str:
        return f"{path}:{self.line}: [{self.check}] {self.message} (see {self.doc})"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def iter_own_scope(node: ast.AST):
    """DFS over *node*'s descendants, without crossing into a nested scope.

    Unlike `ast.walk`, this stops descending at a nested FunctionDef/
    AsyncFunctionDef/Lambda/ClassDef, so a `return` or a call inside a nested
    helper is never attributed to the enclosing function.
    """
    stack = list(ast.iter_child_nodes(node))
    while stack:
        child = stack.pop()
        yield child
        if isinstance(child, SCOPE_NODES):
            continue
        stack.extend(ast.iter_child_nodes(child))


def _call_name(node: ast.AST) -> str | None:
    """Trailing name of a Call's func, e.g. `pmui.Row(...)` -> 'Row'."""
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
    """The Call node if *dec* is a call to `depends`.

    Matched on the trailing attribute/name only, so `@param.depends(...)`,
    `@pn.depends(...)` (Panel's re-export), and a bare `@depends(...)` from
    `from param import depends` all qualify.
    """
    if isinstance(dec, ast.Call) and _call_name(dec) == "depends":
        return dec
    return None


def _kwarg_is(call: ast.Call, kwarg: str, value) -> bool:
    return any(
        kw.arg == kwarg and isinstance(kw.value, ast.Constant) and kw.value.value is value
        for kw in call.keywords
    )


def _returns_layout_constructor(func: FuncDef) -> ast.Return | None:
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


def _from_param_lines_before(func: FuncDef, boundary_line: int) -> list[int]:
    return [
        node.lineno
        for node in iter_own_scope(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_param"
        and node.lineno < boundary_line
    ]


def _is_hold_context(node: ast.With | ast.AsyncWith) -> bool:
    return any(
        isinstance(item.context_expr, ast.Call) and _call_name(item.context_expr) == "hold"
        for item in node.items
    )


def _sub_bodies(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """Statement lists nested directly inside a branching statement."""
    bodies = [
        body for attr in ("body", "orelse", "finalbody") if (body := getattr(stmt, attr, None))
    ]
    return bodies + [handler.body for handler in getattr(stmt, "handlers", [])]


def _is_redraw_write(stmt: ast.stmt) -> bool:
    """True if *stmt* is a property write Panel would redraw on.

    Either `x.y = ...` where `x` is itself an attribute (e.g.
    `self._widget.value =`), or `.update(...)` on such an attribute (the
    Placeholder/pane idiom, e.g. `self._content.update(step)`) — a method call
    rather than an assignment, but the same redraw-per-call cost `pn.io.hold()`
    exists to batch.
    """
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


def _ungrouped_redraw_writes(func: FuncDef) -> list[ast.stmt]:
    """Redraw-triggering writes in *func* that aren't inside a `pn.io.hold()`."""
    hits: list[ast.stmt] = []

    def walk(body: list[ast.stmt], inside_hold: bool) -> None:
        for stmt in body:
            if isinstance(stmt, WITH_NODES):
                walk(stmt.body, inside_hold or _is_hold_context(stmt))
            elif isinstance(stmt, BRANCHING_NODES):
                for sub in _sub_bodies(stmt):
                    walk(sub, inside_hold)
            elif not inside_hold and _is_redraw_write(stmt):
                hits.append(stmt)

    walk(func.body, False)
    return hits


# ---------------------------------------------------------------------------
# Checks — each takes the parsed module and returns its violations
# ---------------------------------------------------------------------------


def _check_depends(func: FuncDef) -> list[Violation]:
    depends = next(
        (call for dec in func.decorator_list if (call := _decorator_depends_call(dec))), None
    )
    if depends is None:
        return []

    if _kwarg_is(depends, "watch", True):
        ret = _returns_nonnull_value(func)
        if ret is None:
            return []
        return [
            Violation(
                ret.lineno,
                "WATCH_RETURNS_VALUE",
                f"`{func.name}` is @param.depends(..., watch=True) but returns a value — "
                "watch=True is for side effects (won't be displayed anywhere); split into "
                "a watch=True updater plus a plain @param.depends view method.",
                "reviewing-panel-apps.md#watch-vs-depends-misuse",
            )
        ]

    ret = _returns_layout_constructor(func)
    if ret is None:
        return []
    return [
        Violation(
            ret.lineno,
            "FLICKER_RECREATED_LAYOUT",
            f"`{func.name}` is @param.depends (no watch=True) and returns a layout/widget "
            "constructor — recreates it on every dependency change, causing flicker. Create "
            "once in __init__, update properties or use pn.pane.Placeholder instead.",
            "reviewing-panel-apps.md#flickering-from-recreated-components",
        )
    ]


def _check_from_param_before_super(func: FuncDef) -> list[Violation]:
    boundary = _find_super_init_line(func)
    if boundary is None:
        return []
    return [
        Violation(
            line,
            "FROM_PARAM_BEFORE_SUPER",
            ".from_param() widget created before super().__init__() — its watchers/"
            "@param.depends will silently never fire. Move it after super().__init__().",
            "reviewing-panel-apps.md#from_param-widgets-created-before-super",
        )
        for line in _from_param_lines_before(func, boundary)
    ]


def _check_missing_hold(func: FuncDef) -> list[Violation]:
    hits = _ungrouped_redraw_writes(func)
    if len(hits) < MIN_UNGROUPED_WRITES:
        return []
    return [
        Violation(
            hits[0].lineno,
            "MISSING_HOLD",
            f"`{func.name}` makes {len(hits)} ungrouped widget/pane property assignments — "
            "wrap in `with pn.io.hold(): ...` to batch into one redraw. Known false-positive "
            "case: if every call site already wraps the call to this method in "
            "`pn.io.hold()`, this is fine as-is (hold is reentrant) — this check has no "
            "cross-function call-site analysis, so verify the callers before editing.",
            "panel/SKILL.md#performance",
        )
    ]


def check_function_level(tree: ast.Module) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, FuncDef):
            continue
        violations += _check_depends(node)
        if node.name == "__init__":
            violations += _check_from_param_before_super(node)
        else:
            violations += _check_missing_hold(node)
    return violations


def check_dict_selector_objects(tree: ast.Module) -> list[Violation]:
    return [
        Violation(
            node.lineno,
            "DICT_SELECTOR_OBJECTS",
            "A dict assigned to a Selector's .objects — renders blank. Use a list, or a dict "
            "passed to the Selector constructor's `objects=` kwarg instead.",
            "troubleshooting.md#select-renders-blank-after-setting-objects",
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
        for target in node.targets
        if isinstance(target, ast.Attribute) and target.attr == "objects"
    ]


def check_radio_default_none(tree: ast.Module) -> list[Violation]:
    return [
        Violation(
            node.lineno,
            "RADIO_DEFAULT_NONE",
            f"{_call_name(node)} constructed with a None default — the first option can't be "
            "selected. Set an explicit non-None default.",
            "troubleshooting.md#first-option-cant-be-selected-selection-widget-with-defaultnone",
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _call_name(node) in RADIO_GROUP_NAMES
        and (_kwarg_is(node, "value", None) or _kwarg_is(node, "default", None))
    ]


def check_mutating_params(tree: ast.Module) -> list[Violation]:
    """In-place mutation of `self.<name>` where `<name>` has no leading underscore.

    The underscore is this codebase's convention for "private instance state,
    not a watched param" (see panel/SKILL.md naming conventions), so excluding
    it keeps the noise down.

    `dict.update()` — the third in-place form reviewing-panel-apps.md names — is
    deliberately not checked: `.update()` on `self.<attr>` is also the idiom for
    pushing content into a `pn.pane.Placeholder` (see `_is_redraw_write`), so the
    rule would be dominated by false positives from that idiom.
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
            attr = node.func.value.attr
            violations.append(
                Violation(
                    node.lineno,
                    "MUTATING_PARAM_LIST",
                    f"In-place `.append()` on `self.{attr}` — won't trigger watchers if this "
                    f"is a param. Reassign the whole list instead: `self.{attr} = "
                    f"self.{attr} + [item]`.",
                    "reviewing-panel-apps.md#mutating-instead-of-reassigning",
                )
            )
        if isinstance(node, ast.Assign | ast.AugAssign):
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
        # Scoped to a container-literal RHS so ordinary numeric accumulators
        # (`self.counter += 1`) aren't flagged — there's no type info here, so
        # the RHS shape is the only available signal.
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.op, ast.Add)
            and isinstance(node.target, ast.Attribute)
            and _is_self_attr(node.target)
            and not node.target.attr.startswith("_")
            and isinstance(node.value, CONTAINER_LITERAL_NODES)
        ):
            attr = node.target.attr
            violations.append(
                Violation(
                    node.lineno,
                    "MUTATING_PARAM_AUGASSIGN",
                    f"`self.{attr} += ...` against a list/tuple/set literal — list.__iadd__ "
                    "mutates in place and rebinds the same object, so the param may not "
                    f"detect a change and skip watchers. Reassign instead: `self.{attr} = "
                    f"self.{attr} + [...]`.",
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
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            has_throttled = has_throttled or any(
                isinstance(target, ast.Attribute)
                and target.attr == "throttled"
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "config"
                and node.value.value is True
                for target in node.targets
            )
    if not (has_slider and not has_throttled):
        return []
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


def lint_file(path: str) -> list[Violation]:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        return [Violation(e.lineno or 1, "SYNTAX_ERROR", str(e), "-")]
    violations = [
        *check_function_level(tree),
        *check_dict_selector_objects(tree),
        *check_radio_default_none(tree),
        *check_mutating_params(tree),
        *check_throttled(tree),
    ]
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
