---
name: developing-with-holoviz
description: Route to HoloViz sub-skills. Use for ANY task involving interactive plots, dashboards, data apps, reactive parameters, or custom JS/Python components in the HoloViz ecosystem (Panel, hvPlot, HoloViews, Param).
---

# Developing with HoloViz Tools

This is a **routing skill** — load the matching sub-skill(s) for the task at hand.

> **Path note:** Sub-skills live in `skills/` relative to this file.

## Loading Table

A single request often spans multiple skills. Load all that apply.

For new apps, prefer `panel-material-ui` over standard Panel templates — it provides modern Material Design components out of the box.

| User Need | Skills to Load |
|---|---|
| Typed, validated, reactive parameters | `skills/param/SKILL.md` |
| Quick exploratory plots from DataFrames / xarray | `skills/hvplot/SKILL.md` |
| Dashboard, data app, or interactive tool | `skills/param/SKILL.md` + `skills/panel/SKILL.md` + `skills/panel-material-ui/SKILL.md` |
| HoloViews/hvPlot plots embedded in Panel (DynamicMap, streams, link_selections) | `skills/param/SKILL.md` + `skills/panel/SKILL.md` + `skills/panel-holoviews/SKILL.md` |
| Custom JS/React/AnyWidget components | `skills/param/SKILL.md` + `skills/panel/SKILL.md` + `skills/panel-custom-components/SKILL.md` |
| Playwright UI testing for Panel components | `skills/panel-custom-components/SKILL.md` + `skills/panel-pytest-playwright/SKILL.md` |

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
