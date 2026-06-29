---
name: exploring
description: >-
  Explore any multidimensional dataset and hand back a narrative that tells its
  story and stays interactive — as a notebook the reader re-runs, or a servable
  Panel layout you can render. Profile first to find what is worth exploring
  (measures, dimensions, time, ids), then build the story one question at a time,
  handing the reader a knob wherever a view has a free dimension: hvPlot
  `groupby=` for the simple case, DynamicMap + pn.bind for deeper one-control
  views. Push heavy aggregation to the engine (DuckDB) and keep the interactive
  layer cheap. Use when the user wants to explore, profile, or understand an
  unfamiliar dataset, do EDA, asks "what's in this data", or wants a data story.
  Do not use for a single known plot (use hvplot) or a prebuilt production
  dashboard (use panel).
compatibility: >-
  Requires hvplot, holoviews, pandas; jupytext to emit a notebook, or panel
  (panel-material-ui) for a servable layout; optionally duckdb for engine-side
  aggregation.
metadata:
  version: "0.4.0"
  author: holoviz
---

# Exploring a Dataset

Approach this as the analyst a team brings in when they have a dataset and no
idea what is in it — the one who hands back not a contact sheet of every column
but **a story with a thesis, and an instrument the reader can keep playing**.
You are not paid to run `describe()`. You are paid for the judgment a column
scan can't supply: which measure is the story, which contrast answers the
question, and which dimension the reader will want to turn in their own hands.

There are two ways this goes generic, and both are easy to fall into:

- **The EDA dump** — `df.info()`, `df.describe()`, a histogram of every numeric
  column, a correlation heatmap, `.hvplot()` on autopilot. It looks the same for
  every dataset and answers no question. If a cell would appear in *any*
  exploration, it is filler.
- **Static when it should move** — a single averaged curve that hides two
  populations; twelve small-multiple facets where one dropdown would let the
  reader drive it. In HoloViz, interactivity is nearly free — leaving it on the
  table is a choice, and usually the wrong one.

Two commitments keep you out of both:

1. **Profile before you plot.** The common failure is exploring the dimension
   you happened to think of (time) and missing the ones the data is begging you
   to filter on (a transaction `value`, a `gas` cost, a price).
2. **Narrate only what you ran.** A story is worth writing only if it is
   grounded — claim a finding once the cell that produces it has actually
   executed, never before. This bans **priors dressed as findings**: it is not
   enough that a pattern is "well known" for this dataset, or that you are
   confident the evening peak is there. If the cell has not run in *this*
   session against *this* file, you have not found it, and you must not write it
   as though you did. A confident prior is still a guess.

## Contents

- [Profile first](#profile-first)
- [Hand the reader the knob](#hand-the-reader-the-knob)
- [The method: start small, build up](#the-method-start-small-build-up)
- [Push the work to the engine](#push-the-work-to-the-engine)
- [Emit it so you can render it](#emit-it-so-you-can-render-it)
- [Ground honestly](#ground-honestly)
- [Process: sketch, build, critique](#process-sketch-build-critique)
- [Example](#example)

This skill **orchestrates** the library skills rather than restating them. Read
the siblings for mechanics: [hvplot](../hvplot/SKILL.md) (`.hvplot`,
`groupby`/`by`/`col`/`row`, `rasterize`), [holoviews](../holoviews/SKILL.md)
(`HeatMap`, `HoloMap`, `DynamicMap`, `.opts()`), [param](../param/SKILL.md)
(`Viewer`, `@param.depends`) and [panel](../panel/SKILL.md) +
[plotting-in-panel](../panel/plotting-in-panel.md) (the `pn.bind` / DynamicMap
trigger pattern). Pull mechanics from there; spend your own judgment here.

## Profile first

Before plotting, profile the columns with a few lines of pandas. This is the
step that gets skipped, and **cardinality is the signal that tells you each
column's role**:

```python
df.shape, df.dtypes          # what and how much
df.isna().mean()             # missingness
df.nunique()                 # cardinality — the key signal
df.select_dtypes("number").describe().T   # ranges (for measures)
```

Classify every column and read off what it earns:

| Role | How to spot it | Earns |
|---|---|---|
| `temporal` | datetime dtype, incl. the index | date-range filter; resample; hour/weekday rhythm |
| `measure` | numeric, many distinct values | distribution **+ range filter**; aggregate (sum/mean) |
| `categorical` | few distinct values (≤ ~20), incl. small-int codes & bools | the **knob**: multiselect / facet / bar |
| `id` | very high cardinality (≈ one per row; hashes, addresses, keys) | top-N / search / join key — **never a facet axis** |
| `geo` | `lat`/`lon`/`latitude`/`longitude` names | map, coordinated with distributions |

The rule that matters: **enumerate every measure and give each one a
distribution and a range filter.** The common miss is to explore only the
dimension you thought of first — say `hour` — because nothing forces you to look
at the rest, leaving a `value` or `price` measure unexamined. A monotonic
`block_number` is an id, not something to average; that judgment is yours, not
the dtype's.

## Hand the reader the knob

Don't ask "static, or do I escalate to Panel?" — ask *what does the reader want
to vary, and have I given them the control?* Any view with a free dimension — a
category to pick, a threshold to slide, a window to sweep — earns a knob.
Freezing one choice, or fanning the choice out into ten static facets, is the
thing to avoid.

Three tiers, **all of them living inside the notebook**. Reach for the cheapest
that answers the question:

1. **A free inline widget** — hvPlot's `groupby=` (which builds a `HoloMap` /
   `DynamicMap` under the hood). One dropdown or slider, no server, no class.
   This is the default whenever a single dimension is worth flipping through:

   ```python
   df.hvplot.hist("arrdelay", groupby="carrier", responsive=True, height=320)
   # a carrier dropdown, for free — no Panel, no callback
   ```

2. **One control drives several linked panels** — a small `pn.bind` or a
   ~20-line `pn.viewable.Viewer`. This is the grammar that makes an exploration
   feel *alive*, and it is worth knowing by name:

   - **highlight-over-context** — the full distribution in gray, the selected
     slice drawn in color on top, so focus never loses the whole;
   - **a cumulative companion** beneath each distribution — "what's the shape"
     and "how much in total" answered together;
   - **a baseline panel beside a faceted one** — all-data on the left, the one
     selected slice on the right;
   - **one control set re-slices every panel at once**, and reference
     annotations carry the *meaning* of the slice rather than decorate it.

   Build it with one element type per `DynamicMap` callback, combined with `*`
   and `+`. Don't reinvent the trigger plumbing — take it from
   [param](../param/SKILL.md) + [plotting-in-panel](../panel/plotting-in-panel.md).

3. **A real app shell** — templating, sessions, multi-page, deployment — is a
   *different deliverable*, not part of exploration. Hand off to
   [panel](../panel/SKILL.md).

So you defer the **app shell**, never the interactivity. A `groupby` widget or a
small Viewer belongs in the exploration itself, embedded in a notebook cell.

### Build controls from the data, not from constants

A control's *options, bounds, and colors live in the data*. Write the dashboard
against column **names and roles**, and let it discover the rest when it runs —
then the same code works on a file you have never seen, and a hand-typed list of
categories can never drift out of sync with what is actually there. This is just
profile-first carried one step further: **the role you assigned each column picks
the widget, and the data fills in the rest.**

- a **categorical** knob → options are `df[col].unique()` (sorted), not a literal list
- a **measure** → slider bounds are its `min`/`max`
- a **temporal** column → a date-range from its span
- **colors** → zip a palette onto the discovered categories, never one literal per category

The hard-coded `regions`/`DAYS`/color-per-row dictionaries that show up in
hand-built dashboards are the anti-pattern; almost all of it is recoverable from
a cheap introspection (in an engine, a `SELECT DISTINCT`/`min`/`max`, so you
never scan the whole table just to populate a dropdown).

Two limits keep it honest. **Cap cardinality** — fall back to top-N on anything
id-like (the "never facet an id" rule again). And **don't pretend to derive what
isn't in the data**: a timezone offset, a domain threshold, the *meaning* of a
category are irreducible semantics — keep those as one named constant
(`WORKDAY = (8, 18)`), not magic literals buried in callbacks. Derive the
values; name the semantics.

## The method: start small, build up

This is how practitioners actually explore, and it is the spine of the story.
Climb only the rungs the profile supports; each rung is one notebook section,
posing a question, picking the *reshape* that puts the answer on an axis,
showing one view, and reading off what it shows — which motivates the next.

| Rung | Move | View (skill) |
|---|---|---|
| 1 · one variable | each measure's distribution; category counts; measure over time | `df.hvplot.hist`/`kde`/`line` (hvplot) |
| 2 · condition on one dim | measure vs time (trend → rhythm); measure by category | `groupby(...).mean().hvplot.line`; `hvplot.box`/`violin` (hvplot) |
| 3 · two dims on one panel | `ordered × categorical → measure`; small multiples; measure vs measure | `hv.HeatMap` (holoviews); `by`/`col`/`row`, `hvplot.scatter[_matrix]` (hvplot) |
| 4 · many dims | reduce & let it cluster; seriate a high-card matrix; big N | PCA/SVD (numpy) + `hvplot.scatter`; `rasterize=True` (hvplot) |

Order encodes dependency: you cannot read the weekday split before the daily
rhythm. **Interactivity is not the top rung — it is orthogonal to the climb.**
At any rung where a dimension is free, hand the reader the knob (above) instead
of freezing it or fanning out static facets. A rung-2 "measure by category"
becomes a rung-2 *with a category dropdown* at no extra cost.

## Push the work to the engine

The interactive layer must stay cheap, or every widget event stutters. The
pattern that scales: **aggregate once in the engine, then let the UI do nothing
but index the result.** For anything large or columnar, push the group-by to
DuckDB — it reads a Parquet glob directly — and pull back only the small
aggregate:

```python
import duckdb
duckdb.sql("""
    CREATE OR REPLACE VIEW txns AS
    SELECT *, hour(block_timestamp) AS hour, dayofweek(block_timestamp) AS weekday
    FROM 'transactions/*.parquet'
""")
agg = duckdb.sql("SELECT hour, weekday, count(*) AS n FROM txns GROUP BY ALL").df()
```

Now a 168-row aggregate (or a pivot of it) drives every panel; slicing is array
math, not a re-scan. **Never re-query or re-scan the full dataset inside a
`DynamicMap` callback** — pre-aggregate to a pivot once and index it. This is the
difference between a Viewer that responds instantly on 7 GB and one that hangs on
every click. (`hvplot.duckdb` plots a relation directly when you don't need the
intermediate frame.)

## Emit it so you can render it

Two shapes for the deliverable. The difference that matters is **what renders
without a live kernel** — which is also how *you* ground your own work:

- **A notebook.** Author a **percent-script** (`.py`, code is code and prose is
  markdown) and convert — never hand-write `.ipynb` JSON, the escaping is
  fragile and wasteful:

  ```bash
  jupytext --to notebook exploration.py        # -> exploration.ipynb
  ```

  This is the analyst's native medium — they edit and re-run it cell by cell.
  But an exported or handed-off notebook may have **no running kernel**, so any
  interactivity in it must be self-contained (a `HoloMap`, see below).

- **A servable Panel layout.** A `pmui.Column` interleaving `pmui.Typography`
  prose with the plots, ending in `.servable()`. This is the form you can
  actually **serve and screenshot**, so it is how you verify the views render
  and the findings are real before handing anything over — and it is the better
  deliverable when the user wants something to *view* rather than edit. Keep it a
  *narrated layout*, not an app shell — no templating, sessions, or routing
  (that is still the [panel](../panel/SKILL.md) hand-off from tier 3).

Cell format for the percent-script — each beat is a markdown cell (the question
+ what you found) followed by one code cell (one view):

```python
# %% [markdown]
# ## 2. The daily rhythm
# Averaging over hour-of-day exposes the two commute peaks…

# %%
df.groupby(df.index.hour)["Total"].mean().hvplot.line(
    responsive=True, height=300, xlabel="hour of day")
```

Use the vetted idioms from the sibling skills — pass `responsive=True, height=N`
as hvPlot *arguments* (never via `.opts()`), add `hover_tooltips` and
`NumeralTickFormatter`, one element type per `DynamicMap` callback.

### `groupby=` for the simple case; DynamicMap / pn.bind for real interactivity

The decision is binary, not a three-way pick:

- **Flipping a single view through one dimension** → hvPlot's `groupby=`. It
  builds a `HoloMap` for you (every frame computed and embedded up front), so it
  is self-contained and renders even in an exported notebook with no kernel. You
  rarely construct a `HoloMap` by hand — `groupby=` *is* the idiom. Good for a
  handful of discrete options; it blows up if the cross-product is large or each
  frame is heavy.
- **Anything deeper** — one control reshaping several linked panels (the HourApp
  pattern), real widgets, custom layout, big or expensive per-frame data → a
  **DynamicMap** (lazy, computes each frame on demand) wired up with **pn.bind**.
  This needs a live kernel — which is fine, it is exactly the servable layout you
  can serve and screenshot. One element type per callback; compose with `*`/`+`.

So: reach for `groupby=` first; the moment the interaction is more than flipping
one plot through one dimension, go straight to DynamicMap + pn.bind. Mechanics
live in [holoviews](../holoviews/SKILL.md) and
[plotting-in-panel](../panel/plotting-in-panel.md).

## Ground honestly

You often **cannot render in your environment** — the data or the plotting stack
may be absent and uninstallable (no network, no Parquet engine). Separate what
you can check from what only running grounds, and be honest about which you did:

- **Static (just pandas):** confirm every column you reference exists (catch
  `arr_delay` vs `arrdelay`); run each reshape/groupby on a small slice or a
  schema-matched frame; keep to vetted idioms. This grounds the *code*, never
  the *findings* — a synthetic frame proves the cell runs, not what your data
  says.
- **Grounded (needs data + stack):** execute the notebook (`jupyter nbconvert
  --to notebook --execute …`, or run all), read the outputs, and rewrite the
  narration to match the real peak hour, the real ratio.

**Never present a finding as grounded if its cell has not run** — and "well
known for this dataset" does **not** count as running. You may recognize the
flights data and *expect* delay to peak in the evening; you may have seen the
correlation a hundred times. Write none of it as a result. Recognizing a
dataset is not measuring it, and a prior — however strong — is a guess until the
cell confirms it. The trap is the confident hedge: "delay peaks in the evening
*(run-locally: read the actual peak hour)*" reads as a finding with a footnote,
but the finding was never made. Hedging the number does not license asserting
the pattern.

So when a cell has **not** run, the prose for that cell must be written in the
**hypothesis voice**, not the findings voice. State the question and the test,
not the answer:

- Findings voice (only after the cell ran): "Delay climbs through the day and
  peaks around 7pm — the signature of aircraft falling behind."
- Hypothesis voice (cell not yet run): "This groups mean `arrdelay` by departure
  hour. Air delay *typically* accumulates through the day as aircraft fall
  behind; **check whether this extract follows that, and where its peak falls.**"

The difference is not a disclaimer bolted on — it is the grammar of the sentence.
A hypothesis names what to look for; a finding claims what was seen. If you have
not run the cell, every claim about magnitude, direction, ranking, or shape
belongs in the first form. Mark such cells plainly (e.g. a leading
"**Hypothesis —**" or a top-of-notebook banner that the narrative is unrun) so a
reader never mistakes the plan for the result. A notebook whose prose *sounds*
grounded but was never executed is the failure to avoid.

| Format | Engine present | Minimal env (no engine, no network) |
|---|---|---|
| CSV / TSV / Excel | full data | full data — `pd.read_csv` / `openpyxl` (built in) |
| SQLite | full data | full data — stdlib `sqlite3` + `pd.read_sql` |
| Parquet | full data (`pyarrow`/`duckdb`) | **schema only** — names/types live in the footer (`strings file.parquet`); author from that |
| DuckDB | full data (`duckdb`) | **no access** — ask for a CSV / SQLite / Parquet export |

Never hand-write a data reader (a Parquet decoder) to dodge a missing engine —
it is a library-sized rabbit hole. Read the schema from the footer and author
from it. *(Many setups — Claude Code, a local run, anything with `pyarrow`/
`duckdb` — read Parquet directly and ground fully; the schema-only fallback is
only for restricted sandboxes.)*

## Process: sketch, build, critique

Work in two passes, like a designer who plans before cutting.

**First, sketch the story before you build it.** Name the thesis in one line
(what is this dataset *about*?), the primary measure, the two or three contrasts
that earn their place, and — for each planned view — whether a dimension is free
enough to hand over as a knob. Then hold the sketch against the EDA-dump default:
if a step is one you would produce for *any* dataset, cut it or sharpen it into a
real question. Do this thinking quietly; show the reader the polished walk, not
the scaffolding.

**Then build the ladder, critiquing as you go:**

- Did **every measure** get a distribution and a range filter, or did you only
  explore the dimension you thought of first?
- Is every interactive control **earning its place**, or is it a scatter of
  dropdowns? Spend your interactivity where the reader most wants to vary the
  view — one control re-slicing linked panels beats ten lonely widgets.
- Did you **narrate only what ran**? Execute, read the outputs, fix the prose.

Match the build to the dataset: a rich multi-dimensional table earns a Viewer; a
three-column CSV does not. Elegance is doing the warranted thing well, not piling
on widgets.

## Example

`examples/seattle_bikes.py` — a percent-script modelling the exploratory loop on
the Fremont Bridge bike counts: it **profiles first** (column roles set the
question list), then proceeds one question at a time, each section posing a
hypothesis, running one view, reading the answer off it, and letting that answer
pick the next question — raw signal fails → weekly trend/season → daily rhythm →
"is one average hiding two populations?" weekday vs weekend → the direction split
the profile flagged → an inline `groupby` month slider where interactivity earns
its place → a hour×weekday heatmap summary. Findings are narrated as findings
because the cells ran. It loads the public Fremont Bridge hourly CSV
(data.seattle.gov, dataset 65db-xm6k); render with
`jupytext --to notebook examples/seattle_bikes.py`.
