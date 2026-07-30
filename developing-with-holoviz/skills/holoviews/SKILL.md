---
name: holoviews
description: Build interactive visualizations with HoloViews elements, opts, streams, and operations. Use when composing plots from element primitives (Curve, Points, Bars, NdOverlay), customizing Bokeh tools/tooltips/formatters, using DynamicMap, streams, or link_selections. Do not use for simple DataFrame plotting (use hvPlot) or Panel app structure (use Panel).
metadata:
  version: "0.1.0"
  author: holoviz
---

# HoloViews

HoloViews lets you build interactive visualizations by composing declarative elements. Use it when you need fine-grained control over plot composition, custom tooltips, Bokeh tool configuration, streaming data, or cross-filtering — things that go beyond hvPlot's `.plot()`-style API.

For embedding HoloViews plots in Panel apps (DynamicMap trigger pattern, responsive sizing, `pn.pane.HoloViews`), see [Plotting in Panel](../panel/plotting-in-panel.md).

## Contents

- [References](#references) — decluttering plots
- [Lookup](#lookup) — site search
- [Opts System](#opts-system)
- [Session Defaults](#session-defaults)
- [Hover Tooltips](#hover-tooltips)
- [Formatters](#formatters)
- [Bokeh Tools](#bokeh-tools)
- [DynamicMap](#dynamicmap)
- [Streams](#streams)
- [Cross-Filtering with link_selections](#cross-filtering-with-link_selections)

## References

Read these for specialized topics. Each is a standalone document you can load with the `view` tool.

- [Decluttering Plots](decluttering-plots.md) — stripping Bokeh chart junk with `.opts()`: hide the toolbar, disable wheel-zoom (`default_tools`/`active_tools`), one-axis gridlines (`gridstyle`), hide/share axes across stacked plots, legend placement, nested categorical axes, and why these opts belong on the top-level overlay/layout rather than per element

## Lookup

Web-search `https://holoviews.org/search.html?q=<topic>` for anything not covered below.

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
- Misplaced options raise `ValueError: Unexpected option 'X' for Y type across all extensions.` The message then either lists near-misses ("Similar options for current extension ('bokeh') are: [...]") or says "No similar options found." — read that tail, it usually names the option you meant.
- A legend with a single entry distinguishes nothing and just adds clutter — suppress it: `.opts(show_legend=len(groups) > 1)` (computed from the same dict/groupby driving the `NdOverlay`, e.g. after a filter narrows a `by=`/`kdims=` grouping down to one category).
- `.opts()` on pure HoloViews elements is fine. For hvPlot, pass options as hvplot kwargs instead — see the [hvPlot skill](../hvplot/SKILL.md).

## Session Defaults

`hv.opts.defaults(...)` sets options once for the session instead of on every element. Use it for
cosmetics repeated across a family of charts:

```python
hv.opts.defaults(*[
    opt(toolbar=None, active_tools=[], show_grid=True,
        gridstyle={"xgrid_line_alpha": 0, "ygrid_line_alpha": 0.35})
    for opt in (hv.opts.Overlay, hv.opts.Curve, hv.opts.Scatter, hv.opts.BoxWhisker)
])
```

- **Per-object options beat session defaults.** Anything written onto an element wins — including
  every option hvPlot writes on your behalf. So `opts.defaults` is the right home for options
  nothing else sets, and the wrong home for anything a call already supplies.
- **hvPlot's `responsive`/`height` cannot be defaulted this way** — hvPlot injects its own
  `width=700` that outranks any session default. See [Plotting in Panel](../panel/plotting-in-panel.md#responsive-sizing)
  for the full explanation. Pure HoloViews elements have no injected width, so for them sizing
  *can* live in `opts.defaults`. That asymmetry is a real reason to build a repeated family of
  charts from `hv.Dataset(...).to(...)` rather than `.hvplot`: every option, sizing included, then
  lives in one place instead of being repeated per call.
- **No catch-all type.** The option store is keyed by concrete registered types, so there is no
  "every element" spelling — list the types you actually build. Include container types (`Overlay`,
  `NdOverlay`, `Layout`) when the option belongs on the outer plot; sizing and `toolbar` do.
- **Check the current default before overriding it.** `active_tools` defaults to `None`, not `[]`,
  so `active_tools=[]` is meaningful — it suppresses the pan/wheel-zoom Bokeh would otherwise
  activate. Conversely hvPlot's `tools` already defaults to `[]`, so passing it does nothing.
- Requires a loaded backend: `hv.extension("bokeh")`, or `import hvplot.pandas`, which is the only
  reason to add `import holoviews as hv` to otherwise hvPlot-only code.

Porting a family of hvPlot calls to elements so their options can be defaulted needs a few
renames: `rot` → `xrotation`, `legend="top_right"` → `legend_position` plus `show_legend`, `by=`
→ `.overlay(dim)`, and `groupby=` → a leftover kdim plus `.layout(dim)`. Building both layers of
an overlay from one `hv.Dataset` also removes the kdim-mismatch failure mode that tempts people
into wrapping the overlay in a `try`/`except`.

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

To strip chart junk wholesale — hide the toolbar, disable accidental wheel-zoom, put gridlines
on one axis, share/hide axes across stacked plots — and for the gotcha that these opts must go
on the top-level plot (overlay/layout), see [Decluttering Plots](decluttering-plots.md).

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

- **DynamicMap support is conditional, and fails quietly.** `link_selections` has an explicit `DynamicMap` branch: it links fine when the DynamicMap's element type is introspectable (`dmap.type` is an `Element` subclass — i.e. the *same-element-type* rule from [DynamicMap](#dynamicmap) above), and also handles `dynamic_mul` overlays and `dynamic_operation` chains. Anything else it cannot recurse into is returned **unlinked** with only a `param.warning`: `linked selection: Encountered DynamicMap that we don't know how to recurse into`. So there is no exception to catch — if cross-filtering silently does nothing, check the logs for that warning, then fall back to Tabulator selection + `pn.bind(watch=True)` (see `examples/dashboard.py` in the Panel skill).
- Use `.instance()` to create a reusable linker.
- `hv.operation.histogram(element, dimension='x')` for numeric histograms — preserves data lineage.
- For categorical bars, subclass `hv.Operation` (see below).
- Don't add selection tools manually — `link_selections` adds `box_select` and `lasso_select` itself.
- Lasso selection on tabular data needs **`spatialpandas` *or* `shapely`** (spatialpandas is preferred when both are present); with neither you get `ImportError: Lasso selection on tabular data requires either spatialpandas or shapely to be available.` Note the lasso *tool* still appears in the toolbar either way — the error only surfaces when a lasso is actually drawn.

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
import param

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
