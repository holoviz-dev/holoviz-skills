---
name: panel
description: Build interactive dashboards, tools, and data apps with HoloViz Panel. Use when the user needs widgets, layouts, templates, or reactive server-side Python web applications. Do not use for standalone plots without widgets (use hvPlot).
metadata:
  version: "1.0.0"
  author: holoviz
---

# Using Panel effectively

Correct patterns and common pitfalls for building dashboards and data apps with Panel.

Before building, consider: what does the user need to control? What changes when they interact? Start simple with `pn.bind`, graduate to a Viewer class when complexity grows.

## Quick Start with `pn.bind`

For simple apps — a few widgets controlling a function — `pn.bind` is all you need.

```python
import hvplot.pandas  # noqa
import panel as pn

pn.extension(throttled=True)

penguins = hvplot.sampledata.penguins("pandas").dropna()

species_widget = pn.widgets.MultiChoice(
    name="Species", value=["Adelie"], options=sorted(penguins["species"].unique()),
)

def scatter(species):
    filtered = penguins[penguins["species"].isin(species)]
    return filtered.hvplot.scatter(
        x="bill_length_mm", y="bill_depth_mm", by="species",
        title=f"{len(filtered)} penguins selected",
    )

pn.Column(species_widget, pn.bind(scatter, species_widget)).servable()
```

## Graduating to Viewer Classes

Graduate to a `pn.viewable.Viewer` class when:
1. Multiple outputs depend on the same filtered data — `pn.bind` recomputes for each.
2. You need shared state across interactions (selection history, undo).
3. You want a template with sidebar/main split.

Notes:
1. Recreating panes or layouts inside `@param.depends` causes flickering. Create them once in `__init__`, bind to reactive content.
2. Use `pn.pane.Placeholder` when the content type varies (string → plot → widget). Swap with `.update()` or `.object =`.

```python
import hvplot.pandas  # noqa
import panel as pn
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
        self._chart_pane = pn.pane.HoloViews(self.param.chart)
        self._layout = pn.Column(self._summary, self._chart_pane)

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
        return self._layout

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
1. Call `pn.extension(throttled=True)` with any needed JS extensions (`"tabulator"`, `"plotly"`). Never add `"bokeh"`.
2. `.from_param()` auto-creates the right widget type from a parameter — syncs value, bounds, and objects.
3. Default to `sizing_mode="stretch_width"` via `pn.config.set`.

```python
...
class Dashboard(pn.viewable.Viewer):
    ...
    def __init__(self, **params):
        super().__init__(**params)
        self._species_widget = pn.widgets.CrossSelector.from_param(self.param.species)
        self._table = pn.widgets.Tabulator(self.param.chart, disabled=True)
        with pn.config.set(sizing_mode="stretch_width"):
            self._sidebar = pn.Column(self._species_widget)
            self._main = pn.Column(self._summary, self._chart_pane, self._table)
```

## Templates and Layouts

For new apps, prefer `pmui.Page` from panel-material-ui over `FastListTemplate` — see the panel-material-ui skill.

Notes:
1. Use `FastListTemplate` for served apps. Set `main_layout=None` for modern styling.
2. Sidebar order: logo → description → widgets → docs.
3. Use `FlexBox`, `GridSpec`, or `GridBox` for complex layouts instead of nested Rows/Columns.
4. Set `min_width`/`max_width`/`min_height`/`max_height` to prevent layout collapse.
5. Guard with `pn.state.served`, not `if __name__ == "__main__"`.

```python
...
class Dashboard(pn.viewable.Viewer):
    ...
    @classmethod
    def create_app(cls, **params):
        instance = cls(**params)
        return pn.template.FastListTemplate(
            title="Penguin Explorer",
            sidebar=[instance._sidebar],
            main=[instance._main],
            main_layout=None,
        )

if pn.state.served:
    Dashboard.create_app().servable()
```

## Serving Workflow

Notes:
1. Keep a dev server running: `panel serve app.py --dev --show`. Don't restart after edits.
2. Don't use `--autoreload` (legacy). Don't use `python app.py`.

## Performance

Notes:
1. `@pn.cache` with `ttl=` and `max_items=` for expensive computations.
2. `pn.extension(defer_load=True, loading_indicator=True)` for heavy components.
3. `pn.io.hold()` to batch multiple updates into a single redraw.
4. Async/await for I/O; threads for CPU-intensive work.
5. `@pn.io.profiler` to find bottlenecks.
6. Memory: cap streaming history, `pn.state.clear_caches()`, schedule restarts.

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
1. Set `matplotlib.use('agg')` BEFORE importing pyplot — required for server-side rendering.
2. Don't add `'matplotlib'` to `pn.extension()` — not a JS extension.
3. Close figures after rendering: `plt.close(fig)`.

```python
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import panel as pn

pn.extension()  # no 'matplotlib' needed
```

### Plotly

Notes:
1. Add `"plotly"` to `pn.extension("plotly")`.
2. Match template to app theme, use transparent backgrounds:

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
1. Prefer dict config over pyecharts.
2. Configs must be JSON-serializable — never use Python functions or lambdas (`SerializationError`).
3. Template strings: `{b}` (category), `{c}` (value), `{d}` (percentage), `{value}` (axis). Prefix/suffix: `'{value}%'`.
4. Use `replaceMerge` when series count changes dynamically, else old series persist:

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
1. `Tabulator`: prefer over `pn.pane.DataFrame` for displaying DataFrames in apps — sortable, filterable, and paginated. Set `disabled=True` unless editing. Prefer Tabulator formatters/editors over Bokeh types. Requires `pn.extension("tabulator")`.
2. `Markdown`: set `disable_anchors=True` to avoid flicker on header hover.
3. `CheckButtonGroup`: use `orientation="vertical"` in sidebars, `button_type="primary"`, `button_style="outline"`.
4. Date widgets: convert to `pd.Timestamp` before comparing to DataFrame columns.

```python
start_date, end_date = self.date_range
start_date = pd.Timestamp(start_date)
end_date = pd.Timestamp(end_date)
filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
```

## Lookup

Search the web at `https://panel.holoviz.org/search.html?q=<topic>` for additional information.