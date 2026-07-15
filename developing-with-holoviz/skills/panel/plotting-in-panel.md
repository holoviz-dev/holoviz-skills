# Plotting in Panel

How to embed plots in Panel apps, across libraries: HoloViews/hvPlot, Matplotlib, Plotly, ECharts, and Bokeh. For standalone HoloViews concepts (elements, `.opts()`, streams, formatters, tools), see the [HoloViews skill](../holoviews/SKILL.md).

Examples build on the penguins Dashboard from the Panel skill.

## Contents

- [HoloViews and hvPlot](#holoviews-and-hvplot)
  - [pn.pane.HoloViews Configuration](#pnpaneholoviews-configuration)
  - [DynamicMap Updates: Depend on the Data, Not a Trigger](#dynamicmap-updates-depend-on-the-data-not-a-trigger)
  - [One Element Per DynamicMap](#one-element-per-dynamicmap)
  - [Responsive Sizing](#responsive-sizing)
- [Matplotlib](#matplotlib)
- [Plotly](#plotly)
- [ECharts](#echarts)
- [Bokeh Toolbar Tools](#bokeh-toolbar-tools)

## HoloViews and hvPlot

The richest Panel integration — hvPlot and HoloViews render through `pn.pane.HoloViews`, with DynamicMap for live updates.

### pn.pane.HoloViews Configuration

```python
pn.pane.HoloViews(
    plot,
    sizing_mode="stretch_width",
    theme="light_minimal",      # Bokeh theme — set here, not globally
    linked_axes=False,          # disable axis linking across plots in layout
)
```

- `theme=` sets the Bokeh theme on the pane. Options: `"light_minimal"`, `"dark_minimal"`, `"caliber"`, `"night_sky"`, `None`. Do NOT set globally via `hv.renderer("bokeh").theme`. (Inside a `pmui.Page`/`ThemeToggle`, plots auto-theme — see [Using Material UI](using-material-ui.md#chart-theming).)
- `linked_axes=False` prevents axis linking when combining charts with different axis types in a Layout (`+`). Pair with `.opts(shared_axes=False)` on the Layout itself.
- `sizing_mode="stretch_width"` is required for responsive HoloViews plots.

### Live Updates: Bind the Render Function Directly (default)

**Start here.** For plots driven by scalar widgets (sliders, selects, toggles), bind the render function directly to its parameters and let the plot re-render on any change, no trigger param and no manual signalling. For a pure style change (color, alpha), skip the callback entirely with `element.apply.opts(color=w.param.value)`. For an expensive render, bind to `param.value_throttled` instead of `param.value` so it fires on mouse-up rather than on every drag step. A manual `_trigger` is a last resort (see below).

```python
import holoviews as hv
import numpy as np
import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True)

class SineExplorer(pn.viewable.Viewer):
    amplitude = param.Number(default=1.0, bounds=(0.1, 10.0))
    frequency = param.Number(default=1.0, bounds=(0.1, 10.0))

    def __init__(self, **params):
        super().__init__(**params)  # from_param widgets go AFTER super() (see panel/SKILL.md)
        self._controls = pmui.Column(
            pmui.FloatSlider.from_param(self.param.amplitude),
            pmui.FloatSlider.from_param(self.param.frequency),
        )
        dmap = hv.DynamicMap(pn.bind(self._render, self.param.amplitude, self.param.frequency))
        self._plot = pn.pane.HoloViews(dmap, sizing_mode="stretch_width")

    def _render(self, amplitude, frequency):
        x = np.linspace(0, 10, 500)
        return hv.Curve((x, amplitude * np.sin(frequency * x)), "x", "y").opts(
            responsive=True, height=400, framewise=True,  # framewise rescales axes to new data
        )

    def __panel__(self):
        return pmui.Row(self._controls, self._plot)

SineExplorer().servable()  # run with: panel serve app.py --dev --show
```

### DynamicMap Updates: Depend on the Data, Not a Trigger

`DynamicMap` preserves zoom/pan and patches only changed data on every refresh (that is inherent to `DynamicMap`; `pane.object = new_plot` resets the axes). Drive it by depending on the actual data, in one of two forms:

- `hv.DynamicMap(pn.bind(self._render, self.param.x, self.param.y))` — bind to the params.
- Decorate the render method with `@param.depends("x", "y")` (no `watch`) and pass the method itself: `hv.DynamicMap(self._render)`. Preferred when the data lives on `self` (e.g. a `DataFrame`), since nothing is passed as an argument for `DynamicMap` to hash.

```python
import holoviews as hv
import hvplot.pandas  # noqa
import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True)

penguins = hvplot.sampledata.penguins("pandas").dropna()
species_list = sorted(penguins["species"].unique())

class Dashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    def __init__(self, **params):
        super().__init__(**params)
        # from_param widget AFTER super() (see panel/SKILL.md)
        self._species_widget = pmui.CheckBoxGroup.from_param(self.param.species)
        dmap = hv.DynamicMap(self._render_scatter)  # method carries its own @param.depends
        self._chart_pane = pn.pane.HoloViews(
            dmap, sizing_mode="stretch_both", theme="light_minimal",
        )

    def _filtered(self):
        return penguins[penguins["species"].isin(self.species)]

    @param.depends("species")
    def _render_scatter(self):
        df = self._filtered()
        if df.empty:
            return hv.Scatter([], kdims=["bill_length_mm"], vdims=["bill_depth_mm"]).opts(
                responsive=True,
            )
        return df.hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species",
            responsive=True,
            title="Penguin bill dimensions by species",
            xlabel="Bill length (mm)", ylabel="Bill depth (mm)",
        )

    def __panel__(self):
        if pn.state.served:
            return pmui.Page(
                title="Penguins",
                sidebar=[self._species_widget],
                main=[self._chart_pane],
            )
        return pmui.Column(self._species_widget, self._chart_pane)
```

**Multiple plots: one source of truth.** When several plots read the same derived state, don't have each plot watch the raw widgets. Compute the state once into a single `param.DataFrame` via one pipeline watcher (`@param.depends(..., watch=True, on_init=True)`), batch that recompute with [`pn.io.hold()`](https://panel.holoviz.org/how_to/performance/hold.html) so it is one redraw, and have every `DynamicMap` `@param.depends` on that one param. That param changing is the single redraw signal for all of them. See [Designing Panel Architecture](designing-panel-architecture.md) for the full `DataStore` pattern.

If what changed genuinely isn't a Parameter you can bind or depend on, a `param.Event` fired with `self.param.trigger("_trigger")` can serve as a manual redraw signal — but prefer making that state a Parameter.

### One Element Per DynamicMap

- Returning mixed types (`hv.Scatter` sometimes, `hv.Overlay` other times) raises `AssertionError`.
- Combining scatter + HLines inside `hv.Overlay([...])` loses hover tooltips.
- Create one DynamicMap per element, combine with `*` at layout level. Each callback always returns the same element type.

```python
...
class Dashboard(pn.viewable.Viewer):
    ...
    def __init__(self, **params):
        super().__init__(**params)
        scatter_dmap = hv.DynamicMap(self._render_scatter)
        mean_dmap = hv.DynamicMap(self._render_mean_line)
        self._chart_pane = pn.pane.HoloViews(scatter_dmap * mean_dmap, sizing_mode="stretch_width")

    @param.depends("species")
    def _render_scatter(self):
        df = self._filtered()
        if df.empty:
            return hv.Scatter([], kdims=["bill_length_mm"], vdims=["bill_depth_mm"]).opts(
                responsive=True, height=300,
            )
        return df.hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species",
            responsive=True, height=300,
        )

    @param.depends("species")
    def _render_mean_line(self):
        df = self._filtered()
        avg = df["bill_depth_mm"].mean() if not df.empty else 0
        return hv.HLine(avg).opts(color="orange", line_dash="dashed")
```

### Responsive Sizing

hvPlot internally sets `width=700`. This conflicts with `responsive=True` if applied via `.opts()`.

- **hvPlot**: pass `responsive=True` and `height=N` as **arguments to the hvplot call**, not via `.opts()`. hvPlot's default `width=700` persists through `.opts()` and can't be removed.
- **Pure HoloViews**: `.opts(responsive=True, height=N)` is fine — HoloViews doesn't inject a default width.
- Never set both `width` and `responsive=True` — `width` wins silently.
- Set `sizing_mode="stretch_width"` on the `pn.pane.HoloViews`. To fill height as well (e.g. a chart that should occupy the whole page/`main` area), use `sizing_mode="stretch_both"` and omit `height` — the pane provides the vertical space and `responsive=True` fills it.
- **Overlays**: all elements must have consistent sizing. If one element has `responsive=True` and another has hvPlot's default `width=700`, the overlay warns "responsive mode could not be enabled". Pass `responsive=True, height=N` to every hvPlot call in the overlay.
- **Multi-chart layouts** (`plot_a + plot_b`): use `.opts(shared_axes=False)` on the Layout and `linked_axes=False` on `pn.pane.HoloViews` when charts have different axis types (e.g. time series + categorical bars).

```python
# ✅ hvPlot: responsive and height as arguments
plot = df.hvplot.scatter(x='x', y='y', responsive=True, height=300)
pane = pn.pane.HoloViews(plot, sizing_mode="stretch_width")

# ✅ Pure HoloViews: .opts() is fine
plot = hv.Curve(df, 'x', 'y').opts(responsive=True, height=300)
pane = pn.pane.HoloViews(plot, sizing_mode="stretch_width")

# ❌ BAD: hvplot sets width=700 internally; .opts(responsive=True) doesn't remove it
plot = df.hvplot.scatter(x='x', y='y').opts(responsive=True, height=300)

# ❌ BAD: overlay mixes responsive and non-responsive — triggers warning
area = df.hvplot.area(x='x', y='y', responsive=True, height=300)
line = df.hvplot.line(x='x', y='y2')  # inherits width=700
overlay = area * line

# ✅ Fix: pass responsive=True, height=N to every element
area = df.hvplot.area(x='x', y='y', responsive=True, height=300)
line = df.hvplot.line(x='x', y='y2', responsive=True, height=300)
overlay = area * line
```

## Matplotlib

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

## Plotly

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

## ECharts

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

## Bokeh Toolbar Tools

For Bokeh-backed plots (including HoloViews/hvPlot output):

- `default_tools=["reset"]` strips all default Bokeh toolbar tools except reset; add specific tools via `tools=["hover", "xwheel_zoom"]`.
- `active_tools=["xwheel_zoom"]` sets which tools are active by default.
- For cumulative/monotonic curves, `hover_mode="vline"` gives a better tooltip experience.
