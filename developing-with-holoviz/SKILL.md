---
name: developing-with-holoviz
description: Route to HoloViz sub-skills. Use for ANY task involving interactive plots, dashboards, data apps, reactive parameters, or custom JS/Python components in the HoloViz ecosystem (Panel, hvPlot, HoloViews, Param).
metadata:
  version: "0.1.4"
  author: holoviz
---

# Developing with HoloViz

This is a **routing skill**. You MUST use the `view` tool to read every sub-skill file listed in the table below that matches the task BEFORE writing any code or giving any answer. Do not skip this step!

## Instructions

1. Identify which sub-skill(s) apply from the Loading Table below.
2. Use the `view` tool to read each matching sub-skill file in full.
3. Only after reading the sub-skill file(s), proceed with the task.

For new apps, prefer `panel-material-ui` over standard Panel templates — it provides modern Material Design components out of the box.

## Loading Table

A single request often spans multiple skills. Read ALL that apply. The Panel skill has reference files under `developing-with-holoviz/skills/panel/` for specialized topics — read those too when relevant.

| User Need | File(s) to read with `view` |
|---|---|
| Typed, validated, reactive parameters | `developing-with-holoviz/skills/param/SKILL.md` |
| Quick exploratory plots from DataFrames / xarray | `developing-with-holoviz/skills/hvplot/SKILL.md` |
| Explore, profile, or understand an unfamiliar dataset; EDA; "what's in this data"; a narrative data story | `developing-with-holoviz/skills/exploring/SKILL.md` (+ `developing-with-holoviz/skills/exploring/story-spec.md` for the spec schema) |
| Dashboard, data app, or interactive tool | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/using-material-ui.md` |
| Convert a design / screenshot / React app into a Material UI (pmui) app | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/using-material-ui.md` + `developing-with-holoviz/skills/panel/converting-designs-to-material-ui.md` (+ `building-custom-components.md` for rich/clickable pieces) |
| HoloViews elements, opts, tooltips, formatters, tools | `developing-with-holoviz/skills/holoviews/SKILL.md` |
| Embedding plots in Panel (HoloViews/hvPlot, Matplotlib, Plotly, ECharts; DynamicMap, responsive sizing) | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/plotting-in-panel.md` + `developing-with-holoviz/skills/holoviews/SKILL.md` |
| Display, filter, sort, or select rows in a data table | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/using-tabulator.md` |
| Custom components — pure-Python (Viewer/PyComponent) or JS/React/AnyWidget | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/building-custom-components.md` |
| Playwright UI testing for Panel components | `developing-with-holoviz/skills/panel/building-custom-components.md` + `developing-with-holoviz/skills/panel/using-pytest-playwright.md` |
| Review or audit a Panel app | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/reviewing-panel-apps.md` |
| Serve, screenshot, and debug a Panel app in a dev loop | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/iterating-on-panel-apps.md` |
| Structure or scale a larger app — multiple views over shared state, sessions, caching, threading, deployment | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/designing-panel-architecture.md` |
| Migrate an existing plain-Panel app to Material UI / pmui | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/migrating-to-material-ui.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [param](skills/param/SKILL.md) | `@param.depends`, `watch=True`, `.watch()`, parameter types, dependent parameters |
| [hvplot](skills/hvplot/SKILL.md) | `.hvplot` accessor, hover tooltips, styling, big data, timeseries, subplots |
| [exploring](skills/exploring/SKILL.md) | Profile any multidimensional dataset (column roles → measures/dimensions/time/ids), then build a grounded narrative EDA notebook (start small → build up the ladder), hvPlot/HoloViews-first, deferring to Panel; ships a profiler + notebook-builder script |
| [holoviews](skills/holoviews/SKILL.md) | Elements, `.opts()`, hover tooltips, formatters, Bokeh tools, DynamicMap, streams, link_selections |
| [panel](skills/panel/SKILL.md) | Static layout, reactivity, widgets, templates, serving, performance, plotting gotchas. Carries 10 topic references (Material UI, custom components, plotting, Tabulator, Playwright testing, review, architecture, migration) — the Loading Table above routes to each; `panel/SKILL.md`'s References section is the full index. |
