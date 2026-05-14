# Interacting with HoloViews

Examples build on the penguins Dashboard from the Panel skill.

## Contents

- [DynamicMap: Preserve Zoom/Pan Across Data Refreshes](#dynamicmap-preserve-zoompan-across-data-refreshes)
- [One Element Per DynamicMap](#one-element-per-dynamicmap)
- [Responsive Sizing](#responsive-sizing)
- [HoloViews Streams](#holoviews-streams)
- [Linked Selections / Cross-Filtering](#linked-selections-cross-filtering)
- [Client-Side Interactions with jslink](#client-side-interactions-with-jslink)

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
        self._chart_pane = pn.pane.HoloViews(dmap, sizing_mode="stretch_width")
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

## HoloViews Streams

### Selection1D

```python
from holoviews import streams

points = hv.Points(penguins, kdims=["bill_length_mm", "bill_depth_mm"]).opts(
    tools=["tap", "box_select"], size=8,
)
selection = streams.Selection1D(source=points)

def show_selected(index):
    if not index:
        return hv.Table(penguins.iloc[:0], kdims=["bill_length_mm", "bill_depth_mm"])
    return hv.Table(penguins.iloc[index], kdims=["bill_length_mm", "bill_depth_mm"])

table_dmap = hv.DynamicMap(show_selected, streams=[selection])
pmui.Row(points, table_dmap).servable()
```

### Tap

```python
tap_stream = streams.Tap(source=points)

def on_tap(x, y):
    if x is None:
        return hv.Text(0, 0, "Click a point")
    nearest = penguins.iloc[((penguins["bill_length_mm"] - x)**2 + (penguins["bill_depth_mm"] - y)**2).argmin()]
    return hv.Text(x, y, f'{nearest["species"]}').opts(text_font_size="10pt")

tap_dmap = hv.DynamicMap(on_tap, streams=[tap_stream])
(points * tap_dmap).servable()
```

### Pipe / Buffer (Streaming Data)

```python
from holoviews.streams import Pipe, Buffer

pipe = Pipe(data=[])
pipe_dmap = hv.DynamicMap(hv.Curve, streams=[pipe]).opts(framewise=True)
pipe.send(new_dataframe)  # replace data

buffer = Buffer(df.iloc[:0], length=500)
buffer_dmap = hv.DynamicMap(hv.Curve, streams=[buffer]).opts(framewise=True)
buffer.send(new_rows_df)  # append data
```

### Stream Pitfalls

- `Selection1D` needs `tools=['tap', 'box_select']` in `.opts()` — without them no events fire.
- Stream callbacks receive `None`/empty on first render — always guard.
- Don't mix streams and `param.depends`/`pn.bind` for the same plot.
- Use `.opts(framewise=True)` with Pipe/Buffer so axes update when data ranges change.

## Linked Selections / Cross-Filtering

`hv.link_selections` provides automatic cross-filtering. Don't build this manually with streams.

- Use `.instance()` to create the linker — `hv.link_selections(plot)` returns a plot, not a reusable linker.
- Use `hv.operation.histogram(source_element, dimension='x')` for numeric histograms — preserves data lineage. Don't use `hv.Histogram(np.histogram(...))` — pre-binned loses the source link.
- `histogram()` only works for numeric dimensions. For categorical bars, use a custom `Operation` subclass (see below).
- Apply `selection_expr` to a `hv.Dataset`, not a pandas DataFrame.
- Don't add selection tools manually — `link_selections` adds them automatically.
- Requires `pyarrow` at runtime. Lasso selection also requires `shapely`.

```python
from holoviews.operation import histogram

ls = hv.link_selections.instance()
scatter = hv.Points(penguins, kdims=["bill_length_mm", "bill_depth_mm"])
hist = histogram(scatter, dimension="bill_length_mm", num_bins=20)
layout = ls(scatter) + ls(hist)
pn.pane.HoloViews(layout, sizing_mode="stretch_width").servable()
```

### Categorical Bars with link_selections

`histogram()` only handles numeric dimensions. For categorical aggregation, subclass `Operation` to preserve data lineage:

```python
import numpy as np
from holoviews.core import Operation

class categorical_agg(Operation):
    dimension = param.String(doc="Categorical dimension to group by")
    value_dimension = param.String(default=None, allow_None=True, doc="Numeric dim to aggregate. None = count.")
    function = param.Callable(default=np.size, doc="Aggregation function")
    label = param.String(default=None, allow_None=True, doc="Value axis label")

    def _process(self, element, key=None):
        cat_vals = element.dimension_values(self.p.dimension, expanded=True)
        unique_cats = np.unique(cat_vals)
        if self.p.value_dimension is None:
            _, counts = np.unique(cat_vals, return_counts=True)
            data = list(zip(unique_cats, counts))
            agg_label = self.p.label or "Count"
        else:
            num_vals = element.dimension_values(self.p.value_dimension, expanded=True)
            results = [self.p.function(num_vals[cat_vals == cat]) for cat in unique_cats]
            func_name = getattr(self.p.function, "__name__", "agg")
            agg_label = self.p.label or f"{func_name}({self.p.value_dimension})"
            data = list(zip(unique_cats, results))
        return hv.Bars(data, kdims=[self.p.dimension], vdims=[agg_label])

# Cross-filter scatter + species bar chart
bars = categorical_agg(scatter, dimension="species")
layout = ls(scatter) + ls(bars)
```

## Client-Side Interactions with jslink

For visual controls that don't need Python, wire Panel widgets directly to Bokeh properties. No server roundtrip.

```python
widget = pn.widgets.FloatSlider(value=1, step=0.01)
plot = hv.Points(penguins, kdims=["bill_length_mm", "bill_depth_mm"]).opts(size=8)
widget.jslink(plot, value='glyph.fill_alpha')

# JS code callback for transforms
widget = pn.widgets.RangeSlider(start=30, end=60)
widget.jslink(plot, code={'value': """
    x_range.start = cb_obj.value[0];
    x_range.end = cb_obj.value[1];
"""})
```

Targets: `glyph.*` (fill_alpha, size, line_width), `plot.title.*`, `xaxis.*`/`yaxis.*`, `x_range.*`/`y_range.*`, `color_mapper.*`.

