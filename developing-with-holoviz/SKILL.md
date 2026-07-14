---
name: developing-with-holoviz
description: Route to HoloViz sub-skills. Use for ANY task involving interactive plots, dashboards, data apps, reactive parameters, or custom JS/Python components in the HoloViz ecosystem (Panel, hvPlot, HoloViews, Param), including Panel apps that embed Bokeh, Matplotlib, or Plotly figures. A named plotting library (e.g. bokeh) is not a reason to skip this skill.
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
| Debug a Panel app that serves but misbehaves — nothing updates, blank Page, flicker, screenshot spinner, version/deprecation surprises | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/troubleshooting.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [param](skills/param/SKILL.md) | `@param.depends`, `watch=True`, `.watch()`, parameter types, dependent parameters |
| [hvplot](skills/hvplot/SKILL.md) | `.hvplot` accessor, hover tooltips, styling, big data, timeseries, subplots |
| [holoviews](skills/holoviews/SKILL.md) | Elements, `.opts()`, hover tooltips, formatters, Bokeh tools, DynamicMap, streams, link_selections |
| [panel](skills/panel/SKILL.md) | Static layout, reactivity, widgets, templates, serving, performance, plotting gotchas. Carries 11 topic references (Material UI, custom components, plotting, Tabulator, Playwright testing, review, iterating, architecture, migration, converting designs, troubleshooting) — the Loading Table above routes to each; `panel/SKILL.md`'s References section is the full index. |
