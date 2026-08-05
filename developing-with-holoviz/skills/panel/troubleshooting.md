# Troubleshooting Panel Apps

Symptom-indexed fixes for Panel/pmui apps that serve but misbehave *silently*. Look up what you see. For the review checklist see [Reviewing Panel Apps](reviewing-panel-apps.md); for the serve→screenshot→debug loop see [Iterating on Panel Apps](iterating-on-panel-apps.md).

## Contents

- [Widgets change but nothing updates (init ordering)](#widgets-change-but-nothing-updates-init-ordering)
- [AttributeError during init (on_init ordering)](#attributeerror-during-init-on_init-ordering)
- [First radio option can't be selected](#first-radio-option-cant-be-selected)
- [Select renders blank after setting .objects](#select-renders-blank-after-setting-objects)
- [Date filter returns nothing / type error](#date-filter-returns-nothing-type-error)
- [Markdown header flickers on hover](#markdown-header-flickers-on-hover)
- [Component rebuilds / flickers on every change](#component-rebuilds-flickers-on-every-change)
- [pmui.Page renders blank (no header/sidebar)](#pmuipage-renders-blank-no-headersidebar)
- ["responsive mode could not be enabled" / won't resize](#responsive-mode-could-not-be-enabled-wont-resize)
- [Tile/map plot renders blank inside a pmui layout](#tilemap-plot-renders-blank-inside-a-pmui-layout)
- [Screenshot shows a loading spinner](#screenshot-shows-a-loading-spinner)
- [Behavior or deprecation differs across versions](#behavior-or-deprecation-differs-across-versions)

## Widgets change but nothing updates (init ordering)

A `.from_param()` widget created **before** `super().__init__(**params)`: its value still syncs, but `@param.depends`/`.watch()` never fire, so dependents go stale. Not widget-specific, not a pmui write-back bug — just ordering. Fix: create `.from_param()` widgets **after** `super()`.

```python
def __init__(self, **params):
    super().__init__(**params)
    self._toggle = pmui.RadioButtonGroup.from_param(self.param.chart_type)  # ✅ after super()
```

Rule: bare panes before `super()`, `.from_param()` widgets after ([Viewer pattern](SKILL.md#viewer-class-pattern)).

## AttributeError during init (on_init ordering)

`AttributeError: '…' object has no attribute '_some_pane'` from inside `super().__init__()`: an `@param.depends(..., on_init=True)` watcher fires during `super()` and references a pane not yet created. Fix: create panes referenced by `on_init` watchers **before** `super()` (the flip side of the rule above).

## First radio option can't be selected

`RadioBoxGroup`/`RadioButtonGroup` with `default=None` highlights the first option anyway, so clicking it fires no change event and callbacks never trigger on load. Fix: set a real default (or use `Select` for an empty state).

## Select renders blank after setting .objects

Assigning a **dict** to `Selector.objects` at runtime can leave display labels unpopulated. Fix: keep the param's `objects` a plain list of values, drive the widget's `options` (a `{label: value}` dict) directly, and reassign `value` to stay within the new set (see [`from_data`](designing-panel-architecture.md#the-from_data-factory)).

## Date filter returns nothing / type error

A date widget yields `datetime.date`, which doesn't compare cleanly to a pandas datetime column. Fix: wrap in `pd.Timestamp` first.

```python
start, end = self.date_range
df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
```

## Markdown header flickers on hover

The auto-generated header anchor renders on hover. Fix: `pn.pane.Markdown(..., disable_anchors=True)`.

## Component rebuilds / flickers on every change

A `@param.depends` method (no `watch=True`) returns a *new* layout/widget each call, so the subtree is recreated. Fix: create panes once in `__init__` and update properties; use `pn.pane.Placeholder` when the content *type* varies. Full checklist: [Reviewing Panel Apps](reviewing-panel-apps.md#flickering-from-recreated-components).

## pmui.Page renders blank (no header/sidebar)

Gating `__panel__`'s `Page` return on `if pn.state.served:` is a bug: the guard is **always** `False` there, even under `panel serve`, so you always fall through to the bare fallback layout. `pn.state.served` inspects its *immediate caller's* module (`inspect.stack()[1]`) and asks whether that module is the served script — Bokeh names it `bokeh_app_<uuid>`. Panel itself calls `__panel__` (from `panel.viewable` / `panel.pane.base`), so the check sees Panel's module, never yours. Fix: build the `Page` once in `__init__` (e.g. `self._page = pmui.Page(...)`) and return it unconditionally from `__panel__` (`return self._page`) ([Page rules](using-material-ui.md#page)).

`pn.state.served` is still the right check at **module level** of the served script, where your module *is* the caller — e.g. `if pn.state.served: App().servable()`. The rule is about where you call it, not the property being unreliable.

## "responsive mode could not be enabled" / won't resize

hvPlot sets `width=700` internally; `.opts(responsive=True)` doesn't remove it, and mixing responsive + non-responsive elements in an overlay conflicts. Fix: pass `responsive=True, height=N` as **hvPlot call args** (not `.opts()`), on *every* overlay element, and never set both `width` and `responsive=True`. Pure-HoloViews `.opts(responsive=True, height=N)` is fine ([Responsive Sizing](plotting-in-panel.md#responsive-sizing)).

## Tile/map plot renders blank inside a pmui layout

A HoloViews tile overlay (`hv.element.tiles.*`, incl. GeoViews `tile_sources`) inside `pmui.Column`/`pmui.Row` paints the toolbar, legend, and attribution but no map and no axes, with `tile extent is not fully defined` and `could not set initial ranges` repeating in the console. pmui layouts are ESM/React components whose child paints before the layout has sized it; Bokeh's tile aspect enforcement then scales the ranges against a zero frame dimension and writes `±Infinity`/`NaN` into both ranges *and* their reset values, which no later layout pass or window resize repairs. Plots without a tile layer recover on the next layout pass, so only tile/geo plots are hit. Fix: put tile plots in native `pn.Column`/`pn.Row` — Bokeh layouts size children before their first paint. pmui layouts are fine everywhere else, including for the surrounding page.

```python
import holoviews as hv, numpy as np, panel as pn, panel_material_ui as pmui

hv.extension("bokeh"); pn.extension()

x, y = np.random.rand(2, 50) * 1e6
overlay = (
    hv.element.tiles.CartoLight()
    * hv.NdOverlay({k: hv.Points((x, y)).opts(size=6) for k in "ABC"}, kdims=["Category"])
).opts(legend_position="right", responsive=True)
pane = pn.pane.HoloViews(overlay, sizing_mode="stretch_both")

pmui.Column(pane, sizing_mode="stretch_width").servable()  # ❌ blank map, axes missing
pn.Column(pane, sizing_mode="stretch_width").servable()    # ✅ renders
```

Only the layout *directly* containing the pane has to be native; `pmui.Page`, `Container`, `Tabs`, and `Paper` further out are fine. Prefer native `pn.Column`/`pn.Row` as the immediate wrapper for any plot pane — Bokeh layouts size children before their first paint, so plots are not exposed to this class of first-paint bug at all.

Open bug as of bokeh 3.9; verify it still reproduces before working around it.

## Screenshot shows a loading spinner

The capture beat the render — a fixed `wait_for_timeout` instead of waiting on the `.pn-loading` overlay that `defer_load`/`loading_indicator`/`loading=True` add. Fix:

```python
page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=30000)
```

Full pattern: [Iterating on Panel Apps](iterating-on-panel-apps.md#screenshot-shows-a-loading-spinner).

## Behavior or deprecation differs across versions

`panel-material-ui` moves fast — param names, defaults, and deprecations shift between releases. Diagnose the method, don't memorize versions:

- Print what's actually loaded: `print(pn.__version__, pmui.__version__)`. A long-lived server holds *old* modules until restarted — restart after upgrading.
- Run it and **read the `DeprecationWarning`** — it names the replacement. Trust the warning over any doc.

Known moving targets: `pmui.Chip(object=...)` is deprecated → use `label=` (but `pmui.Alert(object=...)` is *not* deprecated — don't "fix" it). The button-group "from_param write-back gap" was never real — it's the [init-ordering](#widgets-change-but-nothing-updates-init-ordering) issue.
