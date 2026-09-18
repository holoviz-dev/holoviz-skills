# Reviewing Panel Apps

Checklist for reviewing Panel applications. Focus on anti-patterns that cause flickering, wasted redraws, or subtle bugs. For general code style (imports, naming, param ordering), see also the [cleanup](../../../contributing-to-holoviz/skills/cleanup/SKILL.md) skill — note this reference is only available if the `contributing-to-holoviz` skill category is also installed alongside `developing-with-holoviz`, since the two ship as separate plugin artifacts. For a complete example that applies all these patterns, see `examples/wizard.py`.

This checklist operationalizes Panel's official best-practices guides for review; consult them for upstream rationale and additional patterns (graceful exception handling, `obj.param.update`, `FlexBox` layouts): [Developer Experience](https://panel.holoviz.org/how_to/best_practices/dev_experience.html) and [User Experience](https://panel.holoviz.org/how_to/best_practices/user_experience.html).

## Contents

- [Flickering from Recreated Components](#flickering-from-recreated-components)
- [Missing Hold on Multi-Property Updates](#missing-hold-on-multi-property-updates)
- [Watcher Dependency Gaps](#watcher-dependency-gaps)
- [Reactive Wiring: Prefer Declarative](#reactive-wiring-prefer-declarative)
- [from_param Widgets Created Before super()](#from_param-widgets-created-before-super)
- [Unintended Stretch and Collapsed Labels](#unintended-stretch-and-collapsed-labels)
- [Spacer vs Margin](#spacer-vs-margin)
- [Mutating Instead of Reassigning](#mutating-instead-of-reassigning)
- [Watch vs Depends Misuse](#watch-vs-depends-misuse)
- [Component Gotchas](#component-gotchas)
- [UX Heuristics](#ux-heuristics)

## Flickering from Recreated Components

The most common Panel anti-pattern. A `@param.depends` method that returns a new layout or widget on every call causes the entire component to be torn down and rebuilt, producing visible flicker.

```python
# WRONG — recreates Row on every step change
@param.depends("active_step")
def _nav_buttons(self):
    return pn.Row(self._back_btn, pn.layout.HSpacer(), self._next_btn)

# CORRECT — create once in __init__, reference in layout
def __init__(self, **params):
    self._nav_row = pn.Row(self._back_btn, pn.layout.HSpacer(), self._next_btn)
    super().__init__(**params)
```

**What to look for**: any `@param.depends` method (without `watch=True`) that returns `pn.Column`, `pn.Row`, `pmui.Paper`, or any layout/widget constructor. The fix is always the same — create once, update properties.

For content that genuinely varies in type (string one moment, plot the next), use `pn.pane.Placeholder`:

```python
# WRONG — recreates widget on every toggle
@param.depends("mode")
def _details(self):
    if self.mode == "A":
        return pmui.FloatInput.from_param(self.param.amount)
    return pmui.Typography("No input needed")

# CORRECT — create both once, swap via Placeholder
def __init__(self, **params):
    self._amount_input = pmui.FloatInput.from_param(self.param.amount)
    self._no_input_msg = pmui.Typography("No input needed")
    self._details = pn.pane.Placeholder()
    super().__init__(**params)

@param.depends("mode", watch=True, on_init=True)
def _update_details(self):
    if self.mode == "A":
        self._details.update(self._amount_input)
    else:
        self._details.update(self._no_input_msg)
```

## Missing Hold on Multi-Property Updates

A watcher that assigns to 3+ widget properties without batching triggers a separate redraw per assignment. Wrap in `pn.io.hold()` — see [panel/SKILL.md](SKILL.md#performance) for the pattern.

**What to look for**: any watcher that assigns to 3+ widget properties without `pn.io.hold()`. Two assignments are borderline; three or more should always be held.

## Watcher Dependency Gaps

A watcher that lists only some of the parameters it logically depends on. The method runs when one parameter changes but not the other, leaving the UI out of sync.

```python
# WRONG — interest changes don't update complete status
@param.depends("wages", watch=True)
def _on_income_change(self):
    self.complete = self.wages > 0

# CORRECT — watch all inputs that affect the result
@param.depends("wages", "interest", watch=True)
def _on_income_change(self):
    self.complete = (self.wages + self.interest) > 0
```

**What to look for**: read every `self.param_name` inside the method body and verify it appears in the `@param.depends` decorator. Missing dependencies are silent — no error, just stale state.

## Reactive Wiring: Prefer Declarative

Prefer declarative wiring; reach for imperative `.param.watch()` only as a last resort. The full priority ladder — `@param.depends` → `@param.depends(watch=True)` → `pn.bind(..., watch=True)` → `.param.watch()`, every `watch=True` form being side-effects-only — is defined in the [param skill](../param/SKILL.md#watch-vs-paramdepends-vs-link).

**What to look for**: a `.param.watch()` doing what a declarative `pn.bind(fn, other.param.x, watch=True)` or `@param.depends` would do just as well. A plain bind receives the value directly (no `event` unpacking), so it's usually clearer:

```python
# ⚠️ imperative — reserve for .old/.new or runtime wiring
self._nav_menu.param.watch(self._on_menu_select, "active")
# ✅ declarative — fn receives the value
pn.bind(self._on_menu_select, self._nav_menu.param.active, watch=True)
```

## from_param Widgets Created Before super()

`.from_param()` widgets created before `super().__init__(**params)` have watchers that silently never fire — see [panel/SKILL.md](SKILL.md#viewer-class-pattern) for the full ordering rule.

**What to look for**: a `.from_param()` widget assigned *before* `super().__init__()` whose `@param.depends(..., watch=True)` "isn't firing" — move it below `super()`. Symptom, cause, and the WRONG/CORRECT fix: [Troubleshooting Panel Apps](troubleshooting-panel-apps.md#widgets-change-but-nothing-updates-init-ordering).

## Unintended Stretch and Collapsed Labels

Under the default `sizing_mode="stretch_width"`, fixed-size widgets stretch to fill their container. Icon widgets like `Rating` render enormous, and inline `Markdown`/`HTML` labels placed in a `Row` alongside `HSpacer`s collapse to near-zero width and wrap one character per line. The fix — pinning `width` plus `sizing_mode="fixed"` — is in [Using Material UI](using-material-ui.md#components).

**What to look for**: `Rating`, small buttons, or text labels inside a stretched `Row`/`Column` without an explicit `width`/`sizing_mode="fixed"`.

## Spacer vs Margin

`pn.Spacer(height=N)` creates a real component in the DOM. Margin or padding on the parent achieves the same visual gap without an extra element.

```python
# WRONG — extra DOM element just for spacing
pn.Column(
    self._content,
    pn.Spacer(height=30),
    self._nav_row,
)

# CORRECT — margin on parent
pn.Column(
    self._content,
    self._nav_row,
    margin=(0, 0, 30, 0),
)
```

`pn.layout.HSpacer()` and `pn.layout.VSpacer()` are fine — they're flexbox spacers that push siblings apart, which margin can't replicate.

## Mutating Instead of Reassigning

In-place operations on param values (`list.append()`, `dict.update()`, `+=` on lists) don't trigger watchers, so dependents go stale with no error. Mechanism and the reassignment idioms: [param skill](../param/SKILL.md#parameter-types).

**What to look for**: any `self.<param>.append(...)`, `self.<param>[key] = ...`, or `self.<param> +=` where the param has a watcher or a `@param.depends` reader. Rewrite as a whole-object assignment.

## Watch vs Depends Misuse

`@param.depends("x", watch=True)` is for side effects — updating another param, syncing state, calling an API. It should not return content for display.

`@param.depends("x")` (without `watch`) is for lazy rendering — it returns content and is called only when something reads the result. It should not have side effects.

```python
# WRONG — watch=True returning content (never displayed)
@param.depends("query", watch=True)
def results_view(self):
    return pn.pane.DataFrame(self._run_query())

# WRONG — no watch, but has side effects (runs unpredictably)
@param.depends("query")
def results_view(self):
    self.status = "loading"  # side effect!
    return pn.pane.DataFrame(self._run_query())

# CORRECT — watch for side effect, depends for display
@param.depends("query", watch=True, on_init=True)
def _run_query(self):
    self.result = execute(self.query)

@param.depends("result")
def results_view(self):
    return f"**{len(self.result)} rows**"
```

## Component Gotchas

Per-component traps that produce silent bugs rather than errors. Grep for the pattern in review; each cause and fix lives in [Troubleshooting Panel Apps](troubleshooting-panel-apps.md):

- `RadioBoxGroup`/`RadioButtonGroup` constructed with `default=None` → [first radio option can't be selected](troubleshooting-panel-apps.md#first-option-cant-be-selected-selection-widget-with-defaultnone)
- A **dict** assigned to a `Selector`'s `.objects` → [Select renders blank](troubleshooting-panel-apps.md#select-renders-blank-after-setting-objects)
- A date-widget value compared directly against a DataFrame column → [date filter returns nothing](troubleshooting-panel-apps.md#date-filter-returns-nothing-type-error)
- `pn.pane.Markdown` containing headers → [header flickers on hover](troubleshooting-panel-apps.md#markdown-header-flickers-on-hover)

## UX Heuristics

Layout and interaction patterns for data apps and interactive tools:

- **Context before controls**: show the data a control acts on *before* the control itself — users shouldn't scroll back up to act after scrolling down to look. Applies to forms, dashboards, and review screens alike.
- **Neutral defaults for captured input**: don't preselect an answer the user is meant to provide, and keep submit disabled until they choose — a default silently skews the data. (See the radio `default=None` gotcha above; a directly-created widget makes an unset state real.)
- **Group controls with what they affect**: place action controls adjacent to their content rather than in a distant sidebar.

### Dashboard Layout Patterns

**Sidebar vs full-width.** A sidebar works well for persistent controls (filters, navigation, settings) that the user references while viewing the main content. It works poorly when the sidebar holds a data table that duplicates or competes with the main view — both end up too narrow. If the sidebar content is a different *view* of the same data (a leaderboard next to a map), consider giving each its own tab instead.

**Search-first landing pages.** If the app's primary action is a search, the landing page IS the search. Full-viewport hero with centered content: brand badge → title → search bar (wider than the title) → example-query chips → teaser stat. No empty chart placeholders, no "Connecting..." text. Use a dark background with subtle CSS grid watermark for texture.

**KPI ledger, not cards.** A single horizontal strip with `flex: 1 1 0` cells, separated by hairline borders. No shadows, no individual card backgrounds. Typography hierarchy within each cell: label (serif, small, muted) → value (sans, large, accent color, `tabular-nums`) → caption (small, muted). Avoid monospace for values — system sans with `letter-spacing: -0.02em` and `font-variant-numeric: tabular-nums` gives alignment without the Courier look.

**Tab order = perceived performance.** Put the lightest tab first. An ECharts bar chart (~0.03s) as the default tab, with the datashader map (2–7s) on a secondary tab, makes the app feel instant even though the heaviest component hasn't loaded.

**Horizontal bars over donuts.** A donut with 50 slices is decoration. A sorted horizontal bar chart with inline count labels is scannable at a glance.

**Table design.** Decode codes (FIPS → state name). Add computed columns (geodesic length, lat/lon centroid). Sort by the most interesting column (longest streets first), not database order. Use `layout="fit_data_stretch"` on Tabulator to avoid percentage-width fights inside Tabs.

**Two accent colors.** Structural accent (dark green: header, active tab, focus rings) + data accent (amber: KPI values, chart bars, map density colormap). Everything else neutral. Match the Bokeh plot `bgcolor` to the page background so the map frame disappears.

**Empty/loading states.** Pre-search: the landing page is the empty state. During search: "Searching..." in the header, spinners on panes (`loading_spinner="arc"`, `loading_color` to data accent). KPIs show dashes ("—") until phase 1 completes. Map shows bare basemap (renders instantly) until phase 2 overlays data.
