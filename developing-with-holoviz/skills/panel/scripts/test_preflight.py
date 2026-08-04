"""Tests for preflight.py.

Fixtures are the exact WRONG/CORRECT code pairs already published in
reviewing-panel-apps.md and troubleshooting.md, so this suite doubles as "does
the lint tool agree with the docs it enforces": a rule that doesn't fire on its
own documented WRONG example, or fires on its CORRECT one, is a bug in the rule.

Run from this directory: `python test_preflight.py` (imports the sibling
`preflight` module by plain name, so it must be run from inside `scripts/`,
not from an arbitrary cwd). No pytest required, though `pytest test_preflight.py`
also works.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import preflight

# ---------------------------------------------------------------------------
# Fixtures — copied verbatim from reviewing-panel-apps.md / troubleshooting.md
# ---------------------------------------------------------------------------

CASES: dict[str, dict[str, str]] = {
    "flicker_recreated_layout": {
        "wrong": """
import param
import panel_material_ui as pmui

class C:
    @param.depends("active_step")
    def _nav_buttons(self):
        return pmui.Row(self._back_btn, self._next_btn)
""",
        "correct": """
import param
import panel_material_ui as pmui

class C:
    def __init__(self, **params):
        self._nav_row = pmui.Row(self._back_btn, self._next_btn)
        super().__init__(**params)
""",
        "check": "FLICKER_RECREATED_LAYOUT",
    },
    "watch_vs_depends_misuse": {
        "wrong": """
import param
import pandas as pd

class C:
    @param.depends("query", watch=True)
    def results_view(self):
        return pd.DataFrame(self._run_query())
""",
        "correct": """
import param

class C:
    @param.depends("query", watch=True, on_init=True)
    def _run_query(self):
        self.result = execute(self.query)

    @param.depends("result")
    def results_view(self):
        return f"{len(self.result)} rows"
""",
        "check": "WATCH_RETURNS_VALUE",
    },
    "from_param_before_super": {
        "wrong": """
import panel_material_ui as pmui

class C:
    def __init__(self, **params):
        self._toggle = pmui.RadioButtonGroup.from_param(self.param.chart_type)
        super().__init__(**params)
""",
        "correct": """
import panel_material_ui as pmui

class C:
    def __init__(self, **params):
        super().__init__(**params)
        self._toggle = pmui.RadioButtonGroup.from_param(self.param.chart_type)
""",
        "check": "FROM_PARAM_BEFORE_SUPER",
    },
    "missing_hold": {
        "wrong": """
class C:
    def _update(self):
        self._breadcrumbs.active = self.active_step
        self._next_btn.label = "Submit"
        self._content.update("x")
""",
        "correct": """
import panel as pn

class C:
    def _update(self):
        with pn.io.hold():
            self._breadcrumbs.active = self.active_step
            self._next_btn.label = "Submit"
            self._content.update("x")
""",
        "check": "MISSING_HOLD",
    },
    "mutating_instead_of_reassigning": {
        "wrong": """
class C:
    def add(self, item):
        self.items.append(item)
""",
        "correct": """
class C:
    def add(self, item):
        self.items = self.items + [item]
""",
        "check": "MUTATING_PARAM_LIST",
    },
    "dict_selector_objects": {
        "wrong": """
class C:
    def load(self, df):
        self.param.manufacturers.objects = {"Ford": "F", "GM": "G"}
""",
        "correct": """
class C:
    def load(self, df):
        self.param.manufacturers.objects = sorted(df["manufacturer"].unique().tolist())
""",
        "check": "DICT_SELECTOR_OBJECTS",
    },
    "radio_default_none": {
        "wrong": """
import panel_material_ui as pmui
w = pmui.RadioButtonGroup(options=["a", "b"], value=None)
""",
        "correct": """
import panel_material_ui as pmui
w = pmui.RadioButtonGroup(options=["a", "b"], value="a")
""",
        "check": "RADIO_DEFAULT_NONE",
    },
    "missing_throttled": {
        "wrong": """
import panel as pn
pn.extension()
w = pn.widgets.IntSlider(start=0, end=10)
""",
        "correct": """
import panel as pn
pn.extension(throttled=True)
w = pn.widgets.IntSlider(start=0, end=10)
""",
        "check": "MISSING_THROTTLED",
    },
}

# ---------------------------------------------------------------------------
# Regressions for the specific bugs found reviewing the first cut of this tool
# ---------------------------------------------------------------------------

REGRESSIONS: dict[str, dict[str, object]] = {
    "nested_closure_not_misattributed": {
        # A `return pmui.Row()` inside a nested function must not be blamed
        # on the enclosing @param.depends method (ast.walk-based traversal
        # used to leak into nested scopes here).
        "src": """
import param
import panel_material_ui as pmui

class C:
    @param.depends("x")
    def outer(self):
        def inner():
            return pmui.Row()
        inner()
        return self._cached
""",
        "expect_checks": set(),
    },
    "comparison_not_flagged_as_mutation": {
        # `==` inside an `if` must not match the subscript-assignment check.
        "src": """
class C:
    def f(self):
        if self.x[0] == 5:
            return True
""",
        "expect_checks": set(),
    },
    "docstring_text_not_scanned": {
        # A WRONG example quoted in a docstring must not fire the checks.
        "src": '''
def helper():
    """
    WRONG example:
        w = pmui.RadioButtonGroup(options=["a", "b"], value=None)
    """
''',
        "expect_checks": set(),
    },
    "multiline_call_still_caught": {
        # Anti-pattern split across lines (the common formatter output) must
        # still be caught — this used to be missed by line-scoped regexes.
        "src": """
import panel_material_ui as pmui
w = pmui.RadioButtonGroup(
    options=["a", "b"],
    value=None,
)
""",
        "expect_checks": {"RADIO_DEFAULT_NONE"},
    },
    "pn_depends_alias_matched": {
        "src": """
import panel as pn
import panel_material_ui as pmui

class C:
    @pn.depends("x")
    def bad(self):
        return pmui.Row()
""",
        "expect_checks": {"FLICKER_RECREATED_LAYOUT"},
    },
    "pn_config_throttled_recognized": {
        "src": """
import panel as pn
pn.config.throttled = True
w = pn.widgets.IntSlider(start=0, end=10)
""",
        "expect_checks": set(),
    },
    "private_attr_mutation_not_flagged": {
        # Leading-underscore attrs are this codebase's convention for private
        # instance state (not a watched param) — should stay quiet.
        "src": """
class C:
    def f(self):
        self._cache = {}
        self._cache[1] = 2
        self._private_list = []
        self._private_list.append(1)
""",
        "expect_checks": set(),
    },
    "async_watch_returns_value_caught": {
        # check_function_level used to filter on ast.FunctionDef only, so an
        # `async def` watcher returning a value sailed through entirely.
        "src": """
import param

class C:
    @param.depends("x", watch=True)
    async def bad(self):
        return 5
""",
        "expect_checks": {"WATCH_RETURNS_VALUE"},
    },
    "async_missing_hold_caught": {
        # Same gap, for the ungrouped-writes check.
        "src": """
class C:
    async def _update(self):
        self._a.value = 1
        self._b.value = 2
        self._c.update("x")
""",
        "expect_checks": {"MISSING_HOLD"},
    },
    "augassign_list_caught": {
        # self.items += [item] — list.__iadd__ mutates in place and rebinds
        # the same object, so the param may see old-is-new and skip watchers.
        # This used to pass silently: the AugAssign branch only checked
        # Subscript targets, not a plain Attribute target.
        "src": """
class C:
    def add(self, item):
        self.items += [item]
""",
        "expect_checks": {"MUTATING_PARAM_AUGASSIGN"},
    },
    "augassign_numeric_not_flagged": {
        # += on a plain number is normal (int has no __iadd__, so this is an
        # ordinary rebind that watchers see fine) — must not be flagged just
        # because the target shape matches the list case.
        "src": """
class C:
    def bump(self):
        self.counter += 1
""",
        "expect_checks": set(),
    },
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _lint_source(source: str) -> list[preflight.Violation]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return preflight.lint_file(path)
    finally:
        Path(path).unlink(missing_ok=True)


def run() -> int:
    failures: list[str] = []

    for name, case in CASES.items():
        check = case["check"]

        wrong_hits = {v.check for v in _lint_source(case["wrong"])}
        if check not in wrong_hits:
            failures.append(
                f"[{name}] WRONG fixture did not trigger {check} (got {wrong_hits or 'nothing'})"
            )

        correct_hits = {v.check for v in _lint_source(case["correct"])}
        if check in correct_hits:
            failures.append(f"[{name}] CORRECT fixture incorrectly triggered {check}")

    for name, case in REGRESSIONS.items():
        hits = {v.check for v in _lint_source(case["src"])}
        expected = case["expect_checks"]
        if hits != expected:
            failures.append(f"[{name}] expected checks {expected or 'none'}, got {hits or 'none'}")

    total = len(CASES) * 2 + len(REGRESSIONS)
    passed = total - len(failures)
    print(f"{passed}/{total} passed")
    for f in failures:
        print(f"  FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
