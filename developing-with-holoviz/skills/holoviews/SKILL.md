---
name: holoviews
description: Build interactive visualizations with HoloViews elements, opts, streams, and operations. Use when composing plots from element primitives (Curve, Points, Bars, NdOverlay), customizing Bokeh tools/tooltips/formatters, using DynamicMap, streams, or link_selections. Do not use for simple DataFrame plotting (use hvPlot) or Panel app structure (use Panel).
metadata:
  version: "0.0.3"
  author: holoviz
---

# Using HoloViews

HoloViews lets you build interactive visualizations by composing declarative elements. Use it when you need fine-grained control over plot composition, custom tooltips, Bokeh tool configuration, streaming data, or cross-filtering — things that go beyond hvPlot's `.plot()`-style API.

For embedding HoloViews plots in Panel apps (DynamicMap trigger pattern, responsive sizing, `pn.pane.HoloViews`), see [Plotting in Panel](../panel/plotting-in-panel.md).

## Contents

- [Opts System](#opts-system)
- [Hover Tooltips](#hover-tooltips)
- [Formatters](#formatters)
- [Bokeh Tools](#bokeh-tools)
- [DynamicMap](#dynamicmap)
- [Streams](#streams)

## Opts System

`.opts()` applies visual options to elements. Chain calls for different element types.

```python
# Options on the element itself
hv.Curve(df, "date", "revenue").opts(
    color="blue", line_width=2, responsive=True, height=300,
)

# Chained opts for container + element type
hv.NdOverlay(curves, kdims=["Region"]).opts(
    "NdOverlay", legend_position="top_left", title="Revenue by Region",
).opts(
    "Curve", responsive=True, height=350, tools=["hover"],
)
```

- Options go on the element type they belong to: `legend_position` and `title` on `NdOverlay`, `tools` and `color` on `Curve`.
- Misplaced options raise `ValueError: unexpected option 'X' for Y type`.
- A legend with a single entry distinguishes nothing and just adds clutter — suppress it: `.opts(show_legend=len(groups) > 1)` (computed from the same dict/groupby driving the `NdOverlay`, e.g. after a filter narrows a `by=`/`kdims=` grouping down to one category).
- `.opts()` on pure HoloViews elements is fine. For hvPlot, pass options as hvplot kwargs instead — see the [hvPlot skill](../hvplot/SKILL.md).

## Hover Tooltips

Use `hover_tooltips` as an opts list of `(label, value)` tuples. Bokeh format strings apply inside `{}`.

```python
hv.Curve(df, "date", "revenue").opts(
    tools=["hover"],
    hover_tooltips=[
        ("Date", "@{date}"),
        ("Revenue", "@revenue{$0,0}"),
        ("Region", "$name"),           # $name = NdOverlay key
    ],
)
```

- `@column` or `@{column}` references data columns. Use `@{col name}` for names with spaces.
- `$name` references the NdOverlay key (legend label).
- Bokeh format syntax: `{$0,0}` currency with thousands, `{0.1f}` one decimal, `{0,0}` thousands, `{%F %H:%M}` datetime.
- `hover_formatters` is **deprecated** — do not use it. Format inline in the tooltip string.
- `hover_mode="vline"` snaps tooltip to nearest x-value — ideal for timeseries and cumulative curves.

## Formatters

Import from `bokeh.models` for axis formatting:

```python
from bokeh.models import NumeralTickFormatter, DatetimeTickFormatter

hv.Curve(df, "date", "revenue").opts(
    yformatter=NumeralTickFormatter(format="$0,0"),
    xformatter=DatetimeTickFormatter(months="%b %Y"),
)
```

Common `NumeralTickFormatter` formats: `"$0,0"` (currency), `"0,0"` (thousands), `"0a"` (abbreviated: 1k, 1M), `"0.0%"` (percentage).

## Bokeh Tools

Control the toolbar via `tools`, `default_tools`, and `active_tools`:

```python
hv.Curve(df, "date", "revenue").opts(
    tools=["hover", "xwheel_zoom"],       # add these tools
    active_tools=["xwheel_zoom"],          # active by default
    default_tools=["reset"],               # keep only reset from defaults
)
```

- `default_tools=[]` strips all default Bokeh tools (pan, wheel_zoom, save, reset). Add back selectively: `default_tools=["reset"]`.
- `tools=` adds on top of defaults. Common: `"hover"`, `"xwheel_zoom"`, `"ywheel_zoom"`, `"box_select"`, `"tap"`, `"lasso_select"`.
- `active_tools=` sets which tools are active on load.

## DynamicMap

DynamicMap calls a callback to generate elements lazily. It patches data in place, preserving zoom/pan — unlike replacing `pane.object` which resets axes.

```python
dmap = hv.DynamicMap(render_fn, streams=[stream])
```

- Each DynamicMap callback must **always return the same element type**. Returning `Scatter` sometimes and `NdOverlay` other times raises `AssertionError`.
- Create one DynamicMap per element type, combine with `*` (overlay) or `+` (layout).
- Use `.opts(framewise=True)` with streaming data (Pipe/Buffer) so axes update when data ranges change.

For the Panel integration pattern (trigger param, `pn.bind`, `pn.pane.HoloViews`), see [Plotting in Panel](../panel/plotting-in-panel.md).

## Streams

Streams push events from user interactions or external data into DynamicMap callbacks. The basic pattern: create a stream with `source=element`, write a callback that receives stream values, wrap in `hv.DynamicMap(callback, streams=[stream])`.

Common streams: `Selection1D` (indices from tap/box_select), `Tap` (x/y coordinates), `PointerX`/`PointerY` (cursor position), `BoundsX`/`BoundsXY` (selection range), `Pipe` (replace data), `Buffer` (append data). Use `.opts(framewise=True)` with Pipe/Buffer so axes update when data ranges change.

### PointerX / PointerY (Linked Cross-Sections)

Track cursor position on one plot to update a linked detail view — useful for Hovmueller cross-sections, distributions at a cursor position, etc.

```python
geomap = hv.Image(ds.isel(time=0), ["lon", "lat"], ["air"]).opts(tools=["hover"])
lat_stream = hv.streams.PointerY(y=40, source=geomap)

def create_xsection(y):
    return hv.Image(ds.sel(lat=y, method="nearest"), ["lon", "time"], ["air"])

def create_hline(y):
    return hv.HLine(y).opts(color="red")

# One DynamicMap per element type, combine with *
layout = geomap * hv.DynamicMap(create_hline, streams=[lat_stream]) \
       + hv.DynamicMap(create_xsection, streams=[lat_stream])
```

### BoundsX (Subset Axis Limits)

Use `xbox_select` and `.apply.opts(xlim=stream.param.boundsx)` to drive axis range — no callback needed.

```python
source = hv.Curve(df, "x", "y").opts(
    width=500, height=125, default_tools=["xbox_select"],
)
stream = hv.streams.BoundsX(source=source, boundsx=(0, 2))

target = (hv.Curve(df, "x", "y") * hv.Scatter(df, "x", "y")).opts(
    "Curve", axiswise=True, framewise=True, width=500, height=250,
)
target = target.apply.opts(xlim=stream.param.boundsx)

layout = (source + target).opts(merge_tools=False).cols(1)
```

### Pitfalls

- `Selection1D` needs `tools=['tap', 'box_select']` in `.opts()` — without them no events fire.
- Stream callbacks receive `None`/empty on first render — always guard with `if x is None`.
- Always set `source=` on the stream. For bidirectional interaction, create separate streams with separate sources.
- Don't mix streams and `param.depends`/`pn.bind` for the same plot.

## Cross-Filtering with link_selections

`hv.link_selections` provides automatic cross-filtering across static elements.

- **Does NOT work with DynamicMap** — use Tabulator selection + `pn.bind(watch=True)` instead (see `examples/dashboard.py` in the Panel skill).
- Use `.instance()` to create a reusable linker.
- `hv.operation.histogram(element, dimension='x')` for numeric histograms — preserves data lineage.
- For categorical bars, subclass `hv.Operation` (see below).
- Don't add selection tools manually — `link_selections` adds them.
- Requires `pyarrow` at runtime. Lasso also requires `shapely`.

```python
from holoviews.operation import histogram

ls = hv.link_selections.instance()
scatter = hv.Points(df, kdims=["x", "y"])
hist = histogram(scatter, dimension="x", num_bins=20)
layout = ls(scatter) + ls(hist)
```

### Categorical Bars with link_selections

```python
import numpy as np

class categorical_agg(hv.Operation):
    dimension = param.String(doc="Categorical dimension to group by")
    value_dimension = param.String(default=None, allow_None=True)
    function = param.Callable(default=np.size)
    label = param.String(default=None, allow_None=True)

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
            agg_label = self.p.label or f"{self.p.value_dimension}"
            data = list(zip(unique_cats, results))
        return hv.Bars(data, kdims=[self.p.dimension], vdims=[agg_label])

bars = categorical_agg(scatter, dimension="species")
layout = ls(scatter) + ls(bars)
```

## Lookup

Search the web at `https://holoviews.org/search.html?q=<topic>` for additional information.
