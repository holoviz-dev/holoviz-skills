# HoloViz in Quarto

**Yes — `.qmd` files render live HoloViews, hvPlot, and Panel output.** Quarto's
`{python}` chunks execute through a Jupyter kernel at render time, and the rich
mime bundle a HoloViz object emits (`text/html` plus the Bokeh JS payload) is
passed straight through into the page.

This applies identically to blog posts (`format: html`) and slide decks
(`format: revealjs`). `examples/context_explainer_deck.qmd` is the worked piece.

## Contents

- [Setup](#setup)
- [What survives into the page](#what-survives-into-the-page)
- [Worked snippets](#worked-snippets)
- [Live Python: the panel-convert filter](#live-python-the-panel-convert-filter)
- [Gotchas](#gotchas)

## Setup

Two requirements, both easy to miss because failure is silent:

**1. A Jupyter kernel must be installed.** Quarto shells out to Jupyter to
execute `{python}` chunks. `jupyter` in the environment is not optional:

```bash
conda create -n holoviz-quarto -c conda-forge \
    python=3.12 r-quarto perl jupyter panel hvplot
```

**2. You must call `.extension()` in a chunk.** Nothing else emits the Bokeh
CSS and JavaScript the plots need. Without it the chunk executes, the render
succeeds, and the page shows a blank space where the plot should be.

```{python}
#| include: false
import holoviews as hv
import panel as pn

hv.extension("bokeh")   # same as hvplot.extension("bokeh")
pn.extension()          # only if you display Panel objects
```

`#| include: false` hides the setup chunk's code and its (empty-looking but
script-bearing) output. Put constants, imports, and styling hooks here.

## What survives into the page

Rendered output is HTML and JavaScript. Bokeh's own JS runs; Python does not.
That line decides everything:

| You write | Interactive in the page? | Notes |
|---|---|---|
| `hv.Curve(...)`, `df.hvplot.line(...)` | yes | pan, zoom, hover, linked selection |
| `hv.HoloMap(...)` | yes | every state pre-rendered at build time |
| `df.hvplot.line(..., groupby=…, dynamic=False)` | yes | `dynamic=False` is what pre-renders it |
| `df.hvplot.line(..., groupby=…)` | **no** | `dynamic=True` (the default) needs a live kernel |
| `widget.jslink(plot, value="glyph.line_width")` | yes | the link is compiled to JS |
| `pn.Column(slider, pn.rx(...))` | **no** | the widget moves, nothing responds |
| `pn.Column(...).embed(max_states=N, max_opts=N)` | yes | combinatorial in file size |
| `hv.DynamicMap` with a Python callback | **no** | needs `panel serve` or `panel convert` |

The recurring trap is the pair in the middle: a Panel layout containing a
widget looks correct on the page and does nothing when dragged. `.embed()` is
the fix for small state spaces, `.jslink()` for anything expressible in JS.

## Worked snippets

**A plain interactive chart** — the common case, and all most posts need:

```{python}
import hvplot.pandas
import pandas as pd

df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 3, 2]})
df.hvplot.line(x="x", y="y", height=400, responsive=True)
```

**A widget over pre-rendered states** — `dynamic=False` is load-bearing:

```{python}
df.hvplot.line("x", "y", groupby="freq", dynamic=False,
               responsive=True, height=400)
```

**A Panel layout that actually responds** — bounded state, embedded:

```{python}
slider = pn.widgets.IntSlider(name="Select a value", value=2, start=0, end=10)
pn.Column(pn.rx("You selected: {}").format(slider)).embed(
    max_states=11, max_opts=11)
```

`.embed()` pre-computes every combination of widget states, so file size grows
with the product of the options. Fine for one slider; combinatorial for two.

**A JS-linked control** — no pre-computation, but only JS-expressible changes:

```{python}
plot = df.hvplot.line(x="x", y="y", height=400, responsive=True)
width_slider = pn.widgets.FloatSlider(name="Line Width", start=3, end=10, step=0.1)
width_slider.jslink(plot, value="glyph.line_width")
pn.Column(width_slider, plot)
```

## Live Python: the panel-convert filter

For a genuinely live app inside a Quarto page, the `holoviz-quarto` extension
adds a `{panel-convert-python}` block that builds a Pyodide app in place:

```bash
quarto add awesome-panel/holoviz-quarto
```

```yaml
filters:
  - holoviz/quarto
```

````markdown
```{panel-convert-python}
import panel as pn
pn.extension(design="material")

slider = pn.widgets.IntSlider(name="Select a value", value=10, start=0, end=100)
pn.Column("# Hello Panel + Quarto!",
          pn.rx("You selected: {}").format(slider)).servable()
```
````

Same trade-offs as `panel convert` anywhere else: full Python, several seconds
of first load while Pyodide and the wheels download, and **not offline**. The
extension is community-maintained and was last cut against Quarto 1.3 — check
that it still builds before designing a talk around it.

## Gotchas

- **A missing `.extension()` call fails silently.** The render succeeds and the
  plot area is blank. This is the first thing to check on any blank plot.
- **`fig-cap` on a HoloViews cell produces subfigures and often an empty plot.**
  Use a markdown caption. See
  [Distilling Explanatory Plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md#embedding-fig-cap-makes-subfigures).
- **Charts do not inherit the page's fonts.** Bokeh draws to a canvas outside
  the CSS cascade; you need a hook. Same reference,
  [Fonts](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md#fonts-bokeh-inherits-nothing).
- **A `HoloMap` inside a `pn.Column` loses its widget** — the widget renders and
  does nothing. Yield the HoloMap bare instead.
  ([panel#6131](https://github.com/holoviz/panel/issues/6131), open, milestoned
  v1.10.0.)
- **Setting `widget_location` breaks `dynamic=False` widgets.** Take the default
  position. ([hvplot#1241](https://github.com/holoviz/hvplot/issues/1241), open.)
- **`embed-resources: true` does not inline CDN webfonts.** A theme that
  `@import`s Google Fonts still phones home.
- **Verify the rendered file, not the preview.** `quarto preview` and
  `quarto render` differ; a deck differs again in speaker view and PDF export.
