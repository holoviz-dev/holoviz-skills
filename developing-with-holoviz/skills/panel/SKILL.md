---
name: panel
description: Build interactive dashboards, tools, and data apps with HoloViz Panel. Use when the user needs widgets, layouts, templates, or reactive server-side Python web applications. Do not use for standalone plots without widgets (use hvPlot).
metadata:
  version: "1.0.0"
  author: holoviz
---

# Using Panel effectively

Always use a `pn.viewable.Viewer` class to structure apps. This keeps state, layout, and logic organized and avoids flickering from recreated components.

## Viewer Class Pattern

Notes:
- Recreating panes or layouts inside `@param.depends` causes flickering. Create them once in `__init__`, bind to reactive content.
- Use `pn.pane.Placeholder` when the content type varies (string → plot → widget). Swap with `.update()` or `.object =`.
- Implement `__panel__` to return the layout. When served, wrap in `pmui.Page` (see the panel-material-ui skill); otherwise return the bare component.

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
    chart = param.Parameter()

    def __init__(self, **params):
        super().__init__(**params)
        self._species_widget = pn.widgets.CrossSelector.from_param(self.param.species)
        self._chart_pane = pn.pane.HoloViews(self.param.chart)
        with pn.config.set(sizing_mode="stretch_width"):
            self._sidebar = pn.Column(self._species_widget)
            self._main = pn.Column(self._summary, self._chart_pane)

    def _filtered(self):
        return penguins[penguins["species"].isin(self.species)]

    @param.depends("species")
    def _summary(self):
        return f"**{len(self._filtered())}** penguins selected"

    @param.depends("species", watch=True, on_init=True)
    def _update_chart(self):
        self.chart = self._filtered().hvplot.scatter(
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

Notes:
- Call `pn.extension(throttled=True)` with any needed JS extensions (`"tabulator"`, `"plotly"`). Never add `"bokeh"`.
- `.from_param()` auto-creates the right widget type from a parameter — syncs value, bounds, and objects.
- Default to `sizing_mode="stretch_width"` via `pn.config.set`.

## Templates and Layouts

For new apps, use `pmui.Page` from panel-material-ui (see the panel-material-ui skill). If an existing codebase already uses a different template (e.g. `FastListTemplate`), keep it rather than migrating.

Notes:
- Sidebar order: logo → description → widgets → docs.
- Use `FlexBox`, `GridSpec`, or `GridBox` for complex layouts instead of nested Rows/Columns.
- Set `min_width`/`max_width`/`min_height`/`max_height` to prevent layout collapse.

## Serving Workflow

Notes:
- Keep a dev server running: `panel serve app.py --dev --show`. Don't restart after edits.
- Don't use `--autoreload` (legacy). Don't use `python app.py`.

## Performance

Notes:
- `@pn.cache` with `ttl=` and `max_items=` for expensive computations.
- `pn.extension(defer_load=True, loading_indicator=True)` for heavy components.
- `pn.io.hold()` to batch multiple updates into a single redraw.
- Async/await for I/O; threads for CPU-intensive work.
- `@pn.io.profiler` to find bottlenecks.
- Memory: cap streaming history, `pn.state.clear_caches()`, schedule restarts.

```python
with pn.io.hold():
    self.chart = new_chart
    self.table = new_table
    self.summary = new_summary
```

## Plotting Integration

For HoloViews/hvPlot plots in Panel (DynamicMap, streams, responsive sizing), see the panel-holoviews skill.

### Matplotlib

Notes:
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

Notes:
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

Notes:
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

Notes:
- `Tabulator`: prefer over `pn.pane.DataFrame` for displaying DataFrames in apps — sortable, filterable, and paginated. Set `disabled=True` unless editing. Prefer Tabulator formatters/editors over Bokeh types. Requires `pn.extension("tabulator")`.
- `Markdown`: set `disable_anchors=True` to avoid flicker on header hover.
- `CheckButtonGroup`: use `orientation="vertical"` in sidebars, `button_type="primary"`, `button_style="outline"`.
- Date widgets: convert to `pd.Timestamp` before comparing to DataFrame columns.

```python
start_date, end_date = self.date_range
start_date = pd.Timestamp(start_date)
end_date = pd.Timestamp(end_date)
filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
```

## Lookup

Search the web at `https://panel.holoviz.org/search.html?q=<topic>` for additional information.