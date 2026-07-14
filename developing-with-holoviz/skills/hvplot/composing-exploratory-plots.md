# Composing Exploratory Plots

Reach for this when one plot type isn't enough — you want a metric at several
levels of detail and compared across groups. These are the composition decisions
a single `.hvplot` call won't make for you.

## Contents

- [Lay out for comparison](#lay-out-for-comparison)
- [Layer marks at multiple resolutions](#layer-marks-at-multiple-resolutions)
- [Establish visual hierarchy](#establish-visual-hierarchy)
- [Compose only compatible elements](#compose-only-compatible-elements)
- [Order and type dimensions](#order-and-type-dimensions)
- [Cross-filter with linked selections](#cross-filter-with-linked-selections)
- [Example](#example)

## Lay out for comparison

Put small multiples in a row or grid with a shared axis so values compare at a
glance; facet with `groupby=`, then `.layout().cols(n)` (or `.grid()`). Don't
stack panels vertically or let each panel scale its own axis when the point is to
compare — the reader can't eyeball differences across independent scales.

## Layer marks at multiple resolutions

Overlay marks that show the same data at different resolutions, composed with
`*`: shape/density (`violin`, `kde`, `hist`), summary (`box`, error bars, a mean
line), and raw (`scatter`/`points`, jittered). The figure then reads at a glance
and rewards a closer look.

## Establish visual hierarchy

Mute the context layers so the focus stands out: `box_fill_alpha=0`,
`violin_fill_alpha=0`, one neutral/black color, `legend=False` on redundant
layers, low `alpha` plus jitter on raw points. Keep one focus layer and one color
encoding per figure; left alone a model stacks competing fills and legends. For
the `.opts()` mechanics behind these, see the [HoloViews skill](../holoviews/SKILL.md).

## Compose only compatible elements

Overlaid elements must share key dimensions and axis types. The trap: only
`Bars`/`Violin`/`BoxWhisker` accept a two-level categorical x, while
`Scatter`/`Points` don't, so you can't overlay raw points on a `by=`-plus-inner
violin. When the marks disagree, facet the outer category with `groupby=` and
overlay within each panel, where a single categorical x works for all of them.

## Order and type dimensions

Make categories ordered (`pd.cut(..., ordered=True)`, then sort) and use datetime
dtypes, so facets and axes read in a meaningful order rather than alphabetically.

For line and area plots, sort by the x (key) dimension first: HoloViews connects
points in row order, so unsorted data draws a self-crossing zigzag instead of a
clean line.

## Cross-filter with linked selections

For interactive exploration (a live notebook or Panel app on the bokeh backend),
link the plots so a box or lasso selection in one cross-filters the rest, showing
how the selected subset distributes across every dimension. Build one reusable
linker and apply it to the composed layout:

```python
ls = hv.link_selections.instance()
ls(scatter + hist + table)
```

Don't add `box_select`/`lasso_select` tools yourself: `link_selections` adds
them, and adding them manually breaks the linking. `box_select` scales to large
data; `lasso_select` is finer but slower and needs `shapely` (`pyarrow` is
required at runtime either way). This is interactive-only, so it belongs in
exploration, not a static explanatory export. See the
[HoloViews skill](../holoviews/SKILL.md) for the mechanics.

## Example

Distribution of `mpg` across `origin`, faceted by an ordered efficiency band,
with a muted box for quartiles and jittered points for the raw data:

```python
import hvplot.pandas  # noqa
import pandas as pd

autompg = pd.read_csv("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/mpg.csv")
autompg["categories"] = pd.cut(
    autompg["mpg"], bins=[0, 10, 20, 30, 40],
    labels=["inefficient", "average", "efficient", "very efficient"], ordered=True,
)
autompg = autompg.dropna().sort_values("mpg")

violin  = autompg.hvplot.violin(y="mpg", by="origin", groupby="categories", width=250, violin_fill_alpha=0)
scatter = autompg.hvplot.scatter(x="origin", y="mpg", groupby="categories", width=250, alpha=0.25, color="black").opts(jitter=0.75)
box     = autompg.hvplot.box(y="mpg", by="origin", groupby="categories", width=250, box_fill_alpha=0, box_width=0.5, legend=False)

(violin * scatter * box).layout().cols(len(autompg["categories"].cat.categories))
```

`groupby="categories"` becomes the facet dimension once `.layout()` turns the
`HoloMap` into panels; the three marks share a single categorical `origin` x
within each panel, and the box and jittered scatter recede so the violin reads
first.
