---
name: exploring
description: >-
  Profile any multidimensional dataset and generate a grounded, narrative
  exploratory-analysis notebook. Auto-detects what is worth exploring (measures
  vs dimensions, time, identifiers), then tells the dataset's story with
  hvPlot/HoloViews — deferring to Panel only when a control must drive every
  view at once. Use when the user wants to explore, profile, or understand an
  unfamiliar dataset, do EDA, asks "what's in this data", or wants a data story.
  Do not use for a single known plot (use hvplot) or a prebuilt dashboard (use panel).
compatibility: Requires hvplot, holoviews, pandas (numpy). Notebook output runs in Jupyter/VS Code.
metadata:
  version: "0.1.0"
  author: holoviz
---

# Exploring a Dataset

Approach this like an analyst handed an unfamiliar dataset with one hour to find
where its structure lives. Your deliverable is not a chart — it is a **narrative
notebook that tells the story of the data's structure**: what is in it, how it
behaves across its dimensions, and where the surprises are. The reader should be
able to run it top to bottom, follow the reasoning, and trust every claim.

Two commitments make this skill work, and both are easy to skip:

1. **Profile before you plot.** The most common failure is exploring the
   dimension you happened to think of (time) and missing the ones the data is
   begging you to filter on (a transaction `value`, a `gas` cost, a price). Let
   the profiler tell you what is explorable *first*.
2. **Narrate what you actually saw.** A story is only worth writing if it is
   grounded. Run each cell, read the output, and write the prose to match —
   never stamp out "here we see a clear trend" next to noise.

## Contents

- [References](#references)
- [Available scripts](#available-scripts)
- [The method](#the-method)
- [Step 1 — Profile: auto-determine what's explorable](#step-1--profile-auto-determine-whats-explorable)
- [Step 2 — Start small, build up the ladder](#step-2--start-small-build-up-the-ladder)
- [Step 3 — Author the story spec](#step-3--author-the-story-spec)
- [Step 4 — Build, execute, and ground](#step-4--build-execute-and-ground)
- [Step 5 — Defer to Panel (the four triggers)](#step-5--defer-to-panel-the-four-triggers)
- [What agents get wrong](#what-agents-get-wrong)

## References

- [story-spec.md](story-spec.md) — the JSON story-spec schema and the full
  view-archetype catalog (every `kind`, its params, and the code it renders).
- `examples/bike_story.spec.json` — a complete worked spec (the Fremont Bridge
  bike counts), and `examples/bike_story.ipynb` — the notebook it renders to.

This skill orchestrates the library skills rather than restating them. For
plotting mechanics read the siblings as needed: [hvplot](../hvplot/SKILL.md)
(`.hvplot` accessor, `by`/`col`/`row`/`groupby`), [holoviews](../holoviews/SKILL.md)
(`HeatMap`, `.opts()`, `link_selections`), [panel](../panel/SKILL.md) and
[plotting-in-panel](../panel/plotting-in-panel.md) (the escalation), and
[param](../param/SKILL.md).

## Available scripts

Run these from the skill directory; only their output enters context.

- **`scripts/exploration_profiler.py`** — classify every column's role
  (temporal / measure / categorical / id / geo) and propose an exploration plan
  + story outline. This is the engine that determines *what is explorable*.
  ```bash
  python scripts/exploration_profiler.py PATH.csv          # human-readable plan + outline
  python scripts/exploration_profiler.py PATH.parquet --json   # machine-readable, for authoring
  python scripts/exploration_profiler.py --demo            # bike / penguins / eth outlines
  ```
- **`scripts/build_notebook.py`** — render a declarative story-spec JSON into a
  valid notebook. The vetted hvPlot/HoloViews code for each view lives in the
  builder, so you never hand-write plotting code (and can't get the
  responsive/width idioms wrong).
  ```bash
  python scripts/build_notebook.py story.spec.json -o story.ipynb
  ```

Both declare no exotic dependencies; in a project without the env, run them with
`uv run scripts/exploration_profiler.py …`.

## The method

```
profile  →  outline (start small, build up)  →  story-spec  →  build  →  EXECUTE & ground  →  defer to Panel
```

Each arrow is cheap; take more of them rather than fewer. Exploration is a
conversation with the data — every view should answer the question the last one
raised.

## Step 1 — Profile: auto-determine what's explorable

Run `exploration_profiler.py` on the data before writing anything. It reports,
per column, a **role** and the interaction it implies:

| Role | Meaning | Interaction it earns |
|---|---|---|
| `temporal` | datetime | date-range filter; resample; hour/weekday rhythm |
| `measure` | continuous numeric | distribution **+ range filter**; aggregate (sum/mean) |
| `categorical` | low-cardinality | multiselect / facet / bar |
| `id` | high-cardinality | top-N / search / join key (never a facet axis) |
| `geo` | lat/lon | map, coordinated with distributions |

The plan also lists **measures**, **dimensions**, **temporal**, **ids**, and a
proposed **story outline**. Treat the outline as the table of contents you are
about to write — adapt it, don't follow it blindly.

> The point of profiling: it is what surfaces the `value`/`gas`/`price` columns a
> human (or a hand-built app) forgets to make filterable. If a measure exists,
> the reader should be able to filter and aggregate on it.

## Step 2 — Start small, build up the ladder

This is how practitioners actually explore, and it is the spine of the story.
Climb only the rungs the profile supports:

1. **One variable** — each measure's distribution; counts per category; the
   measure over time. Catch skew, gaps, outliers, the grain.
2. **Condition on one dimension** — measure vs time (trend, then rhythm);
   measure by category (bars/box). Structure first appears here. *Does one
   average hide two populations?*
3. **Two dimensions on one panel** — the 2-D pivot heatmap
   (`ordered × categorical → measure`), small-multiple facets, or a scatter of
   two measures. This is the move that generalizes across datasets.
4. **Many dimensions** — reduce and let the data cluster itself (PCA/SVD of a
   per-unit shape), or seriate a co-occurrence/flow matrix for high-card ids.
5. **Make it live** — only now, Panel (Step 5).

Order encodes dependency: you cannot read the weekday split before the daily
rhythm. Keep that order in the notebook.

## Step 3 — Author the story spec

Write a compact JSON spec — **not** notebook JSON, and **not** raw code in
strings. Each beat names a `kind` (a view archetype), its `params` (which
columns), and the `narrate` markdown. See [story-spec.md](story-spec.md) for the
schema and every available `kind`. Shape:

```json
{
  "title": "Exploring …",
  "intro": "the dataset and the question",
  "setup": "df = pd.read_parquet('…')   # one raw block: load the data",
  "beats": [
    {"kind": "profile",  "narrate": "## What are we holding?"},
    {"kind": "rhythm",   "params": {"measure": "value", "by": "hour"}, "narrate": "## The daily rhythm"},
    {"kind": "heatmap",  "params": {"measure": "value"},               "narrate": "## The weekly fingerprint"},
    {"kind": "scatter",  "params": {"x": "gas", "y": "value"},          "narrate": "## Cost vs amount"},
    {"kind": "code",     "params": {"code": "# bespoke step"},          "narrate": "## …"}
  ]
}
```

Keep raw code to the single `setup` block (loading is dataset-specific) and the
`code` escape hatch. Everything else stays declarative so the builder owns the
correct plotting idioms.

## Step 4 — Build, execute, and ground

```bash
python scripts/build_notebook.py story.spec.json -o story.ipynb
```

Then **execute it and read the outputs** — `jupyter nbconvert --to notebook
--execute story.ipynb`, or open it and run all. This is non-negotiable: revise
each `narrate` to state what the cell actually shows (the real peak hour, the
real ratio, whether the cluster separated), and if a view raised a new question,
add the beat that answers it and rebuild. A spec that was never executed is a
template, not a story.

## Step 5 — Defer to Panel (the four triggers)

The notebook is the default surface — hvPlot/HoloViews render live inline
(hover, zoom, `groupby` widgets) with no server. Escalate to a Panel app **only**
when you hit one of these, and say why:

1. **One control must drive every panel at once** (a date range / threshold that
   re-slices all views).
2. **Highlight-over-context** driven by derived state (gray full distribution +
   colored selected slice).
3. **Selection → DynamicMap / Tabulator** cross-filtering (`link_selections`
   does not work with DynamicMap).
4. **A real app shell** is the deliverable (templating, sessions, deployment).

When you do, hand off to [panel](../panel/SKILL.md) +
[plotting-in-panel](../panel/plotting-in-panel.md) for the `pn.bind` / DynamicMap
trigger pattern. Don't reinvent it here.

## What agents get wrong

- **Plotting before profiling** → you explore time and miss that `value`, `gas`,
  or `price` are filterable measures. Run the profiler first.
- **Hollow narration** → prose that doesn't match the output. Execute, then write.
- **Treating an `id` or a monotonic int as a measure** → `from_address`,
  `block_number`, a row id. The profiler demotes these; don't average them.
- **hvPlot `responsive`/`width` conflict** → pass `responsive=True, height=N` as
  hvPlot *arguments*, never via `.opts()` (the builder already does this right).
- **One element per DynamicMap** → if you escalate to Panel, each DynamicMap
  callback returns one element type; combine with `*`. See plotting-in-panel.
- **Faceting on a high-card column** → never `by=`/`col=` an id; aggregate or
  top-N it instead.
