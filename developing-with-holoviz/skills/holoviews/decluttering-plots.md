# Decluttering Plots

Dashboard and presentation plots carry Bokeh "chart junk" by default: a toolbar, wheel-zoom
that fires when you scroll the page, gridlines on both axes, and repeated axis labels when
charts are stacked. This reference covers the `.opts()` mechanics to strip that — it is the
*how* (mechanical styling). For the *what* (which series to emphasize, annotation, color as
meaning) see [Distilling Explanatory Plots](../hvplot/distilling-explanatory-plots.md). These
options apply to any Bokeh-backed HoloViews object, hvPlot output included — see
[hvPlot vs .opts](#hvplot-vs-opts) for the two APIs' division of labour.

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

For a whole family of charts, prefer setting these once for the session with
`hv.opts.defaults(...)` instead of a per-object helper — see
[Session Defaults](SKILL.md#session-defaults), which also covers why hvPlot's sizing options
are the one thing that cannot be defaulted this way.

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
- `autohide_toolbar=True` keeps the toolbar but hides it until the pointer enters the plot.
  Reach for this instead of `toolbar=None` when the chart is still meant to be explored and
  you only want the icons out of the way while it's being read — you keep reset/save/hover
  without the permanent furniture. It sets Bokeh's `toolbar.autohide`, and has **no effect
  under `toolbar=None`**, since that leaves no toolbar to reveal.
- `default_tools=[]` strips Bokeh's default tools — pan, **wheel_zoom**, box_zoom, save,
  reset, help. This is what actually stops the chart zooming when the user scrolls the page.
  Hiding the toolbar alone is not enough if wheel-zoom is still an active scroll tool.
- `active_tools=[]` guarantees nothing is active on load (belt-and-suspenders so a scroll
  does nothing).
- Add back only the tools you want with `tools=[...]`, e.g. `tools=["hover"]`. Don't blanket
  `tools=[]` if you want hover — it removes hover too.

```python
# Static/presentation chart — no toolbar at all, nothing zooms on scroll
plot.opts(toolbar=None, default_tools=[], active_tools=[], tools=["hover"])

# Still interactive, but the toolbar only appears on hover
plot.opts(autohide_toolbar=True, default_tools=["reset"], active_tools=[], tools=["hover"])
```

`default_tools=["reset"]` keeps just the reset button; `default_tools=[]` keeps none.

`autohide_toolbar` is spelled the same in both APIs — it is valid as an hvPlot call kwarg
(`df.hvplot.line(..., autohide_toolbar=True)`) as well as via `.opts()`, and it takes in
`hv.opts.defaults(...)`, so a whole dashboard can adopt hover-only toolbars in one line (see
[Session Defaults](SKILL.md#session-defaults)).

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

- Rotate long categorical tick labels rather than letting them collide: `.opts(xrotation=25)` (`yrotation=` for the other axis).

## Legend placement

- `legend_position="top_right"` places the legend *inside* the plot at that corner. Prefer an
  inside corner over the default, which can render a wide external legend column that squeezes
  the plot into a sliver.
- Positions: `top_left`, `top_right`, `bottom_left`, `bottom_right`, plus
  `top`/`bottom`/`left`/`right`.
- `show_legend=False` drops it entirely. In a stack of related charts, show the legend on the
  **first** panel only and set `show_legend=False` on the rest, so it isn't repeated down the
  column.
- A legend with a single entry distinguishes nothing — suppress it with
  `show_legend=len(groups) > 1` (see [Opts System](SKILL.md#opts-system)).
- Legend options belong on the **container** (`Overlay`/`NdOverlay`), not the elements inside
  it — see [Apply at the top level](#apply-at-the-top-level).

```python
overlay.opts(legend_position="top_right", show_legend=len(groups) > 1)
```

## Nested categorical axes

Collapsing two grouping columns into one flat `"a · b"` label forces long, angled ticks.
`Bars`, `Violin`, and `BoxWhisker` accept **multiple kdims** for a nested categorical x-axis —
the inner group sits under the outer group, which reads far cleaner. Order matters: the *last*
kdim is the inner level.

```python
hv.Bars(df, kdims=["model", "task"], vdims=["count"])            # task nested under model
hv.Violin(df, kdims=["model", "task"], vdims=["latency_ms"])
```

`Bars` draws the nested axis via `multi_level=True` (the default). `.opts(multi_level=False)`
flattens it back to one tick per outer group, and `.opts(stacked=True)` turns the second kdim
into stack segments instead of a second axis level. `Bars` accepts at most **3** kdims.

Caveat: a jittered `Scatter`/`Points` overlay can't align to a two-level categorical x. If you
need raw points over the violin/box, build a single flat combined key dimension instead:

```python
df["model · task"] = df["model"] + " · " + df["task"]
hv.Violin(df, kdims=["model · task"], vdims=["latency_ms"]) * hv.Scatter(
    df, "model · task", "latency_ms"
).opts(jitter=0.3, alpha=0.3)
```

Otherwise keep the nested kdims and drop the overlay.

## hvPlot vs .opts

Everything above is written as `.opts()` on HoloViews elements. If you arrived here holding
hvPlot output, it is a HoloViews object, so every option applies unchanged — but hvPlot spells
several of them differently in its own call signature:

| This reference (`.opts()`) | hvPlot call kwarg |
|---|---|
| `xrotation=25` | `rot=25` |
| `legend_position="top_right"` | `legend="top_right"` |
| `show_legend=False` | `legend=False` |
| `show_grid=True` (both axes) | `grid=True` |
| multiple `kdims=[...]` | `by=[...]` |

`rot`, `legend`, and `grid` are hvPlot-only — passing them to `.opts()` raises. The reverse also
holds: `gridstyle` has no hvPlot kwarg, so one-axis gridlines always go through `.opts()`.

- The decluttering options here (`toolbar`, `default_tools`, `active_tools`, `tools`,
  `show_grid`, `gridstyle`, `xaxis`) are plot options. Pass them via `.opts()` — reliable on
  overlays and layouts — or as hvPlot kwargs for a single element. When in doubt, use
  `.opts()` on the final object (see [Apply at the top level](#apply-at-the-top-level)).
- The one thing that does **not** work via `.opts()`: `responsive=True` and `height=` must be
  hvPlot **call arguments**. See [Responsive Sizing](../panel/plotting-in-panel.md#responsive-sizing)
  for why.
