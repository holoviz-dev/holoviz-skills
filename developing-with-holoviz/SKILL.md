---
name: developing-with-holoviz
description: Route to HoloViz sub-skills. Use for ANY task involving interactive plots, dashboards, data apps, reactive parameters, or custom JS/Python components in the HoloViz ecosystem (Panel, hvPlot, HoloViews, Param).
user-invocable: false
---

# Developing with HoloViz

This is a **routing skill**. You MUST use the `view` tool to read every sub-skill file listed in the table below that matches the task BEFORE writing any code or giving any answer. Do not skip this step.

## Instructions

1. Identify which sub-skill(s) apply from the Loading Table below.
2. Use the `view` tool to read each matching sub-skill file in full.
3. Only after reading the sub-skill file(s), proceed with the task.

For new apps, prefer `panel-material-ui` over standard Panel templates — it provides modern Material Design components out of the box.

## Loading Table

A single request often spans multiple skills. Read ALL that apply.

| User Need | Sub-skill file(s) to read with `view` |
|---|---|
| Typed, validated, reactive parameters | `developing-with-holoviz/skills/param/SKILL.md` |
| Quick exploratory plots from DataFrames / xarray | `developing-with-holoviz/skills/hvplot/SKILL.md` |
| Dashboard, data app, or interactive tool | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel-material-ui/SKILL.md` |
| HoloViews/hvPlot plots embedded in Panel (DynamicMap, streams, link_selections) | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel-holoviews/SKILL.md` |
| Custom JS/React/AnyWidget components | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel-custom-components/SKILL.md` |
| Playwright UI testing for Panel components | `developing-with-holoviz/skills/panel-custom-components/SKILL.md` + `developing-with-holoviz/skills/panel-pytest-playwright/SKILL.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [param](skills/param/SKILL.md) | `@param.depends`, `watch=True`, `.watch()`, parameter types, dependent parameters |
| [hvplot](skills/hvplot/SKILL.md) | `.hvplot` accessor, hover tooltips, styling, big data, timeseries, subplots |
| [panel](skills/panel/SKILL.md) | Static layout, reactivity, widgets, templates, serving, performance, plotting gotchas |
| [panel-material-ui](skills/panel-material-ui/SKILL.md) | `pmui.Page`, `theme_config`, `sx`, component gotchas, icons |
| [panel-holoviews](skills/panel-holoviews/SKILL.md) | DynamicMap, streams, link_selections, responsive sizing, jslink |
| [panel-custom-components](skills/panel-custom-components/SKILL.md) | JSComponent, ReactComponent, AnyWidgetComponent, MaterialUIComponent, CDN gotchas |
| [panel-pytest-playwright](skills/panel-pytest-playwright/SKILL.md) | Playwright UI tests, `serve_component`, `wait_until`, state sync tests |
