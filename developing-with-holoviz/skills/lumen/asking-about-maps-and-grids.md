# Asking about Maps and Grids

Geometry and gridded data take the same `lumen.read(...).ask(...)` path, with extra prompt rules, a SQL review and geo-aware outputs. Install `lumen[geo]` (geopandas, geoviews, datashader) and `lumen[xarray]` (xarray, xarray-sql).

## Contents

- [Loading Geo and Grid Data](#loading-geo-and-grid-data)
- [Public Remote Data](#public-remote-data)
- [Asking Good Spatial and Gridded Questions](#asking-good-spatial-and-gridded-questions)
- [What Lumen Adds](#what-lumen-adds)
- [Geo Outputs](#geo-outputs)
- [How Maps Draw](#how-maps-draw)

## Loading Geo and Grid Data

```python
import geopandas as gpd
import hvsampledata
import lumen
import xarray as xr

states = lumen.read({"states": hvsampledata.us_states("geopandas")})   # polygons + CRS
quakes = lumen.read({"quakes": hvsampledata.earthquakes("pandas")})    # lat/lon columns
places = lumen.read({"places": gpd.read_file("places.geojson"), "regions": gpd.read_file("regions.geojson")})
air = lumen.read({"air": hvsampledata.air_temperature("xarray")})      # a grid
era5 = lumen.read(xr.open_dataset("era5_t2m.nc"))
```

- GeoDataFrames and GeoParquet keep their geometry and CRS; a table with `lat`/`lon` columns maps as points.
- An xarray Dataset becomes a SQL table over its dimensions and variables (through xarray-sql), queried lazily.
- `hvsampledata.air_temperature` covers only 24 to 28 February 2014; questions about other months return nothing. Check a grid's time range before writing demo questions.

## Public Remote Data

One call, no credentials or cloud SDKs, for public `https://`, `s3://` and `gs://` data:

```python
places = lumen.read(
    "s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/*.parquet",
    bbox=(13.38, 52.51, 13.42, 52.53),            # west, south, east, north
)
era5 = lumen.read(
    "gs://gcp-public-data-arco-era5/ar/1959-2022-full_37-1h-0p25deg-chunk-1.zarr-v2",
    variables=["2m_temperature"],
    sel={"time": "2020-07-01T12:00", "latitude": slice(60, 40), "longitude": slice(0, 20)},
)
```

- `bbox=` cuts (Geo)Parquet to an area and reads it into memory once; Overture's `bbox` column lets it skip files, but the release's metadata scan still takes about a minute.
- `variables=` and `sel=` cut a Zarr store before any SQL runs. Always pass them for ARCO-ERA5-sized stores: an uncut store is far too large to query.
- Private buckets are not supported yet.

## Asking Good Spatial and Gridded Questions

Say the unit and the area; the model follows them:

```python
places.ask("How many places are within 750 km of Berlin?")
states.ask("Map median household income by state")
era5.ask("Which month had the highest area-weighted global mean temperature, in degrees Celsius?")
air.ask("Map the change in air temperature between the first and the last time step")
```

## What Lumen Adds

These are automatic; don't re-implement them in prompts or post-processing.

- **Prompt rules**, only when a table has geometry or is a grid: distances and areas in metres on a sphere or an equal-area CRS (not degrees), longitude before latitude, a spatial predicate in every join; dimension filters on grids, latitude (cosine) weights for means, Kelvin to Celsius.
- **A SQL review before the query runs**: buffers or distances in degrees, areas in degrees, geometry joins without a spatial predicate, Kelvin compared with Celsius. The model is told once; an unchanged resubmission runs as is.
- **Units in the schema**: each grid column's description carries its CF `units`, `standard_name` and non-standard calendar, e.g. `air -- 4xDaily Air temperature [degK]`.
- **Gridded tools**: SQL for a time slice, an area-weighted mean, a climatology (monthly, quarterly, daily, hourly), anomalies from it, and unit conversion (K to degC, Pa to hPa, kg m-2 s-1 to mm day-1). They use the grid's own dimension names (`latitude` on ERA5, `lat` elsewhere) and say so for any non-standard calendar (noleap, 360-day, as in CMIP output), whose dates SQL sees as plain numbers.
- **hvPlotAgent** joins the default agents for geometry and grid sources, since it draws basemaps and rasterizes large grids.

## Geo Outputs

| Field / call | Gives |
|---|---|
| `answer.gdf` | The result as a GeoDataFrame with its CRS (recovered after `ST_Transform`), or None without geometry; warns once when lon/lat-looking geometry has no CRS |
| `answer.ds` | The result as an xarray Dataset for gridded answers, or None |
| `answer.to_file(path)` | By extension: `.parquet` (GeoParquet with geometry), `.geojson`, `.gpkg`, `.csv`; `.zarr` or `.nc` for grids. Pass `overwrite=True` to replace a file; warns when data was cut at `max_rows` |
| `answer.map()` | The geometry on an interactive map: lonboard when installed, else hvPlot on a basemap |

```python
income = states.ask("Map median household income by state")
income.gdf.head()
income.to_file("income.parquet", overwrite=True)
income.map()
air.ask("Mean air temperature per grid point").ds
```

## How Maps Draw

- Longitude/latitude data sits on OpenStreetMap tiles when geoviews is installed; projected geometry draws without tiles.
- Grids draw as a quadmesh over coastlines, not tiles; large grids and point clouds are rasterized when datashader is installed.
- Maps are hvPlot charts, so they only show in the interactive card. A saved notebook keeps a static Vega-Lite map only for tables with a geometry column; lon/lat-column maps and grids have no static fallback yet.
- Click or box-select on a map fills `answer.selection` for `answer.ask_about(...)` (see Reusing Answers).
