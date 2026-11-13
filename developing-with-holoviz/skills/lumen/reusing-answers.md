# Reusing Answers

An Answer is a starting point, not a dead end: change its chart, keep the chart as an object, turn the query into a function, or hand it to code, files and the chat UI. Most of this needs no LLM.

## Contents

- [Changing the Chart](#changing-the-chart)
- [The Chart as an Object](#the-chart-as-an-object)
- [Rerunning without an LLM](#rerunning-without-an-llm)
- [Code, Cells and Files](#code-cells-and-files)
- [Asking about a Clicked Point](#asking-about-a-clicked-point)
- [Keeping a Conversation](#keeping-a-conversation)
- [Opening the Chat UI](#opening-the-chat-ui)

## Changing the Chart

Pick the cheapest tool that does the job; every one returns a **new** Answer and leaves the old one as it was.

| Want | Use | Cost |
|---|---|---|
| Restyle in words ("bars, sorted, coloured by species") | `answer.refine("...")` | One LLM call, no SQL |
| Set the spec exactly | `answer.with_spec(spec)` (dict, JSON or YAML text) | No LLM |
| Different data (filter, new column) | `chat.ask("...")` or a new `ask` | Full question |

```python
answer = source.ask("Average body mass per species as a bar chart")
better = answer.refine("Colour the bars by species and sort them by mass")
manual = answer.with_spec({**answer.spec, "mark": "line"})
```

`refine` asking for one change is reliable; several changes at once is flakier on small models, so chain single refines. In the card, the Spec section has Edit and Redraw buttons that do what `with_spec` does.

## The Chart as an Object

```python
answer.chart          # Altair chart for Vega-Lite (needs altair); HoloViews object for hvPlot
answer.chart + other  # compose, .opts(...), save like any Altair/HoloViews object
answer.to_vega()      # self-contained Vega-Lite spec with the data inlined
```

`answer.chart` is None when the answer has no chart. `to_vega()` raises for an hvPlot chart without geometry (a grid or density image); use `answer.chart` there.

Scatter and line answers over 5,000 points are drawn with hvPlot and datashader as a density image (category-coloured charts blend the categories); the card says so. Without datashader installed they stay Vega-Lite.

## Rerunning without an LLM

`compile` turns the answer's query into a plain function with bound parameters:

```python
count = source.ask("How many penguins were measured in 2008?").compile(["year"])
count(year=2009)              # same query, 2009
count(year=(2007, 2008))      # a (low, high) pair for BETWEEN
count(year=[2007, 2009])      # a list for IN
```

Each parameter is a column the query compares with a literal. Values are bound, never pasted into the SQL. It works on DuckDB sources (what `lumen.read` gives); a column compared with two different literals cannot be one parameter.

## Code, Cells and Files

| Call | Gives |
|---|---|
| `answer.code` | Lumen code that rebuilds the result and chart without an LLM; in-memory data is embedded, so keep it for small results |
| `answer.to_cell()` | That code in a new cell below (Jupyter) |
| `answer.export("out")` | `out/answer.py` plus the data as Parquet under `out/data/`, for large results |
| `answer.to_file("x.parquet")` | The result data by extension (see the maps reference for geo and grid formats) |

`answer.code` copies source settings as they are; check it for credentials (a database URI with a password) before sharing.

## Asking about a Clicked Point

Clicking a point, bar or shape on an answer's chart (or box-selecting on an hvPlot chart) opens an "Ask about this" box under it, and fills `answer.selection`. From code:

```python
answer.ask_about("Why is this one so high?")                     # uses answer.selection
answer.ask_about("Show its history", rows={"island": "Dream"})   # or pass the rows
```

`rows=` takes a DataFrame, a dict, a list of dicts or row positions. The model answers from the rows (up to 20) when they hold the answer and queries the data filtered on them otherwise. It sends row values, so it needs `share="sample"`. Saved notebooks and PNGs have no click target.

## Keeping a Conversation

```python
chat.to_html("chat.html")          # one page: questions, answers, chart images, SQL, specs
chat.to_notebook("chat.ipynb")     # each turn plus Lumen code that rebuilds it with no LLM
chat.to_report("Penguins")         # a Lumen Report with to_html / to_notebook / to_docx
```

The exported notebook runs in a fresh kernel without an LLM.

## Opening the Chat UI

```python
answer.explore()   # ExplorerUI on the same source and LLM, this answer as its first exploration
```

Display the returned object in a notebook, or serve it (`.servable()` under `panel serve`). Keyword arguments go to `ExplorerUI`. For a standalone chat app over files, the CLI is `lumen-ai serve data.csv`.
