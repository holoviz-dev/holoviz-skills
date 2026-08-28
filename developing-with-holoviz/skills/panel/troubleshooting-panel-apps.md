# Troubleshooting Panel Apps

Symptom-indexed fixes for Panel/pmui apps that serve but misbehave *silently*. Look up what you see. For the review checklist see [Reviewing Panel Apps](reviewing-panel-apps.md); for the serve→screenshot→debug loop see [Iterating on Panel Apps](iterating-on-panel-apps.md).

## Contents

- [Widgets change but nothing updates (init ordering)](#widgets-change-but-nothing-updates-init-ordering)
- [AttributeError during init (on_init ordering)](#attributeerror-during-init-on_init-ordering)
- [TypeError: unexpected keyword argument (pmui params aren't universal)](#typeerror-unexpected-keyword-argument-pmui-params-arent-universal)
- [First option can't be selected (selection widget with default=None)](#first-option-cant-be-selected-selection-widget-with-defaultnone)
- [Select renders blank after setting .objects](#select-renders-blank-after-setting-objects)
- [Date filter returns nothing / type error](#date-filter-returns-nothing-type-error)
- [Markdown header flickers on hover](#markdown-header-flickers-on-hover)
- [Component rebuilds / flickers on every change](#component-rebuilds-flickers-on-every-change)
- [pmui.Page renders blank (no header/sidebar)](#pmuipage-renders-blank-no-headersidebar)
- ["responsive mode could not be enabled" / won't resize](#responsive-mode-could-not-be-enabled-wont-resize)
- [Tile/map plot renders blank inside a pmui layout](#tilemap-plot-renders-blank-inside-a-pmui-layout)
- [Screenshot shows a loading spinner](#screenshot-shows-a-loading-spinner)
- [Every user's page freezes while one session loads](#every-users-page-freezes-while-one-session-loads)
- [A panel still shows the previous selection's data](#a-panel-still-shows-the-previous-selections-data)
- [The page says there's no data, then shows data](#the-page-says-theres-no-data-then-shows-data)
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

## TypeError: unexpected keyword argument (pmui params aren't universal)

```
TypeError: RadioButtonGroup.__init__() got an unexpected keyword argument 'variant'
```

Raised from `param`'s `_setup_params`, so every frame is `parameterized.py` and none is pmui — only the last line is informative. Cause: assuming a param generalizes because a sibling widget has it. Verify instead of inferring — `'variant' in pmui.X.param`, `pmui.X.param.variant.objects`, `sorted(pmui.X.param)`.

| You wrote | Reality |
|-----------|---------|
| `RadioButtonGroup(variant=…)`, `CheckButtonGroup(variant=…)` | No `variant` — MUI `ToggleButtonGroup`s. Use `color`/`size`/`orientation`, `sx` for borders ([usage](using-material-ui.md#components)) |
| `CheckBoxGroup(orientation=…)` / `(size=…)` | Neither exists — use `inline=True/False` |
| `Container(variant=…)`, `Switch(variant=…)`, `FloatSlider(variant=…)` | No `variant` on layouts, toggles or sliders |
| `Tabs(variant="scrollable")` | Not on `pmui.Tabs` (it *is* on `TabMenu`) |
| `Paper(color=…)` | No `color` — use `sx={"backgroundColor": …}` |
| `pmui.Column(spacing=2)` | No `spacing` — set gap via `sx` |
| `Grid(ncols=…)` | Doesn't exist — use `size=` breakpoints |

Values don't transfer either, where the param does exist: buttons `contained|outlined|text`, inputs `filled|outlined|standard`, `Paper`/`Card` `elevation|outlined`. A wrong *value* raises `ValueError` from the `Selector`, not this `TypeError`.

**The silent variant of this bug:** `RadioButtonGroup`/`CheckButtonGroup` are the only pmui components carrying the legacy `button_style` alias with no real `variant` behind it, so `button_style="outlined"` is accepted and then dropped before it reaches the browser — no error, no effect.

## First option can't be selected (selection widget with default=None)

`RadioBoxGroup`/`RadioButtonGroup`/`Select` from a `Selector` with `default=None` coerce the value to the **first option** and display it as chosen. So the widget shows a selection the user never made, and clicking that option assigns a value Param considers unchanged — no event fires, no watcher runs, and the feature silently does nothing.

Fix: set a real default, add an explicit sentinel option (`"— pick one —"`) as the default, or use `pmui.AutocompleteInput`, the one *single*-select widget that stays `None` ([recipe](using-material-ui.md#components)). Not a fix: swapping radio for `Select` — it coerces identically. Multi-selects (`CheckBoxGroup`, `CheckButtonGroup`, `MultiSelect`) are unaffected; they start `[]`.

Whatever the widget, route every entry point through one method so re-picking the current value still works:

```python
def _open(self, city):
    if self.selected == city:
        self._dialog.open = True   # unchanged value fires no watcher; just reopen
    else:
        self.selected = city       # watcher builds content and opens
```

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

## Every user's page freezes while one session loads

Widgets stop responding for *everyone* — including sessions doing nothing — then recover together. One event loop serves all sessions, so this is a blocking call on the loop, and it will not show up in your timings: the log records the work, the freeze is the wait.

Usual cause: an `async def` that calls a **synchronous** client and `await`s only between calls (a DB driver, `requests`, `boto3`, a blocking `get_connection()`) — it reads as non-blocking because the `await` is right there. Confirm before hunting, with a heartbeat task that reports its own overshoot:

```python
async def loop_monitor(interval=0.25, warn=0.5):
    while True:
        before = perf_counter()
        await asyncio.sleep(interval)
        if (stall := (perf_counter() - before) - interval) >= warn:
            logger.warning(f"event loop stalled {stall:.2f}s")
```

Fix: wrap each blocking call in `await asyncio.to_thread(...)`. To attribute a stall to a specific callback, set `loop.set_debug(True)` and `loop.slow_callback_duration` (the latter is read only in debug mode). Full treatment — thread-safety check, poll-cadence tax, measured before/after: [Blocking the Event Loop](designing-panel-architecture.md#blocking-the-event-loop).

## A panel still shows the previous selection's data

The user picks a different item, the header updates, but a detail panel beside it still describes the *old* one. Cause: that panel is only rewritten at the *end* of an async handler — after a store read or a query — so between the click and that write, the previously published payload is still on screen, under a name and figures that have already changed. Worse than an empty panel, because it looks authoritative.

Fix: clear every dependent param in the **same synchronous tick** as the selection change, before the first `await`, and let the async path republish once it has real data.

```python
def _on_select(self, event):
    self._clear_dependent_panels()     # ✅ before any await, on every branch
    if not event.new:
        return
    ...
    pn.state.execute(partial(self._load, event.new))
```

Two details. Do it on *every* exit path, including early returns for an empty or unresolvable selection — those returns are how stale panels survive longest. And don't blank a param that the click handler itself sets optimistically (a "loading"/"composing" flag): clearing that one first makes the UI flash the pre-request control before hiding it again.

## The page says there's no data, then shows data

A section reads "No results" / "0 found" / "nothing to review" for a few seconds, then fills in. Nobody filed it as a bug — it looks like a page, not an error — but the user has already read a false answer and acted on it, and the copy that misled them is the copy you were most careful about.

Cause: the render path is being handed a partial result and rendering it in **settled vocabulary**. Every empty state asserts a completed check, so on a still-loading payload each one reports a gap in the *read* as a finding about the *data*.

Fix, in order:

1. Give the payload a state that means "still arriving" and **check the renderer branches on it** — a state the view doesn't test renders wrongly. (A common shape: Python grows a fourth state, the view still reads `if state === "thin"`, so the "still loading" message is computed on every chunk and displayed never.)
2. Replace empty-state prose with a **skeleton** in the sections that have not arrived, and don't caption the skeleton.
3. Sweep the rest of the payload for the same class of claim: counts and totals, all-clears ("nothing hidden", "no conflicts"), a search box's "no matches", and any digest/fingerprint computed over the whole payload.
4. Make the finished state say so *positively* — a badge, not the absence of a banner.

Full treatment: [Painting Partial Results](designing-panel-architecture.md#painting-partial-results).

## Behavior or deprecation differs across versions

`panel-material-ui` moves fast — param names, defaults, and deprecations shift between releases. Diagnose the method, don't memorize versions:

- Print what's actually loaded: `print(pn.__version__, pmui.__version__)`. A long-lived server holds *old* modules until restarted — restart after upgrading.
- Run it and **read the `DeprecationWarning`** — it names the replacement. Trust the warning over any doc.

Known moving targets: `pmui.Chip(object=...)` is deprecated → use `label=` (but `pmui.Alert(object=...)` is *not* deprecated — don't "fix" it). The button-group "from_param write-back gap" was never real — it's the [init-ordering](#widgets-change-but-nothing-updates-init-ordering) issue.
