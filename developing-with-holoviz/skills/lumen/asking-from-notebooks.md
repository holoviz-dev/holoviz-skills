# Asking from Notebooks

The day-to-day loop: read data, ask, read the Answer, follow up. Everything here works in a script too; only the card and the magic need a notebook.

## Contents

- [Reading Data](#reading-data)
- [Asking](#asking)
- [The Answer](#the-answer)
- [Following Up with a Chat](#following-up-with-a-chat)
- [Failed and Unanswerable Questions](#failed-and-unanswerable-questions)
- [Typed Answers](#typed-answers)
- [Better Answers: Describe, Preview, Cache](#better-answers-describe-preview-cache)
- [The %%lumen Magic](#the-lumen-magic)
- [Session Settings](#session-settings)
- [Where the Card Renders](#where-the-card-renders)

## Reading Data

```python
import hvsampledata
import lumen

source = lumen.read({"penguins": hvsampledata.penguins("pandas")})
source = lumen.read({"orders": orders_df, "customers": "data/customers.parquet"})  # joinable
source = lumen.read({"sales": "data/sales/*.parquet"})              # stays on disk
pipeline = lumen.Pipeline(source=source, table="penguins")         # one table
```

- Inputs: paths, globs, URLs, pandas/polars/GeoPandas DataFrames, pyarrow Tables, xarray Datasets, DuckDB connections, Sources, Pipelines.
- A dict puts every entry in one DuckDB connection under the name you give it, so the model can join them. A DuckDB connection's tables are copied in; xarray data becomes lazy views.
- A ready-made Source cannot sit inside the dict; pass it to `lumen.read` (or call `.ask` on it) on its own.
- `hvsampledata` (`penguins`, `earthquakes`, `us_states`, `air_temperature`) is the standard demo data: no downloads, so examples run anywhere.

## Asking

```python
answer = source.ask("Which species is heaviest on average?")
answer = pipeline.ask("Average body mass by island")   # only this table and its filters
answer = await source.aask("...")                      # in async code
```

- Keyword arguments: `llm=`, `agents=`, `confirm=`, `returns=`. Nothing else; there is no `table=` on `source.ask` (use a Pipeline).
- While it runs, one line under the cell shows the current step. Interrupting the kernel cancels the question and its LLM calls.
- `ask` runs on Lumen's own background loop, so it works inside Jupyter's running loop without `nest_asyncio`.

## The Answer

The card shows the written answer, the chart, and collapsed SQL, Spec and Steps sections, ending in a token and cost line. For code:

| Field | Holds |
|---|---|
| `value` | The written answer (Markdown) |
| `sql` | The query that produced the data |
| `data` | The result in the input's type: polars, pyarrow, GeoDataFrame, xarray Dataset, else pandas |
| `pipeline` | A Lumen Pipeline over the result |
| `view` / `spec` | The chart as a Lumen View; `spec` is its Vega-Lite spec, None for hvPlot charts |
| `status` | `"success"`, `"error"`, `"unanswerable"` or `"planned"` (with `confirm=True`) |
| `error` | Why it failed or cannot be answered |
| `usage` | Tokens and cost: `answer.usage.input_tokens`, `.output_tokens`, `.cost_usd` (None when the provider is unpriced) |
| `plan`, `why`, `trace` | The planner's steps, its reasoning, and each step as it ran (seconds, LLM calls, SQL); `answer.plan.graph()` / `.to_mermaid()` |

`answer.data` follows the input type only for data read with `lumen.read`; a Source built by hand gives pandas.

## Following Up with a Chat

A plain second `source.ask` knows nothing of the first. Use a chat when questions build on each other:

```python
chat = source.chat()
chat.ask("What is the average body mass per species?")
chat.ask("Only keep the species above 4000 g")   # runs on the data the last answer left
chat                                             # in a notebook: a chat widget with the history
```

Typing into the widget calls `chat.ask`, so code and widget share one conversation. A chat does not build on an answer that failed.

## Failed and Unanswerable Questions

`ask` returns instead of raising. Branch on `status`:

```python
answer = source.ask("Average flipper length by island in cm?")
if answer.status == "error":           # the SQL failed; the card shows it, open
    answer = answer.retry(hint="Flipper length is in mm, divide by 10")
elif answer.status == "unanswerable":  # no table holds what the question needs
    print(answer.error)                # e.g. "No table records beak colour."
```

`retry()` with no hint asks again. An unanswerable answer ran no query. A plan that neither queries nor answers comes back as an error, so `retry` can redo it.

## Typed Answers

`returns=` gets a value instead of prose, in `answer.result`:

```python
from pydantic import BaseModel

source.ask("How many penguins were measured in 2008?", returns=int).result   # 114

class Heaviest(BaseModel):
    species: str
    body_mass_g: float

source.ask("Which species is heaviest on average?", returns=Heaviest).result
```

When the result already has the shape (one cell for a number, one column for a list, one row for a model) no extra LLM call is made; otherwise one structured call reads the type from the answer. It can round (`int` from 38.5). A value that cannot be read as the type gives `status == "error"`.

## Better Answers: Describe, Preview, Cache

**Describe the data.** The SQL improves most when the model knows what columns mean and their units:

```python
source.describe(
    "penguins", "One row per penguin measured on the Palmer Archipelago, 2007 to 2009",
    columns={"body_mass_g": "Body mass in grams", "sex": "male or female, missing for some birds"},
)
```

It overrides any description from the database, and the next question sees it.

**Preview the plan.** `confirm=True` stops after planning; the card lists the steps with a Run button:

```python
plan = source.ask("Which island has the heaviest penguins?", confirm=True)
plan.status   # "planned"
plan.run()    # runs exactly those steps, no second planning call; returns the same object
```

**Cache answers.** `configure(cache=True)` keeps up to 128 answers in memory; the same question on the same data and model returns at once, marked "From the answer cache". Lumen keys on cached metadata, so after a file or database changes call `lumen.ai.clear_cache()`. Answers over DataFrames or dicts passed directly are never cached, nor are retries.

## The %%lumen Magic

```python
%load_ext lumen.ai.notebook
```

```python
%%lumen source --as heaviest
Which species was heaviest in {year}?
```

The first word names the Source or Pipeline variable, `{name}` fills in a variable, `--as` stores the Answer, `--confirm` previews the plan. `%lumen source How many rows?` asks in one line.

## Session Settings

```python
from lumen.ai import configure
from lumen.ai.llm import Kilo

configure(llm=Kilo(), max_rows=100_000, share="schema", mask_pii=True, cache=True)
```

| Setting | Env variable | Effect |
|---|---|---|
| `llm` | `LUMEN_AI_PROVIDER`, `LUMEN_AI_MODEL` | Default LLM; without it, the first provider with an API key |
| `agents` | | Default agents (keep `ChatAgent` in a custom list) |
| `max_rows` | | LIMIT on an answer's query, 1,000,000 by default, `None` for all; the card notes when a result hits it |
| `share` | `LUMEN_AI_SHARE` | `"sample"` (values reach the LLM), `"schema"` (no values), `"none"` (names and counts only) |
| `mask_pii` | `LUMEN_AI_MASK_PII` | Withhold columns that look like personal data |
| `cache` | `LUMEN_AI_CACHE` | In-memory answer cache |

A question's own `llm=` or `agents=` wins over `configure`.

## Where the Card Renders

| Front end | Result |
|---|---|
| JupyterLab, Notebook 7, Colab | Interactive card |
| VS Code | Interactive card once `jupyter_bokeh` is installed in the kernel's environment; otherwise text, Vega-Lite chart and SQL as plain outputs |
| marimo | Static card (text, PNG, SQL); pick the Vega-Lite output for an interactive chart |
| Script or REPL | One line, `Answer(status='success', value='...')`; read the fields |

PNG and plain-output fallbacks exist for Vega-Lite charts only: an hvPlot chart (maps, grids, density images) shows in the interactive card and nowhere else, so a saved notebook loses it.
