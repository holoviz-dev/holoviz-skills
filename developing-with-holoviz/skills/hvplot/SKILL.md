---
name: hvplot
description: Plot DataFrames and datasets using a Pandas .plot()-like API for Pandas, Polars, Xarray, DuckDB, Dask, and GeoPandas. Use when the user asks to visualize, plot, or chart tabular or multidimensional data. Do not use for pie charts or 3D viz.
metadata:
  version: "0.0.1"
  author: holoviz
---

# Using hvPlot effectively

This skill provides correct patterns and common pitfalls for hvPlot to effectively visualize data interactively.

Before plotting, consider: what story does the data tell? What comparison matters most? Then choose the plot type, encoding, and labels that make that story obvious.

## Dependencies

Activate the `.hvplot` accessor with the appropriate backend import: `import hvplot.pandas`, `hvplot.polars`, `hvplot.xarray`, `hvplot.duckdb`, or `hvplot.dask`. Backends like Polars and DuckDB must be installed separately. Optional: `datashader` for resampling, `geoviews` or `geopandas` for geographic data.

## Plot Labels

Notes:
1. Label axes and colorbars with descriptive names and units.
2. Titles should tell the story (what, where, when); don't repeat what the axes already show.
3. Compute dynamic labels (date ranges, region names) as variables before the plot call to keep it readable.
4. Use `coastline` or `tiles` for geographic context on geospatial plots.

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

## Hover Tooltips

Notes:
1. Pair `hover_cols` with `hover_tooltips`: columns not used as x/y/color are not sent to the client by default, producing `???` in tooltips.
2. Only include the columns you need to avoid sending all data to the client.
3. `hover_tooltips` replaces the deprecated `hover_formatters` — models may hallucinate the old name.
4. Bokeh format syntax: `{0.1f}` floats, `{0,0}` thousands, `{%F %H:%M}` datetimes. Literal text like `km` can follow the format.

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

Notes:
1. `color=` and `size=` are vectorized; they scale to large data. Use `cmap=`/`clabel=` with color, `scale=` with size.
2. `by=` overlays color-coded layers with a legend; useful for stacked/side-by-side bars.
3. `groupby=` adds a dropdown widget to filter to one category at a time.
4. `by=` and `groupby=` loop over categories, creating a separate element per value. Slow with many categories; prefer `color=` for high-cardinality columns.
5. Options not directly exposed by hvPlot (e.g. `color_levels` for a discrete colorbar) can be set via `.opts("Points", ...)`. Use `cticks=` and `clim=` in hvPlot to control colorbar tick count and range.

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

Notes:
1. If data exceeds 100k points, consider `rasterize=True` over `datashade=True`. Rasterize aggregates server-side but colormaps in the browser, preserving hover tooltips, colorbars, and `cnorm`/`cmap` control. Datashade sends an opaque RGB image — use it only for categorical color mixing (`aggregator='count_cat'`).
2. `resample_when=N` disables resampling when the viewport contains fewer than N points (e.g. after zooming in), effectively creating a dynamic overlay that toggles opacity of either the rasterized or original layer. However, because it is an overlay, it can be finicky and may cause confusion, e.g. the hover tooltips will only work when the original layer is active.

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

Notes:
1. Sort values so the largest is at top (or bottom) for easy comparison.
2. Use a single neutral color by default; reserve color encoding for when it maps to data.
3. Simplify when labels carry the information: `xaxis=False`, `yaxis=False`, `show_frame=False`.
4. Overlay `hvplot.labels` to show values directly on bars, eliminating the need for axis ticks entirely.
5. `backend_opts` accesses the underlying plotting library's model properties (e.g. `"outline_line_alpha": 0` to hide the frame in Bokeh). `.opts()` accesses HoloViews-level plot options (e.g. `show_frame=False`). Use either for styling not exposed by hvPlot directly.
6. Use `NumeralTickFormatter(format='0a')` for large-number axes (e.g. 1.2M, 500K). Pass via `xformatter=` or `yformatter=`.
7. Use `fontscale=` to increase readability; `padding=` to add room for labels.
8. This example is heavily stylized to illustrate what's possible; use discretion.

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

## Timeseries

Notes:
1. `subcoordinate_y=True` gives each series its own y sub-axis — useful for multi-stock views with different scales.
2. Access datetime index components directly: `'index.month'`, `'index.hour'`, `'index.year'` work inside hvPlot for aggregation.
3. Use `xformatter=DatetimeTickFormatter(months='%b %Y')` for custom date formatting.
4. For large timeseries, use `downsample=True` (LTTB algorithm) to reduce points sent to the browser while preserving visual shape. Updates dynamically on zoom.

```python
import hvplot.pandas  # noqa
import numpy as np

apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')
stocks = hvplot.sampledata.stocks('pandas').set_index('date')

# Each series gets its own y sub-axis
stocks.hvplot.line(y=['Apple', 'Amazon', 'Google', 'Meta'], subcoordinate_y=True)

# Aggregate by datetime component
apple.hvplot.heatmap(x='index.hour', y='index.month', C='close', cmap='reds', reduce_function=np.mean)
```

## Subplots and Layouts

Notes:
1. `subplots=True` gives each `y` column its own panel. Axes are linked by default; use `shared_axes=False` for independent ranges.
2. `.cols(N)` controls columns per row.
3. `col=` / `row=` creates a faceted grid by category — cleaner than `subplots` for categorical splits.

```python
stocks = hvplot.sampledata.stocks("pandas")

# Linked subplots, 2 per row
stocks.hvplot(
    x="date", y=["Apple", "Amazon", "Google"],
    subplots=True, shared_axes=False,
    width=300, height=200,
).cols(2)

penguins = hvplot.sampledata.penguins("pandas")

# Faceted grid: one panel per species × island
penguins.hvplot.scatter(
    x="bill_length_mm", y="bill_depth_mm",
    col="species", row="island", alpha=0.5,
)
```

## Statistical Functions

These are **top-level functions**, not `.hvplot` accessor methods:

```python
import hvplot
import hvplot.pandas  # noqa

penguins = hvplot.sampledata.penguins('pandas')[[
    'bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g', 'species'
]].dropna()
apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')

hvplot.scatter_matrix(penguins, c='species')          # pairwise scatter with linked brushing
hvplot.parallel_coordinates(penguins, 'species')       # multivariate structure
hvplot.andrews_curves(penguins, 'species')             # Fourier-series class separation
hvplot.lag_plot(apple[['close']], lag=5, alpha=0.3)    # autocorrelation detection
```