---
name: panel
description: Build interactive dashboards, tools, and data apps with HoloViz Panel. Use when the user needs widgets, layouts, templates, or reactive server-side Python web applications. Do not use for standalone plots without widgets (use hvPlot).
metadata:
  version: "2026.11.12"
  author: holoviz
---

# Panel

Panel is a Python library for building interactive dashboards, data apps, and tools entirely in Python — no JavaScript required. It connects widgets to plots, tables, and text with reactive callbacks, and serves the result as a web application.

Use a `pn.viewable.Viewer` class to structure any app that holds state or will grow. This keeps state, layout, and logic organized and avoids flickering from recreated components. A flat script of widgets wired with `pn.bind`/`pn.rx` into stable panes is fine for small apps and teaching material (Panel's basic tutorials are deliberately function-based); don't rewrite one into a class just to satisfy this rule. Once an app outgrows one class — multiple views over shared data, state several components touch — split it into composable classes (see [Designing Panel Architecture](designing-panel-architecture.md)).

## Contents

- [Lookup](#lookup) — component docs URLs and site search
- [References](#references) — iterative development, Panel UI, plotting, data storytelling, custom components, React shells, Playwright testing, app structure & scaling, review
- [Viewer Class Pattern](#viewer-class-pattern)
- [Reactive Output References](#reactive-output-references)
- [Widgets and Extensions](#widgets-and-extensions)
- [Defaults](#defaults)
- [Templates and Layouts](#templates-and-layouts)
- [Serving Workflow](#serving-workflow)
- [Performance](#performance)

## Lookup

Fetch Panel docs as markdown, not HTML: prefix any Panel doc path with `/markdown/` and change `.html`/`.ipynb` to `.md` (also for links found inside pages), e.g `https://panel.holoviz.org/markdown/tutorials/basic/build_dashboard.md`. If the result is empty, the page moved — use the `llms.txt` index: `https://panel.holoviz.org/llms.txt`.

- Anything else: web-search `https://panel.holoviz.org/search.html?q=<topic>`, then convert the `.html` hit to its `/markdown/…​.md` URL.

## References

Read these for specialized topics. Each is a standalone document you can load on demand.

- [Iterating on Panel Apps](iterating-on-panel-apps.md) — pre-flight lint, serve with logging, panel-live-server MCP tools, live-browser layout lint, Bokeh plot-model inspection, startup benchmarking, screenshot with Playwright, review and debug agentic loop
- [Designing Panel Architecture](designing-panel-architecture.md) — composing larger apps (State/DataStore/View/App, `param.ClassSelector`, cross-object `@param.depends`, `from_data`, `pn.rx`) and runtime/scale (per-session model, `pn.state` scheduling, URL state sync, generator streaming, caching tiers, `nthreads`, profiling)
- [Building Custom Components](building-custom-components.md) — Python-vs-JS decision ladder; pure-Python `Viewer`/`PyComponent`; JSComponent, ReactComponent, AnyWidgetComponent, MaterialUIComponent; CDN selection, event handling, state sync lifecycle
- [Wrapping React Apps](wrapping-react-apps.md) — making an existing React/JSX UI the whole app: shell/app class split, `model.useState` as the only transport, `Child` embedding of Panel components, request/response param pairs, shadow-DOM CSS rules, `_importmap` externals, `panel compile` and the dev-vs-production bundle trap
- [Using Panel UI](using-panel-ui.md) — building `panel.ui` apps: `pn.ui.Page`, `Container`/`Grid` layouts, centering, component gotchas
- [Theming Panel UI](theming-panel-ui.md) — `theme_config` palette, typography, web fonts, component overrides, icons, brand assets, chart colors and plot fonts
- [Migrating to Panel UI](migrating-to-panel-ui.md) — converting an existing plain-Panel app to `panel.ui`: template→Page, widget swaps, pane/interaction upgrades, what to leave alone
- [Converting Designs to Panel UI](converting-designs-to-panel-ui.md) — workflow for turning a screenshot/design/React app into a `panel.ui` app: capture references, map to components, build component-first with mock data, assemble, theme last
- [Plotting in Panel](plotting-in-panel.md) — embedding plots from any library: HoloViews/hvPlot (DynamicMap zoom/pan, responsive sizing), Matplotlib, Plotly, ECharts, Bokeh toolbar tools
- [Data Storytelling](data-storytelling.md) — assembling explanatory charts into a scrollable editorial article (`panel.ui` masthead, narrow reading column, prose-then-chart rhythm, one visual family); see `examples/graphic_story.py`
- [Using Tabulator](using-tabulator.md) — `add_filter` with widgets, checkbox selection, row content, function-based filtering
- [Using Pytest Playwright](using-pytest-playwright.md) — `serve_component`/`wait_until` utilities, JS↔Python sync tests, complete test patterns for custom components
- [Reviewing Panel Apps](reviewing-panel-apps.md) — anti-pattern checklist for code review: flickering, missing hold, watcher gaps, reactive-wiring priority, from_param super() ordering, mutation bugs
- [Troubleshooting Panel Apps](troubleshooting-panel-apps.md) — symptom→cause→fix for apps that serve but misbehave silently: init ordering, dead-app, blank Page, responsive/spinner issues, version & deprecation diagnosis

## Viewer Class Pattern

- Recreating panes or layouts inside `@param.depends` causes flickering. Create them once in `__init__`, bind to reactive content.
- **`super().__init__()` ordering matters, in two opposite directions.** Panes/placeholders an `on_init=True` watcher references must be created *before* `super().__init__(**params)` (else `AttributeError` during init). But `.from_param()` widgets must be created *after* it: made before super, the widget binds to the *class* parameter, so moving it writes the class default (every later instance and session starts from that value), param→widget sync breaks, and `@param.depends`/`.watch()` callbacks never fire — so dependent plots silently never update. This is the usual cause of a "widgets move but nothing updates" app. Narrowing a `Selector`'s `.objects` from data also belongs after `super()`, for a different reason: Param only hands out a per-instance copy of the parameter once initialized, so doing it earlier mutates the shared class parameter and every other instance sees it. Rule of thumb: bare panes before `super()`, `from_param` widgets and `.objects` narrowing after. When a `from_param` widget is *also* what an `on_init=True` watcher swaps in, the two halves collide — drop `on_init` and call the updater explicitly at the end of `__init__` (see `examples/wizard.py`'s `DeductionsStep`).
- Use `pn.pane.Placeholder` when the content type varies (string → plot → widget). Swap with `.update()` or `.object =`.
- Implement `__panel__` to return the layout. When served, wrap in `pn.ui.Page` (see [Using Panel UI](using-panel-ui.md)); otherwise return the bare component.
- **Shared UI state**: Add a param (`disabled`, `loading`, `visible`) to a base class and bind widgets to it (e.g., `disabled=self.param.disabled`). Set once to update all widgets — useful for form submit, loading states, or toggling visibility.
- **Organize `__init__`**: Separate component instantiation from wiring (respecting the `super()` ordering rule above), then group `on_click`, `pn.bind`, and `.watch()` calls together. Makes it clear what exists vs. how it's connected.
- **Method naming**: `_on_*` for event handlers (`_on_click`, `_on_submit`), `_update_*` for watchers that sync state (`_update_view`, `_update_button_state`), `_sync_*` for bidirectional syncs.
- **Wizard/pipeline pattern**: For multi-step flows, see `examples/wizard.py` — `pn.ui.StepperMenu` driving navigation and per-step state (completed/error/active, `non_linear`), `pn.pane.Placeholder` step swapping, shared `disabled` state, `pn.io.hold()` batching, inline `pn.ui.Alert` validation, `pn.ui.Tooltip`, and `pn.ui.Page`.
- **KPI dashboard pattern**: For metric dashboards, see `examples/dashboard.py` — `pn.indicators.Trend` KPI cards, `pn.ui.Badge` selection counter, `pn.ui.SpeedDial` quick actions, `pn.ui.Alert` empty-state, `pn.ui.Tooltip` hints, `pn.ui.Grid` responsive layout, DynamicMaps that `@param.depends` on a `param.DataFrame` single source of truth, Tabulator `add_filter` + checkbox selection cross-filtering, `pn.bind(watch=True)` wiring, and `pn.ui.Page`.

## Reactive Output References

Give each output a stable component and pass its *reactive reference* to that component, not to the enclosing layout. This applies equally to `pn.bind`, `@param.depends` methods, `param.rx` expressions, and direct Parameter references. Choose the reference that fits the data: a Parameter for an existing value, `rx` for a simple transformation, a depends method or `pn.bind` for a computed value. Each reference must resolve to the type its consumer expects. Do not make any of these approaches return an entire layout of plots, tables, and text: replacing the layout on updates recreates its components, flickers, and resets plot state.

```python
table_ref = pn.bind(make_table, selector)     # or a @param.depends method
text_ref = selector.param.value.rx.pipe(format_summary)
plot_ref = pn.bind(make_plot, selector)       # or a @param.depends method

pn.ui.Column(
    pn.ui.DataFrame(table_ref),
    pn.ui.Markdown(text_ref),
    hv.DynamicMap(plot_ref),
)

# When state already holds the right types, pass Parameters directly:
pn.ui.Column(pn.ui.DataFrame(state.param.data), pn.ui.Markdown(state.param.summary))

# Wrong with any reactive API: the whole layout is rebuilt on change.
pn.ui.Column(pn.bind(make_entire_dashboard, selector))
```

Use the equivalent `pn.pane.DataFrame` / `pn.pane.Markdown` in a plain-Panel app and the appropriate pane for other result types (for example, `pn.pane.Matplotlib` for a Matplotlib figure). `pn.bind(..., watch=True)` and `@param.depends(..., watch=True)` are for side effects, not display content. For multiple plots, give *each plot* its own reactive callback and `hv.DynamicMap`; see [Plotting in Panel](plotting-in-panel.md#one-element-per-dynamicmap).

```python
import holoviews as hv
import hvplot.pandas  # noqa
import panel as pn
import param

pn.extension(throttled=True)

penguins = hvplot.sampledata.penguins("pandas").dropna()
species_list = sorted(penguins["species"].unique())

# ✅ Static panes, reactive content
class Dashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    def __init__(self, **params):
        super().__init__(**params)
        # from_param widgets must be created AFTER super() — before it, widget
        # changes update the param silently but never fire watchers (dead app).
        self._species_widget = pn.ui.CheckBoxGroup.from_param(self.param.species)
        with pn.config.set(sizing_mode="stretch_width"):
            self._sidebar = pn.ui.Column(self._species_widget)
            self._main = pn.ui.Column(
                pn.ui.Markdown(self._summary),
                pn.pane.HoloViews(hv.DynamicMap(self._plot), sizing_mode="stretch_width"),
            )
        # Build the Page once — __panel__ returns it unconditionally.
        self._page = pn.ui.Page(
            title="Penguin Explorer",
            sidebar=[self._sidebar],
            main=[self._main],
        )

    def _filtered(self):
        return penguins[penguins["species"].isin(self.species)]

    @param.depends("species")
    def _summary(self):
        return f"**{len(self._filtered())}** penguins selected"

    @param.depends("species")
    def _plot(self):
        return self._filtered().hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species", responsive=True,
        )

    def __panel__(self):
        return self._page

# ❌ Recreates layout on every change — causes flickering
class BadDashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    @param.depends("species")
    def view(self):
        filtered = penguins[penguins["species"].isin(self.species)]
        return pn.ui.Column(
            pn.pane.Markdown(f"**{len(filtered)}** penguins selected"),
            pn.pane.HoloViews(filtered.hvplot.scatter(x="bill_length_mm", y="bill_depth_mm", by="species")),
        )
```

## Widgets and Extensions

- Call `pn.extension(throttled=True)` with any needed JS extensions (`"tabulator"`, `"plotly"`). Never add `"bokeh"`. `throttled` matters when sliders drive expensive work (it makes them update on release); it's harmless elsewhere, so set it by default.
- `.from_param()` auto-creates the right widget type from a parameter — syncs value, bounds, and objects. Create `from_param` widgets *after* `super().__init__()` (button groups included) or their `@param.depends`/watchers won't fire — see the [ordering rule](#viewer-class-pattern) and the [review checklist](reviewing-panel-apps.md#from_param-widgets-created-before-super).
- Prefer `pn.bind(self._update, widget1.param.value, widget2.param.value, watch=True)` over lambda-based `.param.watch()` for wiring multiple widgets to a single update method.

## Defaults

Say an option once rather than repeating it on every component.

- **`pn.extension(sizing_mode="stretch_width")`** sets `pn.config.sizing_mode` for the whole session — the highest-value default in a dashboard, since it removes `sizing_mode` from nearly every layout, pane, and widget. Three exclusions, all silent: a component that passes `width` is skipped; a component whose *class* default for `sizing_mode` isn't `None` never consults the config at all (`pn.indicators.Indicator` defaults to `"fixed"`, so `Number` opts out while `Trend` and `Progress` override back to `None` and opt in); and a component may overrule it in its own `__init__` (`Number` assigns `sizing_mode=None` when you don't). Before relying on the config for a given component, check its class default. Use `with pn.config.set(...)` only to scope a default to a block of construction; it does nothing for components built later inside methods.
- **Class param defaults** restyle a component everywhere without repeating a kwarg: `pn.widgets.Tabulator.param.theme.default = "materialize"`, `pn.indicators.Number.param.font_size.default = "24pt"` (otherwise 54pt, which dwarfs a page), `pn.ui.Button.param.disable_elevation.default = True`. They lose to anything the component's own `__init__` assigns — which is why the same trick fails for `Number.sizing_mode`. If a class default seems ignored, read the component's `__init__` before assuming the value is wrong.
- **Check the library default before setting it.** `pn.ui.Alert.variant` already defaults to `"outlined"`, so passing it is noise — but `Alert.severity` defaults to `"success"`, not `"info"`, so an info alert must say so. Both directions bite: one leaves clutter, the other silently changes behaviour.
- For chart options — `hv.opts.defaults`, and why hvPlot's `responsive` can never be defaulted — see [Session Defaults](../holoviews/SKILL.md#session-defaults).

## Templates and Layouts

For new apps, use `pn.ui.Page` from `panel.ui` (see [Using Panel UI](using-panel-ui.md) for Page rules, sidebar order, and layout helpers). If an existing codebase already uses a different template (e.g. `FastListTemplate`), keep it rather than migrating. Use `FlexBox`/`GridSpec`/`GridBox` for complex layouts, and set `min_*`/`max_*` sizing to prevent layout collapse.

## Serving Workflow

- **Preflight before the first serve**: `python <skill-dir>/scripts/preflight.py app.py` — a stdlib-only AST lint for the mechanical anti-patterns this skill documents (flicker-causing `@param.depends` returns, `from_param` before `super()`, missing `pn.io.hold()`, mutated params, `Radio*Group` defaults, missing `throttled`). Exits 0 and prints `preflight: clean` when there's nothing to fix, or 1 with one `file:line: [CHECK_ID] message` per violation, so gate on the exit code and only read the output when it's non-zero. Resolve the script path relative to wherever you read *this* file from — skills install at different paths per tool, so a bare `scripts/preflight.py` won't resolve from the app's own working directory. It needs no server and no dependencies, so run it before spending a log cycle or a screenshot on something greppable.
- Keep a dev server running: `panel serve app.py --dev --show`. Don't restart after edits.
- Don't use `--autoreload` (legacy). For iterating on an app, prefer `panel serve app.py --dev --show` over `python app.py` — it auto-reloads on file changes so you don't need to restart the server after each edit.
- `python app.py` + `.show()` is fine for a one-off quick preview (works for both standard Panel and `panel.ui` apps — it opens a browser tab via Bokeh's server), but it doesn't auto-reload, so it's not the workflow for iterating.
- Once the logs are clean, `python <skill-dir>/scripts/layout_lint.py http://localhost:5007/app_name` checks the rendered DOM at three viewport widths for overflow, small touch targets, and low contrast — findings as text, before a screenshot. It needs an already-running server plus playwright. Full agentic loop: [Iterating on Panel Apps](iterating-on-panel-apps.md).

## Performance

- Defer heavy components with `pn.extension(defer_load=True, loading_indicator=True)`; memoize expensive work with `@pn.cache`.
- **`pn.io.hold()`**: each property assignment on a widget/pane normally triggers its own redraw. When a watcher touches 3+ properties, wrap them in `with pn.io.hold(): ...` so they collapse into a single redraw instead of one per assignment.

  ```python
  with pn.io.hold():
      self._breadcrumbs.active = self.active_step
      self._next_btn.label = "Submit" if is_last else "Continue"
      self._content.update(current_step)
  ```
- For caching tiers, automatic threading, generator streaming, profiling, the loading-spinner pattern, and memory management, see [Designing Panel Architecture](designing-panel-architecture.md).
