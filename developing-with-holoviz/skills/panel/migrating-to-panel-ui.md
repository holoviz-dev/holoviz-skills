# Migrating to Panel UI

This skill provides the steps and diffs for converting an existing plain-Panel app to `panel.ui`.

Migration is a presentation change, not a logic change: swap templates, widgets, and panes, but leave every `@param.depends`, `param.watch`, `pn.bind`, and periodic callback untouched. For how the target API works once you're there, see [Using Panel UI](using-panel-ui.md) (Page, layouts, component gotchas, palette, typography, icons). Do not restate those here.

## Contents

- [When to Migrate](#when-to-migrate)
- [Migration Checklist](#migration-checklist)
- [Imports and Extension](#imports-and-extension)
- [Template to Page](#template-to-page)
- [Widgets](#widgets)
- [Parameter Names](#parameter-names)
- [Panes](#panes)
- [Layouts](#layouts)
- [Styling](#styling)
- [Interaction Upgrades](#interaction-upgrades)
- [Consider New Components](#consider-new-components)
- [What Not to Migrate](#what-not-to-migrate)
- [Gotchas](#gotchas)
- [Verifying](#verifying)

## When to Migrate

- Migrate when the user wants an existing app to use `panel.ui` or a more modern look.
- For a brand-new app, skip this skill and build with [Using Panel UI](using-panel-ui.md) directly.
- Do imports + template + widgets together as one coherent pass — a half-migrated app usually won't serve.
- If you find yourself rewriting reactive wiring (`depends`, `watch`, `bind`), stop: migration changes presentation, not logic.

## Migration Checklist

Walk these in order; each keeps the app runnable:

1. **Imports & extension** — reference components as `pn.ui.X`, drop `template=`.
2. **Template → `pn.ui.Page`** — collapse template + `.servable()` calls into one Page.
3. **Widgets** — `pn.widgets.X` → `pn.ui.X`; `pn.Param(...)` → explicit `from_param`.
4. **Parameter names** — `name`→`label`, `button_type`→`color`, `button_style`→`variant`.
5. **Panes** — `pn.pane.Markdown` → `pn.ui.Typography`; `pn.pane.Alert` → `pn.ui.Alert` (the only pane swaps).
6. **Layouts** (optional) — `pn.Card/FlexBox` → `pn.ui` equivalents; leave `pn.Row`/`pn.Column` as they are.
7. **Styling** — keep `styles`; rewrite any `stylesheets` as `sx`.
8. **Interaction upgrades** (optional) — replace hand-rolled stateful controls with `panel.ui` widgets, and consider [new `panel.ui` components](#consider-new-components) that may serve better than the pattern you're carrying over.
9. **Verify** — serve and screenshot.

## Imports and Extension

- Import Panel once and reference Material components as `pn.ui.X`; there is no separate package import.
- Remove `template=` from `pn.extension()`; importing `pn.ui` selects its Material UI design unless an explicit design was already configured.
- Never add `"bokeh"` to `pn.extension()`; keep genuine JS extensions (`"tabulator"`, `"plotly"`, etc.).

```python
# BEFORE
pn.extension("tabulator", design="material", template="bootstrap", theme="dark")

# AFTER — `pn.ui.Page` replaces the template; `pn.ui` opts into its design
pn.extension("tabulator")
```

## Template to Page

- A template plus scattered `.servable()` calls collapse into a single `pn.ui.Page`.
- `sidebar`, `main`, and `header` take **lists** — a bare component fails silently.
- The title moves to `Page.title`.
- Dark mode and the light/dark switch are built in — delete manual theme plumbing.
- For Page rules (single-row header, centering, when to skip the sidebar), see [Using Panel UI](using-panel-ui.md).

```python
# BEFORE — FastListTemplate
tmpl = pn.template.FastListTemplate(title="My App", theme="dark")
tmpl.sidebar.append(controls)
tmpl.main.append(view)
tmpl.servable()

# BEFORE — per-component .servable(area=...)
controls.servable(area="sidebar")
view.servable(title="My App")

# AFTER — one Page
pn.ui.Page(
    title="My App",
    sidebar=[controls],
    main=[view],
    theme_toggle=True,   # built in — no manual light/dark wiring
).servable()
```

## Widgets

- `panel.ui` provides Material components and re-exports classic components that have no Material equivalent. Swap only when a Material component improves the presentation: `pn.widgets.X` → `pn.ui.X`. Use `hasattr(pn.ui, "X")` to confirm a name.
- `pn.widgets.ButtonIcon` maps to `pn.ui.IconButton` when a Material icon button is wanted; otherwise `pn.ui.ButtonIcon` preserves the classic widget.
- Replace an auto-generated `pn.Param(obj.param)` panel with explicit `ui.*.from_param(...)` so you control each widget's label, color, and visibility.
- `.from_param()` syncs value, bounds, and objects.
- **Caveat:** `.from_param()` widgets must be created *after* `super().__init__()` — see [panel/SKILL.md](SKILL.md#viewer-class-pattern) for the ordering rule.
- For which `panel.ui` widget matches each Param type, see [Using Panel UI](using-panel-ui.md#key-differences-from-panel).

```python
# BEFORE — auto-generated widget panel
controls = pn.Param(self.param)

# AFTER — explicit `panel.ui` widgets
self._radius = pn.ui.IntSlider.from_param(self.param.radius, label="Radius")
self._mode   = pn.ui.Select.from_param(self.param.mode, label="Mode")
controls = pn.Column(self._radius, self._mode)
```

## Parameter Names

`panel.ui` prefers the new parameter names. Legacy aliases still work, but update them while you're in the code:

| Legacy (Panel) | Modern (`panel.ui`) |
|----------------|---------------|
| `name=`        | `label=`      |
| `button_type=` | `color=`      |
| `button_style=`| `variant=`    |

**The rename is not mechanical**, and neither is assuming a param exists at all — on
`RadioButtonGroup`/`CheckButtonGroup` there is no `variant` to rename *to*, so the sweep
converts working code into a `TypeError`. Check with `'variant' in pn.ui.X.param` as you go;
the params that trip this are tabled in
[Troubleshooting](troubleshooting-panel-apps.md#typeerror-unexpected-keyword-argument-panelui-params-arent-universal).

## Panes

- Panes are mostly **not** migrated — the opposite of widgets. `panel.ui` is not a plotting or data-display library, so it ships almost no pane equivalents.
- Two swaps are worth making:
  - **Text:** `pn.pane.Markdown` → `pn.ui.Typography`. Typography renders markdown, so headings and bullet lists carry over unchanged; use `variant=` (`h4`, `body2`, …) for Material text styling.
  - **Alerts:** `pn.pane.Alert` → `pn.ui.Alert`. **Note: `pn.ui.Alert` is technically a layout, not a pane** — it lives in `reference/layouts/`, takes positional children like other `panel.ui` layouts (`pn.ui.Alert("...", severity="warning")`), and can wrap arbitrary content rather than just a string. So you'll find it under Layouts, not Panes, when you look it up.
- Everything else can stay `pn.pane.*` or move to its re-export in `ui.*`. Prefer `pn.pane.*` for explicit legacy pane types. They drop into `pn.ui.Page` and `ui` layouts untouched, and pick up theme-aware styling automatically inside a Page (see [Using Panel UI](theming-panel-ui.md#chart-theming) for plot theming):
  - **Plot panes:** `pn.pane.HoloViews`, `pn.pane.DeckGL`, `pn.pane.ECharts`, `pn.pane.Plotly`, `pn.pane.Matplotlib`, `pn.pane.Bokeh`, `pn.pane.Vega`.
  - **Media / embed:** `pn.pane.Image`, `pn.pane.Audio`, `pn.pane.Video`, `pn.pane.HTML`, `pn.pane.IFrame`.
  - **Data displays:** `pn.pane.DataFrame`, `pn.widgets.Tabulator`.

```python
# BEFORE
pn.pane.Markdown("## Overview\n\n- point a\n- point b")

# AFTER
pn.ui.Typography("## Overview\n\n- point a\n- point b")
```

## Layouts

- `pn.Row`/`pn.Column` → `pn.ui.Row`/`pn.ui.Column`, so the migrated app uses one namespace. Skip this for the layout directly wrapping a tile/geo plot, which must stay native ([tile plot renders blank](troubleshooting-panel-apps.md#tilemap-plot-renders-blank-inside-a-panelui-layout)).
- `pn.ui.Grid` is the Material 12-column **responsive** grid (breakpoint-based), **not** a drop-in for `pn.GridSpec`/`GridStack` coordinate placement (`gspec[0, 0] = ...`). Those have no direct `panel.ui` analog — keep them or rebuild against `pn.ui.Grid`'s breakpoint model.
- `pn.Card` → `pn.ui.Card` (prefer `pn.ui.Paper` for plain grouping); `pn.FlexBox` → `pn.ui.FlexBox`.
- `pn.Modal`/`pn.layout.Modal` → `pn.ui.Dialog` (there is no `pn.ui.Modal`); use `pn.ui.Drawer` for a side panel.
- Optional: if the existing app nests `pn.*` layouts heavily and they work, leave them — migrating layouts is low-value churn.
- `panel.ui` layouts take positional args: `pn.ui.Paper(a, b)`, not `pn.ui.Paper([a, b])`.
- **Sizing carries over unchanged:** `width`, `height`, `sizing_mode`, and `min_*`/`max_*` work identically on both APIs — copy them across, don't "translate".

```python
# BEFORE
pn.Column(pn.Card(chart, title="Chart"), sizing_mode="stretch_both")

# AFTER — sizing params unchanged
pn.ui.Column(pn.ui.Card(chart, title="Chart"), sizing_mode="stretch_both")
```

## Styling

- **`styles` carries over as-is.** It styles a component's *outer container* (spacing, border, background, shadow) and behaves the same on both APIs.
- **`stylesheets` does not carry over.** Classic widgets use `stylesheets=[css]` to reach *internal* DOM (`.noUi-handle`, `.noUi-connect`) — Panel's Bokeh markup. `panel.ui` renders entirely different Material UI DOM, so that CSS silently does nothing. Rewrite it as `sx` targeting MUI slots.
- Don't hand-port colors and fonts widget by widget when a single app-wide `theme_config` will do — see [Using Panel UI](using-panel-ui.md).

```python
# BEFORE — classic Panel, internals via stylesheets
pn.widgets.FloatSlider(
    name="Score",
    stylesheets=[".noUi-handle { border-radius: 50%; } .noUi-connect { background: #0b6bcb; }"],
)

# AFTER — `panel.ui`, internals via sx + MUI slot selectors
pn.ui.FloatSlider(
    label="Score",
    sx={
        "& .MuiSlider-thumb": {"borderRadius": "50%"},
        "& .MuiSlider-track": {"backgroundColor": "#0b6bcb"},
    },
)
```

## Interaction Upgrades

- Migration is a good moment to replace a hand-rolled stateful control with a purpose-built `panel.ui` widget — but only when it *removes* code.
- Classic case: a play/pause built from a `param.Event` whose button label you flip manually becomes a `pn.ui.Toggle`, whose boolean `value` *is* the state, dropping the bespoke `_playing` flag.
- Skip these when they'd complicate things — they're polish, not required for a correct migration.

```python
# BEFORE — Event + manual label/state flipping
play = param.Event(label="▷")
...
def _toggle(self, *_):
    if self._playing:
        self._cb.stop(); self._btn.name = "▷"
    else:
        self._cb.start(); self._btn.name = "❚❚"
    self._playing = not self._playing

# AFTER — Toggle; value is the state
self._play = pn.ui.Toggle(label="Play", icon="play_arrow")
self._play.param.watch(self._on_play, "value")

def _on_play(self, event):
    self._cb.start() if event.new else self._cb.stop()
```

## Consider New Components

`panel.ui` ships components that plain Panel never had. These aren't swaps — there's nothing to replace — but a migration is the natural moment to ask whether a purpose-built component would serve better than the pattern you're carrying over. Reach for them only when they *simplify* the app; don't add UI for its own sake.

- **`pn.ui.Dialog` / `pn.ui.Drawer`** — modal dialogs and slide-out panels. Beyond replacing `pn.Modal`, a `Drawer` is often a cleaner home for secondary controls than a permanently visible sidebar.
- **`pn.ui.Rating`, `pn.ui.Chip` / `pn.ui.Pill` / `pn.ui.MultiPill`** — first-class inputs for star ratings and tag/selection chips that people otherwise fake with buttons or multi-selects.
- **`pn.ui.SpeedDial`, `pn.ui.SplitButton`, `pn.ui.Fab`** — compact action menus and floating actions that replace clusters of buttons.
- **Navigation menus — `pn.ui.Breadcrumbs`/`NestedBreadcrumbs`, `pn.ui.Pagination`, `pn.ui.Tree`, `pn.ui.TabMenu`, `pn.ui.StepperMenu`, `pn.ui.MenuList`** — for paged tables, hierarchical data, or multi-step flows previously hand-wired with callbacks.
- **`pn.ui.Avatar`, `pn.ui.Badge`, `pn.ui.Skeleton`, `pn.ui.Tooltip`** — small polish (user chips, count badges, loading placeholders, hover hints). `Skeleton` is a top-level component; `Badge`/`Tooltip`/`Transition` apply via the wrapper API rather than as standalone constructors.
- **`pn.ui.ThemeToggle`, `pn.ui.BreakpointSwitcher`** — standalone versions of behavior `Page` exposes via `theme_toggle=True`; useful when you're not using `Page` or want the control placed manually.

Browse `reference/{section}/index.md` (especially `menus/` and `wrappers/`, which have no Panel analog) before reimplementing something by hand.

## What Not to Migrate

Some `pn.*` objects are re-exported unchanged by `panel.ui`; keeping their original namespace is clearer:

- **Plot / data panes** — use `pn.pane.*` / `pn.widgets.Tabulator` for the explicit classic names (see [Panes](#panes) for the full list, including media/embed).
- **Classic widgets and indicators** — `panel.ui` re-exports them, but they retain classic behavior. Use `pn.widgets.*` or `pn.indicators.*` when a Material replacement is not intended.
- **Spacers and low-level layout helpers** — keep `pn.layout.HSpacer` and `pn.layout.VSpacer` for clarity.
- **All reactive wiring** — `@param.depends`, `param.watch`, `pn.bind`, `pn.state.add_periodic_callback`.

If unsure whether a `panel.ui` name exists, confirm with `hasattr(pn.ui, "X")` or `dir(pn.ui)`, then use Panel's API reference per the Lookup in [Using Panel UI](using-panel-ui.md) rather than guessing a class name.

## Gotchas

- **Duplicate icon.** `panel.ui` buttons and toggles take a Material `icon=`. If you also leave a glyph (`▷`, `❚❚`) in the label, you get two icons. Pick one — usually the Material `icon=`.
- **Typography vs Markdown.** `pn.ui.Typography` renders markdown, so swapping headings, labels and KPI text to it is lossless and gains `variant=` styling. `pn.ui.Markdown` (the classic pane, re-exported) remains fine for long-form prose and reactive text references; don't churn it just to change namespaces.
- **`stylesheets` silently no-ops on ui.** The CSS targets Panel's old DOM, not MUI slots. Rewrite as `sx` (see [Styling](#styling)); `styles` is safe to keep.
- **`design='material'` is not `panel.ui`.** It selects Panel's older Material design. Let importing `pn.ui` select the new design unless the app deliberately configures another design.
- **Delete manual dark/light toggles.** `Page(theme_toggle=True)` replaces them.

## Verifying

- Use the serve → screenshot → debug loop in [Iterating on Panel Apps](iterating-on-panel-apps.md).
