# HoloViz Claude Skills

A curated collection of **Claude Skills** for the [HoloViz](https://holoviz.org) ecosystem.

## What are Claude Skills?

[Claude Skills](https://www.anthropic.com/news/skills) are folders containing a `SKILL.md` file along with any supporting scripts, references, or examples. When loaded into Claude, a skill teaches it domain-specific best practices, common pitfalls, and the correct APIs for a given library or workflow.

Skills help Claude produce **correct, idiomatic HoloViz code** instead of relying on potentially outdated training data.

## Available Skills

The skills in this repository cover the full HoloViz stack:

### Router

- **`developing-with-holoviz`** — Top-level router that delegates to the correct sub-skill for any HoloViz task.

### Library-specific skills

- **`panel`** — Build reactive, component-based UIs, dashboards, and data apps with [Panel](https://panel.holoviz.org).
- **`panel-material-ui`** — Modern Material UI–themed Panel apps.
- **`panel-custom-components`** — Wrap JS libraries or build custom widgets using `JSComponent`, `ReactComponent`, `AnyWidgetComponent`, or `MaterialUIComponent`.
- **`panel-holoviews`** — Embed HoloViews/hvPlot plots in Panel, preserve zoom/pan state, wire up streams and cross-filtering.
- **`hvplot`** — Quick exploratory data analysis with a Pandas `.plot`–like API using [hvPlot](https://hvplot.holoviz.org).
- **`holoviews`** — Advanced, interactive, publication-quality visualizations with [HoloViews](https://holoviews.org).
- **`param`** — Build Python classes with validated, typed parameters using [Param](https://param.holoviz.org).

### Tooling

- **`holoviz-mcp-cli`** — Command reference for the `holoviz-mcp` CLI, giving Claude direct access to HoloViz docs and component introspection from the shell.

## Using these skills

Claude Skills can be used in a few ways:

1. **Claude Code** — Place skills in `~/.claude/skills/` or a project-local `.claude/skills/` directory.
2. **Claude.ai / API** — Upload skills through the Skills feature where supported.
3. **MCP integrations** — Reference skills through MCP-aware clients.

Once installed, Claude automatically consults the relevant skill whenever you ask it to do HoloViz work — for example, *“build me a Panel dashboard for this dataframe”* will trigger `developing-with-holoviz`, which then routes to `panel` and `hvplot` as needed.

## Why skills?

HoloViz libraries evolve quickly, and LLM training data lags. Without a skill, Claude may:

- Use deprecated APIs (`pn.interact`, old HoloViews syntax, etc.)
- Mix incompatible idioms across HoloViz libraries
- Miss newer features like `pn.rx`, `panel-material-ui`, or modern `hvplot` options

Skills pin Claude to the **current, recommended way** of doing things.

## Links

- [Skills repository](https://github.com/holoviz-dev/holoviz-skills)
- [HoloViz website](https://holoviz.org)
- [Anthropic Skills announcement](https://www.anthropic.com/news/skills)
