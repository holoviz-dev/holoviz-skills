# The Story Spec

The declarative JSON that `scripts/build_notebook.py` renders into a notebook.
You author the spec; the builder owns the vetted hvPlot/HoloViews code for each
view. This keeps specs small and keeps plotting idioms correct by construction.

## Contents

- [Spec object](#spec-object)
- [Beat object](#beat-object)
- [View archetype catalog](#view-archetype-catalog)
- [Adding a new archetype](#adding-a-new-archetype)

## Spec object

```json
{
  "title":  "Exploring …",            // notebook H1
  "intro":  "markdown — the dataset + the question being asked",
  "setup":  "df = pd.read_parquet('…')",   // ONE raw code block: load `df`
  "beats":  [ /* ordered list of Beat objects */ ]
}
```

- `setup` is the one place raw code belongs — loading is dataset-specific. It
  must define a DataFrame named `df`. For temporal stories, give `df` a
  `DatetimeIndex` (e.g. `index_col='Date', parse_dates=['Date']`).
- The builder prepends a fixed imports cell (`numpy`, `pandas`, `hvplot.pandas`,
  `holoviews as hv`, `NumeralTickFormatter`). Do not re-import in `setup`.

## Beat object

```json
{ "kind": "rhythm", "params": { "measure": "value", "by": "hour" }, "narrate": "## The daily rhythm\n\n…" }
```

- `kind` — one of the archetypes below.
- `params` — keys depend on `kind` (see catalog). Most take a `title`.
- `narrate` — markdown for the section above the view. This is the story; write
  it from the executed output, not before.

Each beat becomes a markdown cell (the `narrate`) followed by a code cell (the
rendered view). The narration carries the findings the profiler computed and the
reader's eye confirms.

## View archetype catalog

Ordered by the ladder (start small → build up). All assume `df` from `setup`.

| `kind` | params | Renders | Ladder rung |
|---|---|---|---|
| `profile` | — | `df.info()` + `df.describe()` | 0 acquaint |
| `resample` | `cols`, `freq`="W", `agg`="sum", `ylabel`, `title` | `df[cols].resample(freq).agg().hvplot.line(...)` | 1 univariate over time |
| `rhythm` | `measure`, `by`="hour"\|"weekday", `title` | mean of `measure` over the ordered axis, line + points | 2 condition on time |
| `split` | `measure`, `title` | `measure` by hour, **overlaid weekday vs weekend** | 2 condition |
| `heatmap` | `measure`, `title` | `hv.HeatMap` of mean `measure` over hour × weekday | 3 two dims on one panel |
| `facet` | `measure`, `by`, `title` | `df.hvplot.box(y=measure, by=…)` | 3 facet across a category |
| `scatter` | `x`, `y`, `by`?, `title` | `df.hvplot.scatter(x, y, by=…)` | 3 measure vs measure |
| `pca_dayshape` | `measure`, `title` | SVD of per-day hourly shape; PC1/PC2 scatter colored by daytype | 4 reduce/cluster |
| `code` | `code` | the raw string verbatim | escape hatch |

Notes:

- `rhythm`, `split`, `heatmap`, `pca_dayshape` assume a `DatetimeIndex` on `df`.
- `pca_dayshape` normalizes each day to its total so it compares *shape*, not
  volume — that is what makes regimes (commute vs leisure) separate cleanly.
- Counts axes use `NumeralTickFormatter(format="0,0")`; views pass
  `responsive=True, height=…` as hvPlot arguments (never via `.opts()`).
- Use `code` sparingly — every raw block is a chance to get an idiom wrong and a
  thing the builder can't keep correct for you.

## Adding a new archetype

Add a renderer to `scripts/build_notebook.py`: a function
`r_<kind>(params) -> str` returning Python source, registered in the `RENDERERS`
dict. Keep the emitted code aligned with the [hvplot](../hvplot/SKILL.md) and
[holoviews](../holoviews/SKILL.md) skills (hover tooltips, formatters, responsive
sizing) so generated notebooks stay idiomatic. Then document it in the table
above and, if it unlocks a new user need, add a row to the parent routing skill's
Loading Table.
