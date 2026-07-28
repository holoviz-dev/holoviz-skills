---
name: decluttering-plots
description: Strip chart junk from HoloViews / hvPlot Bokeh plots with .opts — hide the toolbar, disable wheel-zoom and pan (default_tools/active_tools), draw gridlines on one axis, hide or share axes across stacked plots, and place the legend. Use when a plot looks cluttered, scroll-zooms the chart by accident, has gridlines on both axes, repeats axis labels down a column of charts, or otherwise needs clean, presentation-ready styling. Do not use for choosing what to emphasize / annotate (that is distilling-explanatory-plots).
metadata:
  version: "0.1.0"
  author: holoviz
---

# Decluttering Plots

Dashboard and presentation plots carry Bokeh "chart junk" by default: a toolbar, wheel-zoom
that fires when you scroll the page, gridlines on both axes, and repeated axis labels when
charts are stacked. This skill covers the `.opts()` mechanics to strip that. It is the *how*
(mechanical styling); for the *what* (which series to emphasize, annotation, color as
meaning) see [Distilling Explanatory Plots](../hvplot/distilling-explanatory-plots.md). For
the general opts system see [Using HoloViews](../holoviews/SKILL.md).

## Contents

- [Lookup](#lookup) — Bokeh model properties reference
- [Apply at the top level](#apply-at-the-top-level)
- [Toolbar and tools (disable wheel-zoom)](#toolbar-and-tools-disable-wheel-zoom)
- [Gridlines on one axis](#gridlines-on-one-axis)
- [Hiding and sharing axes](#hiding-and-sharing-axes)
- [Legend placement](#legend-placement)
- [Nested categorical axes](#nested-categorical-axes)
- [hvPlot vs .opts](#hvplot-vs-opts)

## Lookup

Bokeh grid/axis/toolbar model properties:
`https://docs.bokeh.org/en/latest/docs/reference/models/plots.html`.

## Apply at the top level

The most common mistake: setting tool/toolbar options **per element** on an `Overlay` or
`Layout`. They often don't stick, because the composite plot builds its own merged toolbar.
Apply them to the *top-level object you actually render*.

```python
# WRONG — per-element on an overlay; the merged toolbar still shows wheel-zoom
overlay = curve.opts(default_tools=[]) * scatter.opts(default_tools=[])

# CORRECT — set on the overlay itself
overlay = (curve * scatter).opts(toolbar=None, default_tools=[], active_tools=[])
```

A one-line helper keeps every chart consistent — apply it right before you hand the object
to `pn.pane.HoloViews(...)`:

```python
def clean(plot):
    return plot.opts(toolbar=None, default_tools=[], active_tools=[])
```

### Applying options by element type

When different elements in a composite need different styles, chain `.opts()` calls
targeting each element type. This applies the options to every matching element in the
composite:

```python
overlay = (curve * scatter).opts(
    "Curve", **curve_opts
).opts(
    "Scatter", **scatter_opts
)
```

Group-style options (`Overlay`, `NdLayout`, `NdGrid`, …) apply to the container itself,
so you can mix container-level and per-element-level options in one chain:

```python
overlay = (curve * scatter).opts(
    "Curve", **curve_opts
).opts(
    "Scatter", **scatter_opts
).opts(
    "Overlay", **overlay_opts
).opts(
    "NdLayout", **ndlayout_opts
)
```

## Toolbar and tools (disable wheel-zoom)

- `toolbar=None` removes the toolbar entirely (the Bokeh logo + pan/zoom/save icons).
- `default_tools=[]` strips Bokeh's default tools — pan, **wheel_zoom**, box_zoom, save,
  reset, help. This is what actually stops the chart zooming when the user scrolls the page.
  Hiding the toolbar alone is not enough if wheel-zoom is still an active scroll tool.
- `active_tools=[]` guarantees nothing is active on load (belt-and-suspenders so a scroll
  does nothing).
- Add back only the tools you want with `tools=[...]`, e.g. `tools=["hover"]`. Don't blanket
  `tools=[]` if you want hover — it removes hover too.

```python
plot.opts(toolbar=None, default_tools=[], active_tools=[], tools=["hover"])
```

`default_tools=["reset"]` keeps just the reset button; `default_tools=[]` keeps none.

## Gridlines on one axis

`show_grid=True` draws gridlines on **both** axes. To keep only horizontal (y) gridlines —
usually what aids reading values — set the x-grid's alpha to 0 via `gridstyle`:

```python
plot.opts(show_grid=True, gridstyle={"xgrid_line_alpha": 0, "ygrid_line_alpha": 0.35})
```

`gridstyle` keys are prefixed `xgrid_` / `ygrid_`; zero the `*_line_alpha` of the axis you
want gone. (`backend_opts={"xgrid.grid_line_color": None}` also works, but `gridstyle` is the
HoloViews-native way.)

## Hiding and sharing axes

- `xaxis=None` / `yaxis=None` hide an axis entirely (ticks **and** label). `xaxis="bare"`
  keeps the axis line but drops ticks and labels.
- When stacking related charts in a column that share one x-axis, show ticks + `xlabel` only
  on the **bottom** chart and set `xaxis=None` on the rest. This removes the repeated axis
  that otherwise appears under every panel:

```python
top.opts(xaxis=None, xlabel="")        # and every panel except the last
bottom.opts(xlabel="model / task")     # only the bottom panel labels the shared axis
```

- Rotate long categorical tick labels rather than letting them collide: `rot=25` in an hvPlot call (e.g. `df.hvplot.bar(rot=25)`), or `.opts(xrotation=25)` for HoloViews elements. Don't pass `rot=` to `.opts()` — it's hvPlot-only.

## Legend placement

- **hvPlot:** `legend="top_right"` (a position string) places the legend *inside* the plot
  at that corner. Prefer this over the default, which can render a wide external legend
  column that squeezes the plot into a sliver.
- **HoloViews:** `legend_position="top_right"` (with `show_legend=True/False`).
- Positions: `top_left`, `top_right`, `bottom_left`, `bottom_right`, plus
  `top`/`bottom`/`left`/`right`.
- In a stack of related charts, show the legend on the **first** panel only and set
  `legend=False` on the rest, so it isn't repeated down the column.

## Nested categorical axes

Collapsing two grouping columns into one flat `"a · b"` label forces long, angled ticks.
`Bars`, `Violin`, and `BoxWhisker` accept **multiple kdims** (`by=[...]`) for a nested
categorical x-axis — the inner group sits under the outer group, which reads far cleaner:

```python
df.hvplot.bar(y="count", by=["model", "task"])        # task nested under model
df.hvplot.violin(y="latency_ms", by=["model", "task"])
```

Caveat: a jittered `scatter` overlay can't align to a two-level categorical x. If you need
raw points overlaid on the violin/box, use a single flat combined series
(`x="model · task"`) instead; otherwise keep the nested `by=[...]` axis and drop the overlay.

## hvPlot vs .opts

- `responsive=True` and `height=` must be **hvPlot call arguments**, not `.opts()`: hvPlot
  injects a default `width=700` that `.opts(responsive=True)` cannot override. See
  [Plotting in Panel](../panel/plotting-in-panel.md#responsive-sizing).
- The decluttering options here (`toolbar`, `default_tools`, `active_tools`, `tools`,
  `show_grid`, `gridstyle`, `xaxis`) are plot options. Pass them via `.opts()` — reliable on
  overlays and layouts — or as hvPlot kwargs for a single element. When in doubt, use
  `.opts()` on the final object (see [Apply at the top level](#apply-at-the-top-level)).
- hvPlot's `grid=True` maps to `show_grid=True` (both axes); for one-axis control use
  `gridstyle` via `.opts()`.
