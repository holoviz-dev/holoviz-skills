# Interacting with HoloViews

How to embed HoloViews and hvPlot plots in Panel apps. For standalone HoloViews concepts (elements, opts, streams, formatters, tools), see the [HoloViews skill](../holoviews/SKILL.md).

Examples build on the penguins Dashboard from the Panel skill.

## Contents

- [pn.pane.HoloViews Configuration](#pnpaneholoviews-configuration)
- [DynamicMap: Preserve Zoom/Pan Across Data Refreshes](#dynamicmap-preserve-zoompan-across-data-refreshes)
- [One Element Per DynamicMap](#one-element-per-dynamicmap)
- [Responsive Sizing](#responsive-sizing)

## pn.pane.HoloViews Configuration

```python
pn.pane.HoloViews(
    plot,
    sizing_mode="stretch_width",
    theme="light_minimal",      # Bokeh theme — set here, not globally
    linked_axes=False,          # disable axis linking across plots in layout
)
```

- `theme=` sets the Bokeh theme on the pane. Options: `"light_minimal"`, `"dark_minimal"`, `"caliber"`, `"night_sky"`, `None`. Do NOT set globally via `hv.renderer("bokeh").theme`.
- `linked_axes=False` prevents axis linking when combining charts with different axis types in a Layout (`+`). Pair with `.opts(shared_axes=False)` on the Layout itself.
- `sizing_mode="stretch_width"` is required for responsive HoloViews plots.

## DynamicMap: Preserve Zoom/Pan Across Data Refreshes

- Setting `pane.object = new_plot` resets axes. DynamicMap patches data in place, preserving zoom/pan.
- Use a trigger parameter as a signal — DynamicMap caches by argument identity, so read actual data from `self` inside the callback.

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
    _trigger = param.Integer(default=0)

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
        self._trigger += 1

    def __panel__(self):
        return self._layout
```

## One Element Per DynamicMap

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

## Responsive Sizing

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
