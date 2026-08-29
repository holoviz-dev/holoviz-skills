# Distilling Explanatory Plots

An explanatory plot is for an audience: it makes one point and strips away everything that
doesn't serve it — the opposite of [Composing Exploratory Plots](composing-exploratory-plots.md),
which shows everything and invites interaction.

This file covers both the **design** (what to show) and the **mechanics**
(what breaks when you embed it). The design sections apply to any chart; the
mechanics sections are the silent failures that look correct in a notebook
and wrong in the output.

## Contents

**Design:**

- [Lead with the takeaway](#lead-with-the-takeaway)
- [Subtract to one message](#subtract-to-one-message)
- [Direct labels, not a legend](#direct-labels-not-a-legend)
- [Gray context, one highlight](#gray-context-one-highlight)
- [Annotate in the static view](#annotate-in-the-static-view)
- [Kill chart junk](#kill-chart-junk)
- [Show uncertainty](#show-uncertainty)
- [Example](#example)

**Publication mechanics:**

- [Fonts: Bokeh inherits nothing](#fonts-bokeh-inherits-nothing)
- [Glyph text properties are dataspecs](#glyph-text-properties-are-dataspecs)
- [The invert_axes traps](#the-invert_axes-traps)
- [Embedding: fig-cap makes subfigures](#embedding-fig-cap-makes-subfigures)
- [Never wrap a plot pane in a pmui layout](#never-wrap-a-plot-pane-in-a-pmui-layout)
- [A reusable theme hook](#a-reusable-theme-hook)

## Lead with the takeaway

The title is the finding, not the variable: `"Skills cut output tokens 38%"`, not
`"Tokens by variant"`. The chart proves a sentence the reader has already read.

## Subtract to one message

Keep the single mark that makes the point and drop the rest — where the exploratory view
layered violin, box, and scatter across facets, the explanatory version is usually one series
or one comparison. Pick the encoding that makes it trivial: sorted bars for a ranking, a line
for a trend, a slope or dumbbell for before/after.

## Direct labels, not a legend

Label the series on the mark itself with `hv.Text` at the line end (or `hv.Labels`) and set
`show_legend=False`, so the eye never leaves the data to decode a color key.

## Gray context, one highlight

Mute everything to gray and give the highlight color only to the series that
carries the message. One focus, one color encoding per figure.

## Annotate in the static view

Mark the point with `hv.Text`, `hv.VLine`/`hv.HLine`, or an arrow — the event, the threshold,
the delta. Assume no interaction: readers won't hover, so the static view must carry the whole
message. Set `toolbar=None`, or control which tools appear via `default_tools=[]` / `tools=[]`, rather than relying on hover tooltips — see [Decluttering Plots](../holoviews/decluttering-plots.md) for the full toolbar/tools guidance.

## Kill chart junk

Pin the axis range to the data (`ylim=`/`xlim=`); an auto-range that pads to round
numbers leaves dead whitespace. Drop gridlines (`show_grid=False`), thin the
ticks, and remove the toolbar.

## Show uncertainty

When the point rests on noisy estimates, show the spread (a band, error bars, a
range) rather than rounding to a single confident number.

## Example

Median fuel economy over time, with the takeaway as the title, the oil shocks
annotated in place, one highlight color, and no toolbar:

```python
import hvplot.pandas  # noqa
import holoviews as hv

trend = df.hvplot.line("year", "mpg", color="#c0392b", line_width=3)
shock = hv.VLine(1979).opts(color="#bbbbbb", line_dash="dashed")
note = hv.Text(1979, 19, "1979 oil crisis").opts(text_align="left", text_color="#888")

(trend * shock * note).opts(
    title="Fuel economy nearly doubled in a decade",
    toolbar=None, show_grid=False, show_legend=False, ylim=(10, 38),
)
```

To assemble several explanatory charts into a scrollable narrative, see
[Data Storytelling](../panel/data-storytelling.md).


## Fonts: Bokeh inherits nothing

A Quarto theme or a pmui `theme_config` reaches every heading on the page and
**no axis label**. Bokeh draws text to a canvas, outside the CSS cascade, so the
prose uses your brand face and the charts keep Bokeh's default. On a page that
mixes the two this reads as sloppiness, and nothing warns you.

Push the stack on with a `hooks` function (see the [reusable hook](#a-reusable-theme-hook)).

**Two compounding traps:**

- **A font you merely name is not loaded.** Selecting `"Poppins, sans-serif"`
  does not deliver Poppins. On a canvas the fallback is silent. Verify by
  rendering the target beside a face that certainly exists and comparing
  letterforms — identical means it did not load.
- **Do not name a family you have not delivered.** Naming a mono you never
  loaded gets you Courier, which looks like a choice rather than the accident it
  is. Keep the stack to faces that actually resolve, and end it with a fallback
  the brand sanctions.

**Use sans-serif on charts.** Mono tick labels suit a dense data tool where
columns of numbers must align; in an editorial chart they are a second typeface
doing no work. If you want digits to align, `font-variant-numeric: tabular-nums`
on the body face beats reaching for mono.


## Glyph text properties are dataspecs

Setting a font on an annotation through `.opts()` does not work:

```python
# WRONG — Bokeh reads the string as a COLUMN NAME and warns
#   "attempted to retrieve property array for nonexistent field 'Inter, ...'"
hv.Text(x, y, "label").opts(text_font="Inter, sans-serif")

# CORRECT — set it on the glyph in a hook, wrapped in value()
from bokeh.core.properties import value

def hook(plot, element):
    for r in plot.state.renderers:
        glyph = getattr(r, "glyph", None)
        if glyph is not None and hasattr(glyph, "text_font"):
            glyph.text_font = value("Inter, sans-serif")
```

Glyph properties are *dataspecs*: a bare string means "look up this column".
Axis properties are ordinary model properties, so a plain string is fine there —
which is why the same value works on `axis.major_label_text_font` and fails on
`glyph.text_font`.


## The invert_axes traps

`invert_axes=True` on `hv.Bars` gives horizontal bars, and two options then
disagree about which axis they mean:

- **The numeric formatter must be `xformatter`.** After inversion the value axis
  is x. A `yformatter` lands on the *category* axis and renders every tick as
  `NaN`.
- **But `xlabel` still follows the pre-inversion dimension**, so it renders
  rotated and clipped down the left edge.

The reliable move is to drop axis labels entirely on a comparison bar chart. The
title states the finding and the tick format carries the unit:

```python
hv.Bars(pairs).opts(
    color=hv.dim("x").categorize(colors), line_color="white", line_width=2,
    invert_axes=True, axiswise=True,
    xlabel="", ylabel="",                                   # not xlabel=unit
    xformatter=NumeralTickFormatter(format="0a"),           # not yformatter
    title="Editing reads 73% less",
)
```

`axiswise=True` matters when more than one bar chart appears in a document:
without it they share the categorical axis and each shows the other's rows.


## Embedding: fig-cap makes subfigures

A HoloViews object emits a multi-part mime bundle (`text/html` plus
`application/vnd.holoviews_exec.v0+json`). In Quarto, adding `#| fig-cap` to
such a cell makes it treat those parts as **subfigures** — you get `(a)` and
`(b)` labels and, frequently, one empty plot container.

Do not use `fig-cap` on a cell that emits a HoloViews or Panel object. Write the
caption as markdown after the chunk instead:

```python
#| echo: false
cost_curve()
```

::: {.caption}
What you typed against what was processed.
:::

Related: put `hv.extension("bokeh")` / `pn.extension()` in a chunk marked
`#| include: false`. Inside a folded `code-fold` block the load bundle can fail
to initialise the first plot on the page, which renders as an empty frame while
later plots work.


## Never wrap a plot pane in a pmui layout

`pmui.Column` / `pmui.Row` are ESM/React components, so children can paint
before the layout has sized them — a plot inside one can render blank. Use
`pn.Column` / `pn.Row` as the immediate wrapper around any plot pane, and keep
pmui for the shell that actually carries styling (`Paper`, `Card`, `Container`,
`Grid`):

```python
pmui.Paper(                       # styled shell — fine
    pn.Column(                    # plain layout immediately around the pane
        pn.pane.HoloViews(fig)
    ),
    elevation=0,
    sx={"border": "1px solid #dadde2", "borderRadius": "14px", "padding": "8px"},
)
```


## A reusable theme hook

One hook, applied through a shared `BASE` dict so every chart in the artifact
reads as one family. Declare your typefaces and palette once at the top of the
module and every chart inherits them:

```python
from bokeh.core.properties import value

# ── Set these to match the project or organisation ──────────────
DISPLAY = "Verdana, sans-serif"        # titles and headings
BODY    = "Verdana, sans-serif"        # axes, labels, annotations
INK     = "#1a1a1a"                    # primary text
MUTED   = "#6b7280"                    # secondary text (axis labels)
HAIRLINE = "#d1d5db"                   # rules and tick marks
# ────────────────────────────────────────────────────────────────

def font_hook(plot, element):
    fig = plot.state
    if fig.title is not None:
        fig.title.text_font = DISPLAY
        fig.title.text_font_style = "bold"
        fig.title.text_font_size = "15pt"
        fig.title.text_color = INK
    for axis in fig.axis:
        axis.axis_label_text_font = BODY
        axis.axis_label_text_font_style = "normal"   # Bokeh italicises by default
        axis.axis_label_text_color = MUTED
        axis.major_label_text_font = BODY
        axis.major_label_text_color = MUTED
        axis.axis_line_color = HAIRLINE
        axis.major_tick_line_color = HAIRLINE
        axis.minor_tick_line_color = None
    fig.outline_line_color = None
    for r in fig.renderers:                          # annotations
        glyph = getattr(r, "glyph", None)
        if glyph is not None and hasattr(glyph, "text_font"):
            glyph.text_font = value(BODY)

BASE = dict(toolbar=None, show_grid=False, show_legend=False,
            hooks=[font_hook], fontscale=1.05)
```

The five constants at the top are the only lines that change between projects.
The hook itself stays the same.

`axis_label_text_font_style = "normal"` is worth keeping: Bokeh italicises axis
labels by default, which almost never matches a brand.

Keep the model constants that drive the numbers in the same module as these
builders, so the post and the deck derive from one source and a changed constant
updates both.
