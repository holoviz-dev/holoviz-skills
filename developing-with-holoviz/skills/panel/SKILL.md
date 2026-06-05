---
name: panel
description: Build interactive dashboards, tools, and data apps with HoloViz Panel. Use when the user needs widgets, layouts, templates, or reactive server-side Python web applications. Do not use for standalone plots without widgets (use hvPlot).
metadata:
  version: "1.0.0"
  author: holoviz
---

# Using Panel

Panel is a Python library for building interactive dashboards, data apps, and tools entirely in Python — no JavaScript required. It connects widgets to plots, tables, and text with reactive callbacks, and serves the result as a web application.

Always use a `pn.viewable.Viewer` class to structure apps. This keeps state, layout, and logic organized and avoids flickering from recreated components.

## Contents

- [References](#references) — iterative development, Material UI, HoloViews, custom components, Playwright testing, widget mapping, cleanup
- [Viewer Class Pattern](#viewer-class-pattern)
- [Widgets and Extensions](#widgets-and-extensions)
- [Templates and Layouts](#templates-and-layouts)
- [UX Heuristics](#ux-heuristics)
- [Serving Workflow](#serving-workflow)
- [Performance](#performance)
- [Plotting Integration](#plotting-integration)
- [Component Gotchas](#component-gotchas)

## References

Read these for specialized topics. Each is a standalone document you can load with the `view` tool.

- [Iterating on Panel Apps](iterating-on-panel-apps.md) — serve with logging, screenshot with Playwright, review and debug agentic loop
- [Mapping Widgets](mapping-widgets.md) — which Panel/pmui widget to use for each Param type, with `.from_param()` patterns
- [Building Custom Components](building-custom-components.md) — building JSComponent, ReactComponent, AnyWidgetComponent, and MaterialUIComponent; CDN selection, event handling, state sync lifecycle
- [Applying Material UI](applying-material-ui.md) — `pmui.Page` template, `Container`/`Grid` layouts, centering, component gotchas
- [Branding Material UI](branding-material-ui.md) — `theme_config` palettes, typography, icons, brand assets, chart theming
- [Interacting with HoloViews](interacting-with-holoviews.md) — DynamicMap for preserving zoom/pan, `pn.pane.HoloViews` config (`theme=`, `linked_axes=`), responsive sizing
- [Using Tabulator](using-tabulator.md) — `add_filter` with widgets, checkbox selection, row content, function-based filtering
- [Using Pytest Playwright](using-pytest-playwright.md) — `serve_component`/`wait_until` utilities, JS↔Python sync tests, complete test patterns for custom components
- [Reviewing Panel Apps](reviewing-panel-apps.md) — anti-pattern checklist for code review: flickering, missing hold, watcher gaps, bind vs watch, mutation bugs

## Viewer Class Pattern

- Recreating panes or layouts inside `@param.depends` causes flickering. Create them once in `__init__`, bind to reactive content.
- `on_init=True` watchers fire during `super().__init__()`. Create any panes they reference *before* the `super().__init__(**params)` call.
- Use `pn.pane.Placeholder` when the content type varies (string → plot → widget). Swap with `.update()` or `.object =`.
- Implement `__panel__` to return the layout. When served, wrap in `pmui.Page` (see [Material UI](applying-material-ui.md)); otherwise return the bare component.
- **Shared UI state**: Add a param (`disabled`, `loading`, `visible`) to a base class and bind widgets to it (e.g., `disabled=self.param.disabled`). Set once to update all widgets — useful for form submit, loading states, or toggling visibility.
- **Organize `__init__`**: Separate component instantiation from wiring. First create all widgets/panes, then group `on_click`, `pn.bind`, and `.watch()` calls together. Makes it clear what exists vs. how it's connected.
- **Method naming**: `_on_*` for event handlers (`_on_click`, `_on_submit`), `_update_*` for watchers that sync state (`_update_view`, `_update_button_state`), `_sync_*` for bidirectional syncs.
- **Wizard/pipeline pattern**: For multi-step flows, see `examples/wizard.py` — `pmui.StepperMenu` driving navigation and per-step state (completed/error/active, `non_linear`), `pn.pane.Placeholder` step swapping, shared `disabled` state, `pn.io.hold()` batching, inline `pmui.Alert` validation, `pmui.Tooltip`, and `pmui.Page`.
- **KPI dashboard pattern**: For metric dashboards, see `examples/dashboard.py` — `pn.indicators.Trend` KPI cards, `pmui.Badge` selection counter, `pmui.SpeedDial` quick actions, `pmui.Alert` empty-state, `pmui.Tooltip` hints, `pmui.Grid` responsive layout, DynamicMap with trigger pattern, Tabulator `add_filter` + checkbox selection cross-filtering, `pn.bind(watch=True)` wiring, `param.DataFrame` as single source of truth, and `pmui.Page`.

```python
import hvplot.pandas  # noqa
import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True)

penguins = hvplot.sampledata.penguins("pandas").dropna()
species_list = sorted(penguins["species"].unique())

# ✅ Static panes, reactive content
class Dashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    def __init__(self, **params):
        # Create panes before super().__init__ — on_init=True watchers fire during super()
        self._species_widget = pmui.CheckButtonGroup.from_param(self.param.species)
        self._chart_pane = pn.pane.HoloViews(sizing_mode="stretch_width")
        super().__init__(**params)
        with pn.config.set(sizing_mode="stretch_width"):
            self._sidebar = pmui.Column(self._species_widget)
            self._main = pmui.Column(self._summary, self._chart_pane)

    def _filtered(self):
        return penguins[penguins["species"].isin(self.species)]

    @param.depends("species")
    def _summary(self):
        return f"**{len(self._filtered())}** penguins selected"

    @param.depends("species", watch=True, on_init=True)
    def _update_chart(self):
        self._chart_pane.object = self._filtered().hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species",
        )

    def __panel__(self):
        if pn.state.served:
            return pmui.Page(
                title="Penguin Explorer",
                sidebar=[self._sidebar],
                main=[self._main],
            )
        return self._main

# ❌ Recreates layout on every change — causes flickering
class BadDashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    @param.depends("species")
    def view(self):
        filtered = penguins[penguins["species"].isin(self.species)]
        return pn.Column(
            pn.pane.Markdown(f"**{len(filtered)}** penguins selected"),
            pn.pane.HoloViews(filtered.hvplot.scatter(x="bill_length_mm", y="bill_depth_mm", by="species")),
        )
```

## Widgets and Extensions

- Call `pn.extension(throttled=True)` with any needed JS extensions (`"tabulator"`, `"plotly"`). Never add `"bokeh"`.
- `.from_param()` auto-creates the right widget type from a parameter — syncs value, bounds, and objects. **Caveat**: button-group widgets (`pmui.RadioButtonGroup`, `CheckButtonGroup`, `CheckBoxGroup`) may not sync the widget's value back to the param — clicks change the buttons but watchers never fire. Create them directly and wire `widget.param.watch(handler, "value")` (see [Applying Material UI](applying-material-ui.md)).
- Prefer `pn.bind(self._update, widget1.param.value, widget2.param.value, watch=True)` over lambda-based `.param.watch()` for wiring multiple widgets to a single update method.
- Default to `sizing_mode="stretch_width"` via `pn.config.set`.

## Templates and Layouts

For new apps, use `pmui.Page` from panel-material-ui (see [Material UI](applying-material-ui.md)). If an existing codebase already uses a different template (e.g. `FastListTemplate`), keep it rather than migrating.

- Sidebar order: logo → description → widgets → docs.
- Use `FlexBox`, `GridSpec`, or `GridBox` for complex layouts instead of nested Rows/Columns.
- Set `min_width`/`max_width`/`min_height`/`max_height` to prevent layout collapse.

## UX Heuristics

General layout and interaction patterns for data apps and interactive tools.

- **Context before controls**: show the data a control acts on *before* the control itself — users shouldn't scroll back up to act after scrolling down to look. Applies to forms, dashboards, and review screens alike.
- **Neutral defaults for captured input**: don't preselect an answer the user is meant to provide, and keep submit disabled until they choose — a default silently skews the data. (See the radio `default=None` gotcha; a directly-created widget makes an unset state real.)
- **Group controls with what they affect**: place action controls adjacent to their content rather than in a distant sidebar.

## Serving Workflow

- Keep a dev server running: `panel serve app.py --dev --show`. Don't restart after edits.
- Don't use `--autoreload` (legacy). Don't use `python app.py`.

## Performance

- `@pn.cache` with `ttl=` and `max_items=` for expensive computations.
- `pn.extension(defer_load=True, loading_indicator=True)` for heavy components.
- `pn.io.hold()` to batch multiple updates into a single redraw.
- Async/await for I/O; threads for CPU-intensive work.
- Loading spinner: wrap a slow update in the component's `loading` flag — `with self._main.param.update(loading=True): ...` sets it on enter and reverts on exit. **Caveat**: a synchronous callback won't flush the spinner until it returns; make the slow work `async` if you need it visible *during* the load.
- `@pn.io.profiler` to find bottlenecks.
- Memory: cap streaming history, `pn.state.clear_caches()`, schedule restarts.

```python
with pn.io.hold():
    self.chart = new_chart
    self.table = new_table
    self.summary = new_summary
```

## Plotting Integration

For HoloViews/hvPlot plots in Panel (DynamicMap, streams, responsive sizing), see [HoloViews integration](interacting-with-holoviews.md). For standalone HoloViews concepts (elements, `.opts()`, streams, formatters), see the [HoloViews skill](../holoviews/SKILL.md).

- `pn.pane.HoloViews(plot, theme="light_minimal")` — set `theme=` on the pane, not globally. Options: `"light_minimal"`, `"dark_minimal"`, `"caliber"`, `"night_sky"`, etc.

### Matplotlib

- Set `matplotlib.use('agg')` BEFORE importing pyplot — required for server-side rendering.
- Don't add `'matplotlib'` to `pn.extension()` — not a JS extension.
- Close figures after rendering: `plt.close(fig)`.

```python
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import panel as pn

pn.extension()  # no 'matplotlib' needed
```

### Plotly

- Add `"plotly"` to `pn.extension("plotly")`.
- Match template to app theme, use transparent backgrounds:

```python
template = "plotly_dark" if pn.state.theme == "dark" else "plotly_white"
fig.update_layout(
    template=template,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
)
```

### ECharts

- Prefer dict config over pyecharts.
- Configs must be JSON-serializable — never use Python functions or lambdas (`SerializationError`).
- Template strings: `{b}` (category), `{c}` (value), `{d}` (percentage), `{value}` (axis). Prefix/suffix: `'{value}%'`.
- Use `replaceMerge` when series count changes dynamically, else old series persist:

```python
chart_pane = pn.pane.ECharts(
    self._chart_config,
    options={"replaceMerge": ["series"]},
    sizing_mode="stretch_width",
    height=400,
)
```

## Component Gotchas

- `Tabulator`: prefer over `pn.pane.DataFrame` for displaying DataFrames in apps — sortable, filterable, and paginated. Requires `pn.extension("tabulator")`. See [Using Tabulator](using-tabulator.md) for `add_filter`, checkbox selection, and row content patterns.
- `Markdown`: set `disable_anchors=True` to avoid flicker on header hover.
- `CheckButtonGroup`: use `orientation="vertical"` in sidebars, `button_type="primary"`, `button_style="outline"`.
- Selector widgets with `default=None`: `RadioBoxGroup`/`RadioButtonGroup` visually highlight the first option even when `value=None`. Clicking that option doesn't fire a change event (UI thinks it's already selected), so users can't select the first option. Also, `@param.depends` and `pn.bind` won't trigger on initial load since the value is `None` and clicking the highlighted option doesn't change it. Always set a real default value for radio widgets, or use `Select` if you need an empty state.
- `Selector.objects` as a dict: assigning a **dict** to `param.Selector.objects` after construction can leave the widget's display labels unpopulated, so a `Select` renders blank. Drive the widget's `options` (a `{label: value}` dict) directly and keep the param's `objects` a plain list of values; sync `value` both ways with a guarded watcher.
- Unintended stretch: under the default `sizing_mode="stretch_width"`, fixed-size widgets scale to fill width (`Rating` renders giant stars) and inline `Markdown`/`HTML` labels in a `Row` with `HSpacer`s collapse and wrap one character per line. Give inline widgets and labels a fixed `width` + `sizing_mode="fixed"`.
- Bokeh tools: use `default_tools=["reset"]` to strip all default Bokeh toolbar tools except reset, then add specific tools via `tools=["hover", "xwheel_zoom"]`. Use `active_tools=["xwheel_zoom"]` to set which tools are active by default. For cumulative/monotonic curves, `hover_mode="vline"` gives a better tooltip experience.
- Date widgets: convert to `pd.Timestamp` before comparing to DataFrame columns.

```python
start_date, end_date = self.date_range
start_date = pd.Timestamp(start_date)
end_date = pd.Timestamp(end_date)
filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
```

## Lookup

### Component Reference

Look up component docs at `https://panel.holoviz.org/reference/{section}/{Component}.html`

Sections: `panes`, `widgets`, `layouts`, `chat`, `global`, `indicators`, `templates`, `custom_components`

### Search

Search the web at `https://panel.holoviz.org/search.html?q=<topic>` for additional information.
