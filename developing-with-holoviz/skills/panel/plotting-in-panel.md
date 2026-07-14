# Plotting in Panel

How to embed plots in Panel apps, across libraries: HoloViews/hvPlot, Matplotlib, Plotly, ECharts, and Bokeh. For standalone HoloViews concepts (elements, `.opts()`, streams, formatters, tools), see the [HoloViews skill](../holoviews/SKILL.md).

Examples build on the penguins Dashboard from the Panel skill.

## Contents

- [HoloViews and hvPlot](#holoviews-and-hvplot)
  - [pn.pane.HoloViews Configuration](#pnpaneholoviews-configuration)
  - [DynamicMap: Preserve Zoom/Pan Across Data Refreshes](#dynamicmap-preserve-zoompan-across-data-refreshes)
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

**Start here.** For plots driven by scalar widgets (sliders, selects, toggles), bind the render function directly to its parameters and let the plot re-render on any change — no trigger param, no manual signalling. Use the `_trigger` pattern below only when this is insufficient.

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

pn.serve(SineExplorer())
```

### DynamicMap: Preserve Zoom/Pan Across Data Refreshes

**When to use the trigger pattern.** Prefer direct binding (above). Use a `_trigger` param + `DynamicMap` only to: (1) depend on an unhashable value (`DataFrame`, list) that breaks `DynamicMap`'s argument-identity caching; (2) share one refresh signal across several render methods; or (3) preserve zoom/pan across refreshes (`pane.object = new_plot` resets axes; `DynamicMap` patches in place).

- Setting `pane.object = new_plot` resets axes. DynamicMap patches data in place, preserving zoom/pan.
- Use a `param.Event` as the signal (`self.param.trigger("_trigger")`) — it fires watchers then auto-resets, so there's no ever-growing counter. Read actual data from `self` inside the callback; ignore the callback's argument.

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
    _trigger = param.Event()

    def __init__(self, **params):
        super().__init__(**params)
        dmap = hv.DynamicMap(pn.bind(self._render_scatter, self.param._trigger))
        self._chart_pane = pn.pane.HoloViews(
            dmap, sizing_mode="stretch_width", theme="light_minimal",
        )
        self._layout = pmui.Column(self._chart_pane)

    def _filtered(self):
        return penguins[penguins["species"].isin(self.species)]

    def _render_scatter(self, trigger):
        df = self._filtered()
        if df.empty:
            return hv.Scatter([], kdims=["bill_length_mm"], vdims=["bill_depth_mm"]).opts(
                responsive=True, height=300,
            )
        return df.hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species",
            responsive=True, height=300,
        )

    @param.depends("species", watch=True, on_init=True)
    def _on_species_changed(self):
        self.param.trigger("_trigger")

    def __panel__(self):
        return self._layout
```

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
        scatter_dmap = hv.DynamicMap(pn.bind(self._render_scatter, self.param._trigger))
        mean_dmap = hv.DynamicMap(pn.bind(self._render_mean_line, self.param._trigger))
        self._chart_pane = pn.pane.HoloViews(scatter_dmap * mean_dmap, sizing_mode="stretch_width")

    def _render_scatter(self, trigger):
        df = self._filtered()
        if df.empty:
            return hv.Scatter([], kdims=["bill_length_mm"], vdims=["bill_depth_mm"]).opts(
                responsive=True, height=300,
            )
        return df.hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species",
            responsive=True, height=300,
        )

    def _render_mean_line(self, trigger):
        df = self._filtered()
        avg = df["bill_depth_mm"].mean() if not df.empty else 0
        return hv.HLine(avg).opts(color="orange", line_dash="dashed")
```

### Responsive Sizing

hvPlot internally sets `width=700`. This conflicts with `responsive=True` if applied via `.opts()`.

- **hvPlot**: pass `responsive=True` and `height=N` as **arguments to the hvplot call**, not via `.opts()`. hvPlot's default `width=700` persists through `.opts()` and can't be removed.
- **Pure HoloViews**: `.opts(responsive=True, height=N)` is fine — HoloViews doesn't inject a default width.
- Never set both `width` and `responsive=True` — `width` wins silently.
- Set `sizing_mode="stretch_width"` on the `pn.pane.HoloViews`.
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
