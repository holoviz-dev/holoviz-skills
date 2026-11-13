---
name: lumen
description: Ask questions of data in plain language from Python or a notebook with Lumen AI: load data with lumen.read, call .ask() for an Answer holding the text, the SQL and a chart, follow up, check data, test, and map spatial or gridded data. Use when the user wants an LLM to query, chart or explain a DataFrame, file, database or xarray Dataset. Do not use for hand-written plots (use hvPlot) or for building a Panel app (use Panel).
metadata:
  version: "2026.11.13"
  author: holoviz
---

# Lumen

Lumen AI turns a question about data into SQL, runs it on the user's machine (DuckDB by default) and returns the answer with the query and a chart. From Python the whole workflow is two calls: `lumen.read(...)` builds a Source, and `source.ask("...")` returns an `Answer`.

```python
import lumen

source = lumen.read({"penguins": df})          # name the table with a dict
answer = source.ask("Which species is heaviest on average?")
answer                                          # a card: text, chart, collapsed SQL
answer.value, answer.sql, answer.data           # the parts, for code
```

## Contents

- [References](#references): asking from notebooks, reusing answers, checking and testing, maps and grids
- [Lookup](#lookup)
- [Version](#version)
- [Loading Data](#loading-data)
- [Asking](#asking)
- [Choosing the LLM](#choosing-the-llm)
- [Reading the Answer](#reading-the-answer)
- [Privacy](#privacy)
- [Common Mistakes](#common-mistakes)

## References

Read these for specialized topics. Each is a standalone document you can load on demand.

- [Asking from Notebooks](asking-from-notebooks.md): `lumen.read` inputs, `ask`/`aask`, the Answer's fields, `chat` follow-ups, failed and unanswerable answers, `returns=` typed results, `confirm=True`, `describe`, the `%%lumen` magic, the cache, `configure`, where the card renders
- [Reusing Answers](reusing-answers.md): `refine` and `with_spec` for the chart, `chart`/`to_vega` objects, `compile` to an LLM-free function, `code`/`to_cell`/`export`, `explore` in the chat UI, `ask_about` a clicked point, chat exports
- [Checking and Testing Data](checking-and-testing-data.md): `overview()` quality flags, `check()` rules usable in pytest, recording and replaying LLM calls with `lumen.ai.testing`
- [Asking about Maps and Grids](asking-about-maps-and-grids.md): GeoDataFrames, GeoParquet and xarray input, public Overture/Zarr reads, `gdf`/`ds`/`to_file`/`map`, the spatial and gridded checks Lumen adds

## Lookup

The notebook guide is `docs/getting_started/lumen_in_notebooks.md` in the Lumen repo (`https://github.com/holoviz/lumen/blob/main/docs/getting_started/lumen_in_notebooks.md`); it reaches `https://lumen.holoviz.org` with the 1.5 release. Example notebooks: `examples/notebooks/ask_in_a_notebook.ipynb` and `maps_and_grids.ipynb`. For the chat UI, YAML dashboards and custom agents, use the published docs at `https://lumen.holoviz.org`.

## Version

`lumen.read` and `.ask()` ship in Lumen 1.5. Lumen 1.4 has neither, and fails with `AttributeError: module 'lumen' has no attribute 'read'`. Check `lumen.__version__` before writing this code; until 1.5 is out, install from main:

```bash
pip install "lumen[ai-openai] @ git+https://github.com/holoviz/lumen"
```

The `ai-*` extra names the provider SDK (`ai-openai`, `ai-anthropic`, `ai-google`, ...); `lumen[geo]` and `lumen[xarray]` add maps and grids.

## Loading Data

`lumen.read` accepts file paths, globs and URLs, pandas, polars and GeoPandas DataFrames, pyarrow Tables, xarray Datasets, DuckDB connections, Sources and Pipelines.

- **Name tables with a dict.** `lumen.read({"sales": df})` gives a table the model can call `sales`; a bare path names the table after the whole path, which makes for ugly SQL.
- **One dict, one source.** Every entry of a dict lands in one DuckDB connection, so a question can join them. A ready-made `Source` cannot go inside the dict; pass it on its own.
- **Files stay on disk.** Paths and globs are queried in place, not loaded into memory, so `lumen.read({"sales": "data/*.parquet"})` is the way to ask about large data.

## Asking

- `source.ask(q)` asks about every table; `pipeline.ask(q)` limits the question to one table and its filters.
- `ask` works inside Jupyter's running event loop; don't wrap it in `asyncio.run`. In async code, `await source.aask(q)`.
- `agents=` replaces the default agents. Keep `ChatAgent` in the list (`[ChatAgent, SQLAgent, VegaLiteAgent]`): the planner looks it up by name and raises `KeyError: 'ChatAgent'` without it. By default Lumen uses ChatAgent, SQLAgent and VegaLiteAgent, plus hvPlotAgent when the data has geometry or is a grid.
- The card loads the Panel extension itself the first time it renders; no `pn.extension()` needed.

## Choosing the LLM

Without `llm=`, `ask` uses the first provider whose API key is in the environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...). Pass one explicitly when the user names a model, or set it once for the session:

```python
from lumen.ai import configure
from lumen.ai.llm import Kilo, OpenAI

configure(llm=OpenAI(model_kwargs={"default": {"model": "gpt-6-luna"}}))
answer = source.ask("...", llm=Kilo())   # a question's own llm= wins
```

`Kilo()` serves free models with no account, which suits demos and examples. `LUMEN_AI_PROVIDER` and `LUMEN_AI_MODEL` pick the provider from the environment.

## Reading the Answer

- **`ask` does not raise when a question fails.** It returns an Answer with `status` `"error"` (SQL failed; `answer.retry(hint=...)`) or `"unanswerable"` (the data lacks what the question needs; `answer.error` says why). Check `answer.status == "success"` before using `answer.data` in a script.
- `answer.data` comes back in the input's type: polars for polars, a GeoDataFrame or xarray Dataset for geo or grid input, pandas otherwise.
- `answer.value` is the prose, `answer.sql` the query, `answer.view` the Lumen View, `answer.spec` the Vega-Lite spec (None for an hvPlot chart).
- In a script, echoing `answer` prints one line (`Answer(status='success', value='...')`); read `answer.value` for the text.

## Privacy

Lumen sends the LLM what `share` allows. The default `"sample"` sends values from the data: summaries, examples and chart images. For data that must not leave the machine, use `configure(share="schema")` (names, types, counts, no values) or `"none"`. `mask_pii=True` withholds columns that look like personal data, but judges by name and value patterns, so treat it as best effort. The SQL always runs locally on the full data. Lumen never runs Python the LLM writes unless code execution is turned on.

## Common Mistakes

```python
# WRONG: there is no DataFrame accessor or SmartDataframe in Lumen
df.lumen.ask("...")
# CORRECT: build a Source, then ask it
lumen.read({"sales": df}).ask("...")

# WRONG: a failed question is not an exception
try:
    total = source.ask("Total revenue?").data
except Exception: ...
# CORRECT: read the status
answer = source.ask("Total revenue?")
if answer.status != "success":
    answer = answer.retry(hint="Revenue is in the amount column, in cents")

# WRONG: a second ask starts from scratch, so "only 2024" has nothing to refer to
source.ask("Revenue by month"); source.ask("Only 2024")
# CORRECT: a chat keeps the history and the last answer's data
chat = source.chat(); chat.ask("Revenue by month"); chat.ask("Only 2024")

# WRONG: asking again to restyle a chart reruns the SQL and may change the data
source.ask("Same chart but as bars")
# CORRECT: refine changes the chart only (one LLM call, no SQL)
answer.refine("Draw it as bars sorted by value")
```

Ask questions the data can answer: check the date range and columns first (`source.overview(questions=False)`). A question about a month the data does not cover returns no rows or an `"unanswerable"` answer, not an error.
