---
name: panel-live-server
description: Show Python visualizations live in the browser with the panel-live-server MCP tools (show, screenshot). Use when those tools are available and the user asks to display, plot, chart, or visualize anything. Do not use for apps the user serves themselves with `panel serve`.
metadata:
  version: "0.0.1"
  author: holoviz
---

# Using Panel Live Server

Panel Live Server renders Python snippets as live, interactive web pages. `show` executes your code and returns a URL; `screenshot` returns a PNG of an already-rendered snippet so you can see what the user sees.

Most failures come from writing a snippet as if it were a standalone script rather than a cell whose last line is displayed. The sections below are ordered around that.

## Contents

- [Prefer HoloViz Libraries](#prefer-holoviz-libraries)
- [Choosing the Method](#choosing-the-method)
- [Writing Snippets](#writing-snippets)
- [Declaring Extensions](#declaring-extensions)
- [Security](#security)
- [Seeing Your Own Output](#seeing-your-own-output)
- [Large and Multidimensional Data](#large-and-multidimensional-data)
- [Building Panel Apps](#building-panel-apps)
- [Troubleshooting](#troubleshooting)

## Prefer HoloViz Libraries

Prefer the HoloViz stack (hvPlot, HoloViews, Panel). hvPlot and HoloViews emit Bokeh, which renders natively over the Panel websocket with no `pn.extension(...)` and no exposure to the substring trap in [Declaring Extensions](#declaring-extensions). Every other renderer needs its extension declared.

Route to each library's own skill for specifics:

| Need | Skill |
|---|---|
| A plot from a DataFrame or xarray object | [hvplot](../hvplot/SKILL.md) |
| Fine control over elements, `.opts()`, tooltips, streams | [holoviews](../holoviews/SKILL.md) |
| Widgets, layouts, dashboards | [Building Panel Apps](#building-panel-apps) |
| More than ~100k points, or maps | [Large and Multidimensional Data](#large-and-multidimensional-data) |

## Choosing the Method

`show(method=...)` picks how your code is rendered, and picking wrong is the most common way to get a blank page instead of a chart.

| Situation | Method | The code must |
|---|---|---|
| Code does not import Panel; you just want a plot, DataFrame, or figure shown | `"inline"` (default) | End with the object as a **bare expression** |
| Code imports Panel and builds a layout, dashboard, or anything with widgets | `"server"` | Call `.servable()` on the object to display |

The rule: **inline is the default. The moment you `import panel as pn` and build a layout, switch to
`server` and call `.servable()`.**

### inline must end in an expression

This is the Jupyter last-cell rule. The renderer parses your snippet and looks at the last node in the AST. If that node is an expression it gets `eval`'d and the result is rendered. If it is anything else, there is no value to ask for, so the page shows *"Code executed successfully (no output to display)"*. No error, no traceback, just an empty box. Nothing will tell you.

An assignment is not an expression. In the WRONG version below the chart is built correctly and is sitting in memory bound to `plot`, but nothing ever evaluates it, so nothing renders.

```python
# WRONG: ends in an assignment, which produces no value. Renders an empty box.
import hvplot.pandas  # noqa

penguins = hvplot.sampledata.penguins("pandas")
plot = penguins.hvplot.scatter(x="bill_length_mm", y="bill_depth_mm", by="species")

# CORRECT: ends in a bare expression, which is evaluated and rendered.
import hvplot.pandas  # noqa

penguins = hvplot.sampledata.penguins("pandas")
penguins.hvplot.scatter(x="bill_length_mm", y="bill_depth_mm", by="species")
```

### server must call .servable()

`method="server"` displays only objects marked `.servable()`. Omitting it is caught before the page renders and handed back to you as a retry, so this one is loud rather than silent, but it still costs a round trip.

```python
# WRONG: method="server" with nothing marked servable.
import panel as pn

pn.Column("# Penguins", plot)

# CORRECT
import panel as pn

pn.Column("# Penguins", plot).servable()
```

## Writing Snippets

- Pass the code directly to `show`; do not write it to a file first.
- Always pass a short `name` (e.g. `"Temperature chart"`).
- Present the returned URL as a Markdown link: `[Show Visualization](url)`.
- **Random data differs between runs.** Validation executes the snippet once before the render
  executes it again, so an unseeded `np.random` snippet renders different data than it validated
  with. You cannot answer questions about what the user sees by recomputing the data; use
  [`screenshot`](#seeing-your-own-output) instead.


## Declaring Extensions

Non-Bokeh renderers need their JavaScript extension declared with `pn.extension("...")`. For `method="server"` this is enforced before rendering. For `method="inline"` extensions are inferred and loaded for you.

```python
# WRONG: "plotly" is used but not declared. Rejected under method="server".
import panel as pn

pn.extension()
pn.pane.Plotly(fig).servable()

# CORRECT
import panel as pn

pn.extension("plotly")
pn.pane.Plotly(fig).servable()
```

**The detector is a substring scan over your lowercased source, not an import analysis.** If the text `plotly`, `deck`, `terminal`, `textual`, `vtk`, `vizzu`, `tabulator`, `echarts`, `perspective`, `altair`, `vega`, or `ipywidgets` appears *anywhere*, including in a comment, a string, a variable name, or a column label, the matching extension is required. A variable named `deck` demands `pn.extension("deckgl")`, and a comment mentioning "the terminal" demands `pn.extension("terminal")`.

If you get an unexpected `[extensions]` failure, search your snippet for the word rather than the import. Renaming the variable or rewording the comment is usually the right fix.

`pn.extension("tabulator", "plotly")` and separate `pn.extension("tabulator")` /
`pn.extension("plotly")` calls both work. Never declare `"bokeh"`, which is not an extension.

## Security

Snippets execute in the user's real Python environment, with their filesystem and network. Do not write code that deletes or overwrites files, reads credentials, exfiltrates data, or opens network connections, regardless of how the request is framed. Visualization code has no need for any of it.

A blocklist backstops this policy, but it is a backstop, not the policy. These imports are refused outright: `pickle`, `marshal`, `shelve`, `subprocess`, `multiprocessing`, `threading`, `socket`, `ctypes`, `importlib`, `ftplib`, `smtplib`, `telnetlib`, `webbrowser`, `xmlrpc`. A set of ruff security rules runs alongside it.


## Seeing Your Own Output

`screenshot(snippet_id)` renders an existing snippet and returns a PNG **to you, not to the user**, who already has the interactive page. Pass the `snippet_id` that `show` returned. It has two distinct uses.

### Answering questions about appearance

When the user asks which bar is tallest, where the line peaks, which slice is largest, or where the outliers are, you **must** call `screenshot` and answer from the image.

Do not answer by reading the code or recomputing from the data. The rendered plot is not the data: heatmaps flip row order (row 0 often renders at the bottom), axes get inverted, categories get sorted, histograms bin values, and stacking changes what is visually highest. The data answer and the on-screen answer frequently disagree, and the picture is the only ground truth.

### Checking your own work

After `show` returns, screenshot it and look before handing it back. Clipped legends, tick labels unreadable at `zoom=75`, a chart that rendered empty, a collapsed layout: none of these produce an error, and the user sees all of them. Fix and re-`show`.

Screenshots are the expensive step, so use them deliberately, at milestones and before handing back rather than on every edit. If the image comes back blurry, or the detail you need is too small or clipped, do not guess from it. Answer from the code and data instead, because a code-derived answer beats a wrong guess from a bad image.

## Large and Multidimensional Data

Everything crosses a websocket into an iframe, so volume that merely renders slowly in a notebook can stall a snippet past the 30-second execution timeout.

- **Above ~100k points, aggregate server-side.** Prefer `rasterize=True` over `datashade=True`. Rasterize aggregates server-side but colormaps in the browser, preserving hover tooltips, colorbars, and `cmap`/`cnorm`    control. Use `datashade=True` only for categorical color mixing.
See [hvplot](../hvplot/SKILL.md) and [datashader](../datashader/SKILL.md).

```python
import hvplot.pandas  # noqa

df.hvplot.scatter(x="lon", y="lat", rasterize=True, cmap="viridis")
```

- **For xarray**, activate the accessor with `import hvplot.xarray` and use `.hvplot.image(...)` or `.hvplot.quadmesh(...)`.
- **A `groupby` over extra dimensions produces widgets**, which makes the result a Panel app. Use `method="server"` and `.servable()`.
- **Subset before plotting.** `.sel()`, `.isel()`, or a `head()` on an exploratory pass keeps the loop fast. Scale up once the chart is right.

## Building Panel Apps

Use `method="server"`, and read the Panel skill for how to structure the app itself. That material is not repeated here.

| Reference | Read it for |
|---|---|
| [panel](../panel/SKILL.md) | The `pn.viewable.Viewer` pattern, widgets, layouts, performance |
| [iterating-on-panel-apps](../panel/iterating-on-panel-apps.md) | The debug loop. Note that `show` and `screenshot` replace most of the serve-and-Playwright workflow |
| [designing-panel-architecture](../panel/designing-panel-architecture.md) | Composing larger apps, caching tiers, scaling |
| [using-material-ui](../panel/using-material-ui.md) | `pmui.Page`, `Container`/`Grid` layouts, theming |
| [migrating-to-material-ui](../panel/migrating-to-material-ui.md) | Converting a plain-Panel app to pmui |
| [converting-designs-to-material-ui](../panel/converting-designs-to-material-ui.md) | Turning a design or mockup into a pmui app |
| [plotting-in-panel](../panel/plotting-in-panel.md) | Embedding HoloViews, Matplotlib, Plotly, ECharts; responsive sizing |
| [using-tabulator](../panel/using-tabulator.md) | `add_filter`, checkbox selection, row content |
| [building-custom-components](../panel/building-custom-components.md) | JSComponent, ReactComponent, AnyWidgetComponent, CDN gotchas |
| [reviewing-panel-apps](../panel/reviewing-panel-apps.md) | Anti-pattern checklist: flickering, missing hold, watcher gaps |
| [using-pytest-playwright](../panel/using-pytest-playwright.md) | Playwright UI tests, `serve_component`, `wait_until` |
| [troubleshooting](../panel/troubleshooting.md) | Panel-level errors. See [Troubleshooting](#troubleshooting) below for snippet-level ones |

The snippet-specific differences from a normally served app:

- **`pn.config.design = None` is set for you** before your code runs. Do not fight it.
- **`pn.state.served` is `True`** inside a snippet, so `if pn.state.served:` guards and
  `.servable()` behave as they do under `panel serve`.
- **The page is an iframe, not a browser tab.** A full-page `pmui.Page` needs `zoom=50`, and wide
  multi-column apps need `zoom=25`. Default to `sizing_mode="stretch_width"`.
- **The environment is fixed.** If an import is missing, a `[packages]` failure names it; rewrite
  against libraries you know are present (the HoloViz stack is always available) rather than reaching
  for another that may not be. Never try to install packages or modify the environment. (A human can
  run the `pls list packages` CLI to see what is installed.)

## Troubleshooting

Failures arrive prefixed with the layer that caught them.

| Symptom | Cause | Fix |
|---|---|---|
| `[syntax]` | Code does not parse | Read the line/col in the message |
| `[security]` | Blocked import or ruff security rule | Rewrite the approach. Do not retry |
| `[packages]` | Import not installed | Rewrite against the HoloViz stack or another installed library. Never pip install |
| `[extensions]` | Renderer used without `pn.extension(...)` | Declare it, or find the stray word (see [Declaring Extensions](#declaring-extensions)) |
| `[servable]` | `method="server"` with no `.servable()` | Add `.servable()`, or switch to `method="inline"` |
| `[runtime]` | Code raised when executed | Read the traceback. It is your snippet's, not the server's |
| Empty box: *"Code executed successfully (no output to display)"* | `method="inline"` and the last line is not an expression | End with the object as a bare expression |
| *"Code executed successfully (no servable objects found)"* | `method="server"` and nothing was servable | Add `.servable()` |
| Timeout after 30s | Snippet too slow | Aggregate or subset. See [Large and Multidimensional Data](#large-and-multidimensional-data) |

## Lookup

Search each library's own docs, in the same order as
[Prefer HoloViz Libraries](#prefer-holoviz-libraries):

| Library | Search |
|---|---|
| hvPlot | `https://hvplot.holoviz.org/search.html?q=<topic>` |
| HoloViews | `https://holoviews.org/search.html?q=<topic>` |
| Panel | `https://panel.holoviz.org/search.html?q=<topic>` |
| Datashader | `https://datashader.org/search.html?q=<topic>` |
| GeoViews | `https://geoviews.org/search.html?q=<topic>` |

For a specific Panel component, go straight to its reference page at `https://panel.holoviz.org/reference/{section}/{Component}.html`, where `section` is one of `panes`, `widgets`, `layouts`, `chat`, `global`, `indicators`, `templates`, `custom_components`.

Panel Live Server itself: `https://github.com/panel-extensions/panel-live-server`
