# Migrating to Material UI

This skill provides the steps and diffs for converting an existing plain-Panel app to panel-material-ui (pmui).

Migration is a presentation change, not a logic change: swap templates, widgets, and panes, but leave every `@param.depends`, `param.watch`, `pn.bind`, and periodic callback untouched. For how the target API works once you're there, see [Using Material UI](using-material-ui.md) (Page, layouts, component gotchas, palette, typography, icons) — don't restate those here.

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

- Migrate when the user wants an existing app to use Material UI / pmui, or a more modern look.
- For a brand-new app, skip this skill and build with [Using Material UI](using-material-ui.md) directly.
- Do imports + template + widgets together as one coherent pass — a half-migrated app usually won't serve.
- If you find yourself rewriting reactive wiring (`depends`, `watch`, `bind`), stop: migration changes presentation, not logic.

## Migration Checklist

Walk these in order; each keeps the app runnable:

1. **Imports & extension** — add `pmui`, drop `template=`/`design=`.
2. **Template → `pmui.Page`** — collapse template + `.servable()` calls into one Page.
3. **Widgets** — `pn.widgets.X` → `pmui.X`; `pn.Param(...)` → explicit `from_param`.
4. **Parameter names** — `name`→`label`, `button_type`→`color`, `button_style`→`variant`.
5. **Panes** — `pn.pane.Markdown` → `pmui.Typography`; `pn.pane.Alert` → `pmui.Alert` (the only pane swaps).
6. **Layouts** (optional) — `pn.Row/Column/Card/FlexBox` → `pmui` equivalents.
7. **Styling** — keep `styles`; rewrite any `stylesheets` as `sx`.
8. **Interaction upgrades** (optional) — replace hand-rolled stateful controls with pmui widgets, and consider [new pmui components](#consider-new-components) that may serve better than the pattern you're carrying over.
9. **Verify** — serve and screenshot.

## Imports and Extension

- Add `import panel_material_ui as pmui`.
- Remove `template=` and `design=` from `pn.extension()` — `pmui.Page` replaces templates and pmui owns the design system.
- Never add `"panel_material_ui"` or `"bokeh"` to `pn.extension()`; keep genuine JS extensions (`"tabulator"`, `"plotly"`, etc.).

```python
# BEFORE
pn.extension("tabulator", design="material", template="bootstrap", theme="dark")

# AFTER — design / template / theme are handled by pmui.Page
pn.extension("tabulator")
```

## Template to Page

- A template plus scattered `.servable()` calls collapse into a single `pmui.Page`.
- `sidebar`, `main`, and `header` take **lists** — a bare component fails silently.
- The title moves to `Page.title`.
- Dark mode and the light/dark switch are built in — delete manual theme plumbing.
- For Page rules (100px header, centering, when to skip the sidebar), see [Using Material UI](using-material-ui.md).

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
pmui.Page(
    title="My App",
    sidebar=[controls],
    main=[view],
    theme_toggle=True,   # built in — no manual light/dark wiring
).servable()
```

## Widgets

- Most common widgets have a pmui equivalent: swap `pn.widgets.X` → `pmui.X`. But not all — `CodeEditor`, `Terminal`, `JSONEditor`, `FileSelector`/`FileDropper`, `Player`/`DiscretePlayer`, `StaticText`, `ToggleGroup`, `ArrayInput`, and the `DataFrame` widget have **no** pmui class and stay `pn.widgets.*` (see [What Not to Migrate](#what-not-to-migrate)). Don't assume the swap exists — confirm with `hasattr(pmui, "X")`.
- `pn.widgets.ButtonIcon` migrates 1:1 to `pmui.ButtonIcon`, but `pmui.IconButton` is the idiomatic Material name if you're touching it anyway.
- Replace an auto-generated `pn.Param(obj.param)` panel with explicit `pmui.*.from_param(...)` so you control each widget's label, color, and visibility.
- `.from_param()` syncs value, bounds, and objects.
- **Caveat:** `.from_param()` widgets (button groups included) must be created *after* `super().__init__()`, or their `@param.depends`/watchers won't fire (see [Using Material UI](using-material-ui.md) and the [review checklist](reviewing-panel-apps.md#from_param-widgets-created-before-super)).
- For which pmui widget matches each Param type, see [Using Material UI](using-material-ui.md#key-differences-from-panel).

```python
# BEFORE — auto-generated widget panel
controls = pn.Param(self.param)

# AFTER — explicit pmui widgets
self._radius = pmui.IntSlider.from_param(self.param.radius, label="Radius")
self._mode   = pmui.Select.from_param(self.param.mode, label="Mode")
controls = pmui.Column(self._radius, self._mode)
```

## Parameter Names

pmui prefers the new parameter names. Legacy aliases still work, but update them while you're in the code:

| Legacy (Panel) | Modern (pmui) |
|----------------|---------------|
| `name=`        | `label=`      |
| `button_type=` | `color=`      |
| `button_style=`| `variant=`    |

## Panes

- Panes are mostly **not** migrated — the opposite of widgets. pmui is not a plotting or data-display library, so it ships almost no pane equivalents.
- Two swaps are worth making:
  - **Text:** `pn.pane.Markdown` → `pmui.Typography`. Typography renders markdown, so headings and bullet lists carry over unchanged; use `variant=` (`h4`, `body2`, …) for Material text styling.
  - **Alerts:** `pn.pane.Alert` → `pmui.Alert`. **Note: `pmui.Alert` is technically a layout, not a pane** — it lives in `reference/layouts/`, takes positional children like other pmui layouts (`pmui.Alert("...", severity="warning")`), and can wrap arbitrary content rather than just a string. So you'll find it under Layouts, not Panes, when you look it up.
- Everything else stays `pn.pane.*` — there is no pmui version and you should not invent one. They drop into `pmui.Page` and pmui layouts untouched, and pick up theme-aware styling automatically inside a Page (see [Using Material UI](using-material-ui.md#chart-theming) for plot theming):
  - **Plot panes:** `pn.pane.HoloViews`, `pn.pane.DeckGL`, `pn.pane.ECharts`, `pn.pane.Plotly`, `pn.pane.Matplotlib`, `pn.pane.Bokeh`, `pn.pane.Vega`.
  - **Media / embed:** `pn.pane.Image`, `pn.pane.Audio`, `pn.pane.Video`, `pn.pane.HTML`, `pn.pane.IFrame`.
  - **Data displays:** `pn.pane.DataFrame`, `pn.widgets.Tabulator`.

```python
# BEFORE
pn.pane.Markdown("## Overview\n\n- point a\n- point b")

# AFTER
pmui.Typography("## Overview\n\n- point a\n- point b")
```

## Layouts

- Swap `pn.Row`/`pn.Column` → `pmui.Row`/`pmui.Column` for spacing and theme inheritance. (`pmui.Row`/`Column`/`Divider` exist even though the reference index has no page for them — see the index caveat in [What Not to Migrate](#what-not-to-migrate).)
- `pmui.Grid` is the Material 12-column **responsive** grid (breakpoint-based), **not** a drop-in for `pn.GridSpec`/`GridStack` coordinate placement (`gspec[0, 0] = ...`). Those have no direct pmui analog — keep them or rebuild against `pmui.Grid`'s breakpoint model.
- `pn.Card` → `pmui.Card` (prefer `pmui.Paper` for plain grouping); `pn.FlexBox` → `pmui.FlexBox`.
- `pn.Modal`/`pn.layout.Modal` → `pmui.Dialog` (there is no `pmui.Modal`); use `pmui.Drawer` for a side panel.
- Optional: if the existing app nests `pn.*` layouts heavily and they work, leave them — migrating layouts is low-value churn.
- pmui layouts take positional args: `pmui.Row(a, b)`, not `pmui.Row([a, b])`.
- **Sizing carries over unchanged:** `width`, `height`, `sizing_mode`, and `min_*`/`max_*` work identically on both APIs — copy them across, don't "translate".

```python
# BEFORE
pn.Column(pn.Card(chart, title="Chart"), sizing_mode="stretch_both")

# AFTER — sizing params unchanged
pmui.Column(pmui.Card(chart, title="Chart"), sizing_mode="stretch_both")
```

## Styling

- **`styles` carries over as-is.** It styles a component's *outer container* (spacing, border, background, shadow) and behaves the same on both APIs.
- **`stylesheets` does not carry over.** Classic widgets use `stylesheets=[css]` to reach *internal* DOM (`.noUi-handle`, `.noUi-connect`) — Panel's Bokeh markup. pmui renders entirely different Material UI DOM, so that CSS silently does nothing. Rewrite it as `sx` targeting MUI slots.
- Don't hand-port colors and fonts widget by widget when a single app-wide `theme_config` will do — see [Using Material UI](using-material-ui.md).

```python
# BEFORE — classic Panel, internals via stylesheets
pn.widgets.FloatSlider(
    name="Score",
    stylesheets=[".noUi-handle { border-radius: 50%; } .noUi-connect { background: #0b6bcb; }"],
)

# AFTER — pmui, internals via sx + MUI slot selectors
pmui.FloatSlider(
    label="Score",
    sx={
        "& .MuiSlider-thumb": {"borderRadius": "50%"},
        "& .MuiSlider-track": {"backgroundColor": "#0b6bcb"},
    },
)
```

## Interaction Upgrades

- Migration is a good moment to replace a hand-rolled stateful control with a purpose-built pmui widget — but only when it *removes* code.
- Classic case: a play/pause built from a `param.Event` whose button label you flip manually becomes a `pmui.Toggle`, whose boolean `value` *is* the state, dropping the bespoke `_playing` flag.
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
self._play = pmui.Toggle(label="Play", icon="play_arrow")
self._play.param.watch(self._on_play, "value")

def _on_play(self, event):
    self._cb.start() if event.new else self._cb.stop()
```

## Consider New Components

pmui ships components that plain Panel never had. These aren't swaps — there's nothing to replace — but a migration is the natural moment to ask whether a purpose-built component would serve better than the pattern you're carrying over. Reach for them only when they *simplify* the app; don't add UI for its own sake.

- **`pmui.Dialog` / `pmui.Drawer`** — modal dialogs and slide-out panels. Beyond replacing `pn.Modal`, a `Drawer` is often a cleaner home for secondary controls than a permanently visible sidebar.
- **`pmui.Rating`, `pmui.Chip` / `pmui.Pill` / `pmui.MultiPill`** — first-class inputs for star ratings and tag/selection chips that people otherwise fake with buttons or multi-selects.
- **`pmui.SpeedDial`, `pmui.SplitButton`, `pmui.Fab`** — compact action menus and floating actions that replace clusters of buttons.
- **Navigation menus — `pmui.Breadcrumbs`/`NestedBreadcrumbs`, `pmui.Pagination`, `pmui.Tree`, `pmui.TabMenu`, `pmui.StepperMenu`, `pmui.MenuList`** — for paged tables, hierarchical data, or multi-step flows previously hand-wired with callbacks.
- **`pmui.Avatar`, `pmui.Badge`, `pmui.Skeleton`, `pmui.Tooltip`** — small polish (user chips, count badges, loading placeholders, hover hints). `Skeleton` is a top-level component; `Badge`/`Tooltip`/`Transition` apply via the wrapper API rather than as standalone constructors.
- **`pmui.ThemeToggle`, `pmui.BreakpointSwitcher`** — standalone versions of behavior `Page` exposes via `theme_toggle=True`; useful when you're not using `Page` or want the control placed manually.

Browse `reference/{section}/index.md` (especially `menus/` and `wrappers/`, which have no Panel analog) before reimplementing something by hand.

## What Not to Migrate

Some `pn.*` objects have no pmui equivalent — keep them as-is:

- **Plot / data panes** — no pmui equivalent; keep as `pn.pane.*` / `pn.widgets.Tabulator` (see [Panes](#panes) for the full list, including media/embed).
- **Widgets with no pmui class:** `CodeEditor`, `Terminal`, `JSONEditor`, `FileSelector`, `FileDropper`, `Player`, `DiscretePlayer`, `StaticText`, `ToggleGroup`, `ArrayInput`, `ColorMap`, the `DataFrame` widget, and the speech/media widgets (`SpeechToText`, `TextToSpeech`, `VideoStream`). Keep them as `pn.widgets.*`.
- **Indicators:** pmui has only `LoadingSpinner`, `Progress`, `CircularProgress`, and `LinearProgress`. Everything else — `Number`, `Trend`, `Gauge`, `Dial`, `Tqdm`, `BooleanStatus`, `LinearGauge`, `TooltipIcon` — stays `pn.indicators.*`.
- **Spacers and low-level layout helpers** without a Material counterpart (`pn.layout.HSpacer`, `pn.layout.VSpacer`).
- **All reactive wiring** — `@param.depends`, `param.watch`, `pn.bind`, `pn.state.add_periodic_callback`.

If unsure whether a pmui equivalent exists, **don't rely on the reference index alone** — it is not exhaustive (e.g. `Row`, `Column`, `Divider`, `LoadingSpinner`, and `Progress` exist but have no index page). Confirm with `hasattr(pmui, "X")` or `dir(pmui)`, then check the section index (`reference/{section}/index.md`) per the Lookup in [Using Material UI](using-material-ui.md) for usage rather than guessing a class name.

## Gotchas

- **Duplicate icon.** pmui buttons and toggles take a Material `icon=`. If you also leave a glyph (`▷`, `❚❚`) in the label, you get two icons. Pick one — usually the Material `icon=`.
- **Don't keep `pn.pane.Markdown` defensively.** `pmui.Typography` renders markdown; the swap is lossless.
- **`stylesheets` silently no-ops on pmui.** The CSS targets Panel's old DOM, not MUI slots. Rewrite as `sx` (see [Styling](#styling)); `styles` is safe to keep.
- **`design='material'` is not pmui.** That's the old Panel design system — remove it, don't confuse it for panel-material-ui.
- **Delete manual dark/light toggles.** `Page(theme_toggle=True)` replaces them.

## Verifying

- Use the serve → screenshot → debug loop in [Iterating on Panel Apps](iterating-on-panel-apps.md).
