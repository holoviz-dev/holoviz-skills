---
name: hvplot
description: Best practices for quick exploratory data analysis with minimal code using HoloViz hvPlot's Pandas-like .plot API. Use when the user asks to visualize data, create interactive plots or charts, explore datasets, build dashboards with Panel, or work with Pandas/Polars/Xarray DataFrames.
metadata:
  version: "0.0.1"
  author: holoviz
  category: data-visualization
  difficulty: intermediate
---

# hvPlot Development Skills

This document provides best practices for developing plots and charts with HoloViz hvPlot in notebooks and .py files.

Please develop as an **Expert Python Developer** developing advanced data-driven analytics and testable data visualisations, dashboards and applications would do. Keep the code short, concise, self-contained, documented, testable and professional.

## When to use

- User asks to visualize, plot, or chart data
- User mentions exploratory data analysis (EDA) or data exploration
- User needs interactive visualizations with Pandas, Polars, or Xarray
- User wants to create dashboards or data apps with Panel
- User needs to handle large datasets (100K+ points) with rasterization or downsampling
- User asks for geographic/map visualizations with tile layers

Do not use for: Static publication-quality figures with complex customization (use HoloViews directly with matplotlib backend instead), 3D visualizations, pie charts (not supported).

## Examples

**Input:** "Create a line plot showing Apple stock closing prices over time"

**Output:**

```python
import hvplot.pandas
apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')
apple.hvplot.line(y='close', title='Apple Close Price', ylabel='USD')
```

**Input:** "Visualize earthquake magnitude distribution with a histogram"

**Output:**

```python
import hvplot.pandas
earthquakes = hvplot.sampledata.earthquakes('pandas')
earthquakes.hvplot.hist('mag', title='Earthquake Magnitude Distribution')
```

**Input:** "Plot earthquakes on a map with magnitude shown by color"

**Output:**

```python
import hvplot.pandas
earthquakes = hvplot.sampledata.earthquakes('pandas')
earthquakes.hvplot.points('lon', 'lat', tiles=True, color='mag', cmap='fire')
```

## Dependencies

Core dependencies provided with the `hvplot` Python package:

- **hvplot**: Core visualization framework
- **holoviews**: Declarative data visualization library with composable elements. Best for: complex multi-layered plots, advanced interactivity (linked brushing, selection), when you need fine control over plot composition, scientific visualizations. More powerful but steeper learning curve than hvPlot. hvPlot is built upon holoviews.
- **colorcet**: Perceptually uniform colormaps
- **panel**: Provides widgets and layouts enabling tool, dashboard and data app development.
- **param**: A declarative approach to creating classes with typed, validated, and documented parameters. Fundamental to the reactive programming model of hvPlot and the rest of the HoloViz ecosystem.
- **pandas**: Industry-standard DataFrame library for tabular data. Best for: data cleaning, transformation, time series analysis, datasets that fit in memory. The default choice for most data work.

Optional dependencies from the HoloViz Ecosystem:

- **datashader**: Renders large datasets (millions+ points) into images for visualization. Best for: big data visualization, geospatial datasets, scatter plots with millions of points, heatmaps of dense data. Requires hvPlot or HoloViews as frontend.
- **geoviews**: Geographic data visualization with map projections and tile sources. Best for: geographic/geospatial plots, map-based dashboards, when you need coordinate systems and projections. Built on HoloViews, works seamlessly with hvPlot.
- **hvsampledata**: Shared datasets for the HoloViz projects.

## Installation for Development

```bash
pip install hvplot panel watchfiles
```

For development in .py files DO always include watchfiles for Panel hotreload.

## Reference Data Exploration Example

Below is a simple reference example for data exploration.

```python
import hvplot.pandas  # noqa: F401
# DO import panel if working in .py files
import panel as pn
# DO always run pn.extension() to load panel javascript extensions
pn.extension()

data = hvplot.sampledata.earthquakes('pandas')

mag_class_counts = data.groupby('mag_class').size().reset_index(name='counts')

plot = mag_class_counts.hvplot.bar(x='mag_class', y='counts', title='Earthquake Counts by Magnitude Class')
# If working in notebook DO output to plot:
plot
# Else if working in .py file DO provide a method to serve the app with `panel serve`:
if pn.state.served:
    # DO remember to add .servable to the panel components you want to serve with the app
    pn.panel(plot, sizing_mode="stretch_both").servable()
# DON'T provide a `if __name__ == "__main__":` method to serve the app with `python`
```

If working in a .py file DO always serve the plot with hotreload for manual testing while developing:

```bash
panel serve path/to/file.py --dev --show
```

DONT serve with `python path_to_this_file.py`.

## General Instructions

- Always import hvplot for your data backend:

```python
import hvplot.pandas  # adds .hvplot namespace to Pandas DataFrames and Series
import hvplot.polars  # adds .hvplot namespace to Polars DataFrames
import hvplot.xarray  # adds .hvplot namespace to xarray DataArrays and Datasets
...
```

- Prefer Bokeh > Matplotlib > Plotly plotting backend for interactivity in that order
- Use bar charts instead of pie charts because pie charts are not currently supported and bar charts communicate categorical comparisons more effectively.
- For detailed styling and publication-quality charts, use HoloViews directly with the matplotlib backend, as it provides more granular control over plot composition and styling than hvPlot's simplified API and better output for print/publication.
- Use NumeralTickFormatter with 'a' formatter for readable axis labels that automatically format large numbers (1.2M, 500K):

```python
from bokeh.models.formatters import NumeralTickFormatter

df.hvplot(
    ...,
    yformatter=NumeralTickFormatter(format='0.00a'),  # Format as 1.00M, 2.50M, etc.
)
```

| Input   | Format String | Output |
| ------- | ------------- | ------ |
| 1230974 | '0.0a'        | 1.2m   |
| 1460    | '0 a'         | 1 k    |
| -104000 | '0a'          | -104k  |

- Use `hover_tooltips` to customise tooltip content (replaces deprecated `hover_formatters`):

```python
df.hvplot.scatter(x='year', y='rate',
                  hover_tooltips=[('Year', '@year'), ('Rate', '@rate{0.2f}')])
```

- Use `backend_opts` for fine-grained Bokeh model styling not exposed by hvPlot's own API (hvPlot >= 0.12):

```python
df.hvplot.line(..., title='...', backend_opts={'title.text_font_size': '18pt',
                                  'xaxis.axis_label_text_color': '#555555'})
```

## Developing

When developing a hvplot please serve it for development using Panel:

```python
import hvplot.pandas  # noqa
import panel as pn

apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')

plot = apple.hvplot.line(y='close', grid=True,
                         title='Apple Close Price', ylabel='Close Price (USD)')

app = pn.Column("# Apple Stock Close Price", plot)

if pn.state.served:
    app.servable()
```

```bash
panel serve plot.py --dev --show
```

### Recommended Plot Types

| Method            | Best for                                                             |
| ----------------- | -------------------------------------------------------------------- |
| `line`            | Time series and continuous data                                      |
| `scatter`         | Relationships between variables; `c=` column for color encoding      |
| `points`          | Independent variables in two-dimensional space                       |
| `bar`             | Categorical comparisons; `stacked=True` for stacked bars             |
| `area`            | Filled/stacked series; `y2=` for min/max spread bands                |
| `hist`            | Distributions; `bin_range=`, `by=` for grouped histograms            |
| `kde` / `density` | Smooth distribution estimate; overlay multiple columns with `alpha=` |
| `box`             | Summary statistics by category; `invert=True` for horizontal         |
| `violin`          | Richer distribution view than box; `by=` grouping                    |

- For distribution plots (`hist`, `kde`, `box`, `violin`), specify `y` column(s) — no `x` needed.

## Subplots and Layouts

Use `subplots=True` to give each `y` column its own panel. Axes are linked by default:

```python
import hvplot.pandas  # noqa

stocks = hvplot.sampledata.stocks('pandas')

# Linked subplots, 2 per row; shared_axes=False for independent axis ranges
stocks.hvplot(x='date', y=['Apple', 'Amazon', 'Google'],
              subplots=True, shared_axes=False, width=300, height=200).cols(2)
```

Use `col=` / `row=` for a clean faceted grid with shared axis labels:

```python
penguins = hvplot.sampledata.penguins('pandas')

# 2D grid: one panel per species × island combination
penguins.hvplot.scatter(x='bill_length_mm', y='bill_depth_mm',
                        col='species', row='island', alpha=0.5)
```

## Large Data Strategies

Choose the right strategy based on dataset size:

| Dataset size      | Strategy                                                             |
| ----------------- | -------------------------------------------------------------------- |
| < ~100K points    | Plain WebGL (default — no extra params needed)                       |
| ~100K–1M points   | `downsample=True` — LTTB algorithm preserves visual signal           |
| 1M+ points        | `rasterize=True` — renders a pixel image server-side                 |
| Dynamic threshold | `resample_when=N` — activates rasterize/downsample only above N rows |

```python
import hvplot.pandas  # noqa

apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')   # 1 509 daily rows
clusters = hvplot.sampledata.synthetic_clusters('pandas')             # 1 000 000 rows, columns: x, y, cat

# LTTB downsampling — visually representative subset, updates on zoom
apple.hvplot.line(y='close', downsample=True)

# Advanced downsample methods (requires tsdownsample library)
# 'lttb' (default), 'minmax', 'minmax-lttb', 'm4'
apple.hvplot.line(y='close', downsample='m4')

# Rasterize — full-density pixel image, best for 1M+ points
clusters.hvplot.scatter(x='x', y='y', rasterize=True, cnorm='eq_hist')

# Dynamic: use rasterize only when data exceeds 10 000 rows
apple.hvplot.line(y='close', rasterize=True, resample_when=10_000)

# Auto-scale y-axis to visible data on zoom/pan (hvPlot >= 0.9)
apple.hvplot.line(y='close', autorange='y')
```

Avoid using naive `df.sample()` for large datasets because random sampling causes aliasing artifacts and misrepresents the underlying signal, especially for time series and spatial data.

## Geographic / Tile Maps

No geo dependencies are required for basic tile maps. hvPlot auto-projects lat/lon → Web Mercator when `tiles=True` (hvPlot >= 0.11):

```python
import hvplot.pandas  # noqa

earthquakes = hvplot.sampledata.earthquakes('pandas')

# Auto-projection from lat/lon to Web Mercator
earthquakes.hvplot.points('lon', 'lat', tiles=True, color='red', alpha=0.3)

# Named tile layer
earthquakes.hvplot.points('lon', 'lat', tiles='CartoDark', color='mag', cmap='fire')

# xyzservices provider (pip install xyzservices for hundreds of basemaps)
import xyzservices.providers as xyz
earthquakes.hvplot.points('lon', 'lat', tiles=xyz.CartoDB.Positron, color='mag', colorbar=True)

# Style the basemap layer independently
earthquakes.hvplot.points('lon', 'lat', tiles=True, tiles_opts={'alpha': 0.5})
```

For full projection support, install GeoViews. Use `geo=True` (assumes PlateCarree lat/lon input) or specify `crs=` / `projection=` explicitly:

```python
# geo=True: shorthand for crs=PlateCarree, projection=WebMercator
earthquakes.hvplot.points('lon', 'lat', geo=True, tiles=True, color='mag', cmap='fire')

# Custom output projection (requires GeoViews + Cartopy)
import cartopy.crs as ccrs
earthquakes.hvplot.points('lon', 'lat',
                           projection=ccrs.Orthographic(125, 0),
                           coastline=True, color='mag', cmap='fire')

# Available geographic features: 'borders', 'coastline', 'lakes',
# 'land', 'ocean', 'rivers', 'states'
earthquakes.hvplot.points('lon', 'lat', geo=True, features=['coastline', 'borders'])
```

For raster/xarray geo data, prefer `quadmesh` over `image` for non-rectangular projections.

```python
import hvplot.xarray  # noqa

air_ds = hvplot.sampledata.air_temperature('xarray')

# project=True pre-projects data before rasterizing — avoids per-zoom reprojection
air_ds.air.isel(time=0).hvplot.quadmesh(
    'lon', 'lat', crs=ccrs.PlateCarree(),
    projection=ccrs.GOOGLE_MERCATOR,
    tiles=True, project=True, rasterize=True,
)
```

## Timeseries-Specific Features

```python
import numpy as np
import hvplot.pandas  # noqa
from bokeh.models.formatters import DatetimeTickFormatter

apple = hvplot.sampledata.apple_stocks('pandas').set_index('date')
stocks = hvplot.sampledata.stocks('pandas').set_index('date')

# Custom datetime tick formatting on x-axis
apple.hvplot.line(y='close', xformatter=DatetimeTickFormatter(months='%b %Y'))

# Stacked multi-stock view: each series gets its own y sub-axis
stocks.hvplot.line(y=['Apple', 'Amazon', 'Google', 'Meta'], subcoordinate_y=True)

# Access datetime components directly for aggregation
# Works on Pandas datetime index: 'index.month', 'index.hour', 'index.year', etc.
apple.hvplot.heatmap(x='index.hour', y='index.month', C='close', cmap='reds', reduce_function=np.mean)
apple.hvplot.violin(by='index.month')
```

## Statistical Module Functions

These are **top-level functions** (not accessor methods) that mirror `pandas.plotting`:

```python
import hvplot
import hvplot.pandas  # noqa

# Select numeric columns + class column, drop NaN rows
numeric_cols = ['bill_length_mm', 'bill_depth_mm', 'flipper_length_mm', 'body_mass_g']
penguins = hvplot.sampledata.penguins('pandas')[numeric_cols + ['species']].dropna()
apple    = hvplot.sampledata.apple_stocks('pandas').set_index('date')

# Pairwise scatter matrix with linked brushing (box_select, lasso_select)
hvplot.scatter_matrix(penguins, c='species')

# Parallel coordinates — reveals multivariate structure and class differences
hvplot.parallel_coordinates(penguins, 'species')

# Andrews curves — Fourier-series view of class separation
hvplot.andrews_curves(penguins, 'species')

# Lag plot — detect autocorrelation and volatility in time series
hvplot.lag_plot(apple[['close']], lag=5, alpha=0.3)
```

## Workflows

### Lookup additional information

Search the web for additional information. For example, search the hvplot website for `streaming` related information via https://hvplot.holoviz.org/en/docs/latest/search.html?q=streaming

### Test the app with pytest

Add tests to the `tests` folder and run them with `pytest tests/path/to/test_file.py`.

- Separate data extraction and transformation from plotting code to make tests simpler and more focused.
- Fix any test errors and rerun the tests to ensure code quality.
- Run tests and fix errors before displaying or serving the plots.

### Test the app manually with panel serve

Always start and keep running a development server `panel serve path_to_file.py --dev --show` with hot reload while developing.

- The `--show` flag automatically opens a browser tab showing your app.
- The `--dev` flag enables hot reload so the panel server and app automatically reload when you change the code.
- The app will be served at http://localhost:5006/.
- Fix any errors that show up in the terminal. Consider adding new tests to prevent regressions.
- Don't stop or restart the server after changing code - the app will automatically reload.
- If you see 'Cannot start Bokeh server, port 5006 is already in use', serve the app on another port with `--port {port-number}` flag.
- Remind the user to test the plot on multiple screen sizes (desktop, tablet, mobile).
- Don't use the legacy `--autoreload` flag or run `python path_to_file.py` to serve the app.
- Use `pn.Column, pn.Tabs, pn.Accordion` to layout multiple plots.
- If you close the server to run other commands, remember to restart it.
