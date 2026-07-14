---
name: hvplot
description: Plot DataFrames and datasets using a Pandas .plot()-like API for Pandas, Polars, Xarray, DuckDB, Dask, and GeoPandas. Use when the user asks to visualize, plot, or chart tabular or multidimensional data. Do not use for pie charts or 3D viz, or for element composition, streams, or custom Bokeh tools/tooltips (use HoloViews).
metadata:
  version: "0.0.3"
  author: holoviz
---

# Using hvPlot

This skill provides correct patterns and common pitfalls for hvPlot to visualize data interactively.

Before plotting, consider: what story does the data tell? What comparison matters most? Then choose the plot type, encoding, and labels that make that story obvious. For publication-quality figures needing fine-grained control, use HoloViews directly with the Matplotlib backend instead of Bokeh.

## Contents

- [Dependencies](#dependencies)
- [Serving and Iterating](#serving-and-iterating)
- [Plot Labels](#plot-labels)
- [Geographic Plots](#geographic-plots)
- [Hover Tooltips](#hover-tooltips)
- [Managing Dimensions](#managing-dimensions)
- [Big Data](#big-data)
- [Styling](#styling)
- [Interaction](#interaction)
- [Timeseries](#timeseries)
- [Subplots and Layouts](#subplots-and-layouts)
- [Statistical Functions](#statistical-functions)

## Dependencies

Activate the `.hvplot` accessor with the appropriate backend import: `import hvplot.pandas`, `hvplot.polars`, `hvplot.xarray`, `hvplot.duckdb`, or `hvplot.dask`. Backends like Polars and DuckDB must be installed separately. Optional: `datashader` for resampling, `geoviews` or `geopandas` for geographic data. Prefer the Bokeh backend (default) for interactivity, Matplotlib for static/print output, Plotly as a last resort.

Any example below (or elsewhere in this skill set) that calls `hvplot.sampledata.<name>(...)` (e.g. `penguins`, `earthquakes`, `apple_stocks`, `stocks`) requires the separate `hvsampledata` package. It is not installed by hvPlot itself — install it explicitly (`pip install hvsampledata` / `conda install hvsampledata`) or the call raises `AttributeError: Install the package 'hvsampledata' to access datasets from the 'sampledata' module of hvPlot.`

Do NOT add `import holoviews as hv` or `hv.extension('bokeh')` to hvplot-only code. `import hvplot.pandas` activates the Bokeh backend automatically. Only import holoviews when you need HoloViews elements or containers like VLine, HLine, Text, Overlay, etc. For `.opts()` system, formatters, Bokeh tools, streams, and other HoloViews concepts, see the [HoloViews skill](../holoviews/SKILL.md).

```python
# WRONG — redundant import, do not do this
import holoviews as hv
import hvplot.pandas

# CORRECT — hvplot.pandas is sufficient
import hvplot.pandas
```

## Serving and Iterating

To serve an hvPlot visualization as a Panel app for interactive development:

```python
import hvplot.pandas  # noqa
import panel as pn

pn.extension()

plot = df.hvplot.scatter(x="col_a", y="col_b")
pn.pane.HoloViews(plot).servable()
```

Run with `panel serve app.py --dev --show`. See the [Panel skill](../panel/SKILL.md) for the full Viewer class pattern and [Iterating on Panel Apps](../panel/iterating-on-panel-apps.md) for the serve → screenshot → debug loop.

## Plot Labels

- Label axes and colorbars with descriptive names and units.
- Titles should tell the story (what, where, when); don't repeat what the axes already show.
- Compute dynamic labels (date ranges, region names) as variables before the plot call to keep it readable.
- Use `coastline` or `tiles` for geographic context on geospatial plots.

```python
import hvplot.pandas  # noqa

earthquakes = hvplot.sampledata.earthquakes("pandas")
time_range_label = f"({earthquakes['time'].min():%b %Y} to {earthquakes['time'].max():%b %Y})"
title = f"Indonesian Archipelago Earthquakes {time_range_label}"
earthquakes.hvplot.points(
    x="lon",
    y="lat",
    color="mag",
    xlabel="Longitude (°E)",
    ylabel="Latitude (°N)",
    clabel="Magnitude",
    title=title,
    coastline=True,
)
```

## Geographic Plots

- `geo=True` enables geographic (web-mercator) projection and tile basemaps. Requires `geoviews` to be installed.
- `tiles=` accepts these built-in strings: `"CartoDark"`, `"CartoLight"`, `"CartoMidnight"`, `"OSM"`, `"EsriImagery"`, `"EsriTerrain"` or ``xyzservices.TileProvider`` instances **Do not use `"CartoDB.DarkMatter"`, `"CartoDB Dark_Matter"`.** See https://hvplot.holoviz.org/en/docs/latest/ref/plotting_options/geographic.html#tiles
- Do not convert to a GeoDataFrame or reproject to EPSG:3857 manually. Pass `geo=True` and hvplot handles projection.

```python
import hvplot.pandas  # noqa

earthquakes = hvplot.sampledata.earthquakes("pandas")
earthquakes.hvplot.points(
    x="lon",
    y="lat",
    geo=True,
    tiles="CartoDark",       # correct — do NOT use "CartoDB.DarkMatter"
    color="mag",
    cmap="viridis_r",
    clabel="Magnitude",
    size=6,
    alpha=0.8,
    hover_cols=["place", "time", "mag", "depth"],
    responsive=True,
    title="Earthquakes colored by magnitude",
)
```

## Hover Tooltips

- Pair `hover_cols` with `hover_tooltips`: columns not used as x/y/color are not sent to the client by default, producing `???` in tooltips.
- Only include the columns you need to avoid sending all data to the client.
- `hover_formatters` is deprecated and should not be used. Do not pass it even alongside `hover_tooltips`. Format datetimes inline in the tooltip string instead.
- Bokeh format syntax: `{0.1f}` floats, `{0,0}` thousands, `{%F %H:%M}` datetimes. Literal text like `km` can follow the format.

```python
...
earthquakes.hvplot.points(
    ...,
    hover_tooltips=[
        ("Place", "@place"),
        ("Time", "@time{%F %H:%M}"),
        ("Magnitude", "@mag{0.1f}"),
        ("Depth", "@depth{0.0f} km"),
    ],
    hover_cols=["place", "time", "mag", "depth"],
    title=title,
    coastline=True,
)
```

## Managing Dimensions

- `color=` and `size=` are vectorized; they scale to large data. Use `cmap=`/`clabel=` with color, `scale=` with size.
- `by=` overlays color-coded layers with a legend; useful for stacked/side-by-side bars.
- `groupby=` adds a dropdown widget to filter to one category at a time.
- `by=` and `groupby=` loop over categories, creating a separate element per value. Slow with many categories; prefer `color=` for high-cardinality columns.
- Options not directly exposed by hvPlot (e.g. `color_levels` for a discrete colorbar) can be set via `.opts("Points", ...)`. Use `cticks=` and `clim=` in hvPlot to control colorbar tick count and range.

```python
...
earthquakes.hvplot.points(
    ...,
    color="mag",
    cmap="viridis_r",
    clabel="Magnitude",
    cticks=5,
    clim=(4, 7),
    size="depth",
    scale=0.5,
).opts("Points", color_levels=6)
```

## Big Data

- If data exceeds 100k points, consider `rasterize=True` over `datashade=True`. Rasterize aggregates server-side but colormaps in the browser, preserving hover tooltips, colorbars, and `cnorm`/`cmap` control. Datashade sends an opaque RGB image — use it only for categorical color mixing (`aggregator='count_cat'`).
- `resample_when=N` disables resampling when the viewport contains fewer than N points (e.g. after zooming in), creating a dynamic overlay that toggles opacity of either the rasterized or original layer. However, because it is an overlay, it can be finicky and may cause confusion, e.g. the hover tooltips will only work when the original layer is active.

```python
...
earthquakes.hvplot.points(
    ...,
    coastline=True,
    rasterize=True,
    resample_when=5000,
)
```

## Styling

- Sort values so the largest is at top (or bottom) for easy comparison.
- For `barh`, `.set_index("category")` before plotting. Without this, `sort_values()` leaves a numeric index that renders as NaN on the y-axis.
- Use a single neutral color by default; reserve color encoding for when it maps to data. Use `c="column", cmap={val: "#hex", ...}` for categorical coloring (a list of hex values via `color=` does not work for bar/barh). For stacked bars with `by=`, pass the same dict via `cmap=`.
- Simplify when labels carry the information: `xaxis=False`, `yaxis=False`, `show_frame=False`.
- Overlay `hvplot.labels` to show values directly on bars, eliminating the need for axis ticks entirely. Pass `responsive=True` and `hover=False` on both plot and labels calls. Inside bars: `y="pos"` where `pos = value * 0.98`, `text_align="right"`, `text_color="white"`. Outside bars: `pos = value + offset`, `text_align="left"`, `text_color="black"`. For stacked bars + labels, the labels DataFrame must include stacked columns via `hover_cols`.
- `backend_opts` accesses Bokeh model properties (e.g. `"outline_line_alpha": 0`). `.opts()` accesses HoloViews plot options (e.g. `show_frame=False`).
- Prefer hvPlot kwargs over `.opts()` — they take precedence. Pass `responsive=True` in the hvPlot call, not via `.opts()`, which can conflict with default dimensions.
- Use `NumeralTickFormatter(format='0a')` for large-number axes via `xformatter=`/`yformatter=`.
- Use `fontscale=` for readability.
- This example is heavily stylized to illustrate what's possible; use discretion.

```python
import hvplot.pandas  # noqa

earthquakes = hvplot.sampledata.earthquakes("pandas")

counts = earthquakes.value_counts("depth_class").sort_values()
counts = counts.reset_index().assign(**{"position": counts.values + 3})

barh = counts.hvplot.barh(
    x="depth_class",
    y="count",
    title="Most Earthquakes Occur at Shallow Depths",
    color="#4e79a7",
    hover_tooltips=[("Depth Class", "@depth_class"), ("Count", "@count{0,0}")],
    hover_cols=["depth_class", "count"],
    xaxis=False,
    yaxis="bare",
    legend=False,
    fontscale=1.35,
    padding=(0, 0.25),
    backend_opts={"plot.toolbar.autohide": True, "plot.outline_line_alpha": 0},
).opts(show_frame=False)

labels = counts.hvplot.labels(
    x="depth_class",
    y="position",
    text="{count} {depth_class}",
    hover_cols=["count"],
    text_align="left",
    text_color="black",
)
barh * labels
```

## Interaction

- Hide the toolbar for polished output: `backend_opts={"plot.toolbar.autohide": True}` (shows on hover) or `.opts(toolbar=None)` (removes entirely). Hide on secondary panels in a layout (e.g. the bottom chart) and keep on the main chart.
- For timeseries, use `hover_mode='vline'` to snap the crosshair to the nearest x-value — much easier to read than the default point hover.
- Configure wheel zoom axis: `tools=['xwheel_zoom']` for timeseries (zoom x only), `tools=['ywheel_zoom']` for vertical, or default `'wheel_zoom'` for both. Replace the active tool with `active_scroll=`.

```python
# Timeseries with vline crosshair, x-only zoom, toolbar hidden
apple.hvplot.line(
    y='close',
    hover_mode='vline',
    tools=['xwheel_zoom'],
    active_tools=['xwheel_zoom'],
    responsive=True, height=300,
).opts(toolbar=None)
```

## Timeseries

- `subcoordinate_y=True` gives each series its own y sub-axis — useful for multi-stock views with different scales.
- Access datetime index components directly: `'index.month'`, `'index.hour'`, `'index.year'` work inside hvPlot for aggregation.
- Use `xformatter=DatetimeTickFormatter(months='%b %Y')` for custom date formatting.
- For large timeseries, use `downsample=True` (LTTB algorithm) to reduce points sent to the browser while preserving visual shape. Updates dynamically on zoom.

```python
import hvplot.pandas  # noqa
import numpy as np
from bokeh.models.formatters import DatetimeTickFormatter

apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')
stocks = hvplot.sampledata.stocks('pandas').set_index('date')

# Each series gets its own y sub-axis
stocks.hvplot.line(y=['Apple', 'Amazon', 'Google', 'Meta'], subcoordinate_y=True)

# Custom date formatting + LTTB downsampling
apple.hvplot.line(
    y='close',
    xformatter=DatetimeTickFormatter(months='%b %Y'),
    downsample=True,
)

# Aggregate by datetime component
apple.hvplot.heatmap(x='index.hour', y='index.month', C='close', cmap='reds', reduce_function=np.mean)
```

## Subplots and Layouts

- `col=`/`row=` creates a cleaner faceted grid than `subplots=True` for categorical splits. Use `shared_axes=False` for independent ranges.
- Narrow subplots (e.g. `width=300`) crowd datetime tick labels until they overlap. Pass a lower `xticks=` count (an integer, not a rotation) so fewer labels are drawn and they stay readable — `xrotation=` does not affect hvPlot/Bokeh datetime axes.

```python
stocks = hvplot.sampledata.stocks("pandas")

# Linked subplots, 2 per row — xticks keeps narrow datetime axes readable
stocks.hvplot(
    x="date", y=["Apple", "Amazon", "Google"],
    subplots=True, shared_axes=False,
    width=300, height=200, xticks=4,
).cols(2)

penguins = hvplot.sampledata.penguins("pandas")

# Faceted grid: one panel per species × island
penguins.hvplot.scatter(
    x="bill_length_mm", y="bill_depth_mm",
    col="species", row="island", alpha=0.5,
)
```

## Statistical Functions

These are **top-level functions**, not `.hvplot` accessor methods.

- `parallel_coordinates` plots each numeric column on its own vertical axis but shares one y-scale across all of them. If the columns have very different magnitudes (e.g. `body_mass_g` in the thousands next to `bill_length_mm` in the tens), the small-scale columns flatten to a line near zero and the chart stops being readable. Normalize/rescale columns to a common range (e.g. min-max or z-score) before passing them in, unless they're already comparable.

```python
import hvplot
import hvplot.pandas  # noqa

penguins = hvplot.sampledata.penguins('pandas')[[
    'bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g', 'species'
]].dropna()
apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')

hvplot.scatter_matrix(penguins, c='species')          # pairwise scatter with linked brushing

# Rescale to [0, 1] first — parallel_coordinates shares one y-axis across all columns
normalized = penguins.copy()
num_cols = ['bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g']
normalized[num_cols] = (normalized[num_cols] - normalized[num_cols].min()) / (
    normalized[num_cols].max() - normalized[num_cols].min()
)
hvplot.parallel_coordinates(normalized, 'species')     # multivariate structure

hvplot.andrews_curves(penguins, 'species')             # Fourier-series class separation
hvplot.lag_plot(apple[['close']], lag=5, alpha=0.3)    # autocorrelation detection
```
