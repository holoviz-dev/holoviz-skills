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

A single request often spans multiple skills. Read ALL that apply. The Panel skill has reference files under `developing-with-holoviz/skills/panel/references/` for specialized topics — read those too when relevant.

| User Need | File(s) to read with `view` |
|---|---|
| Typed, validated, reactive parameters | `developing-with-holoviz/skills/param/SKILL.md` |
| Quick exploratory plots from DataFrames / xarray | `developing-with-holoviz/skills/hvplot/SKILL.md` |
| Dashboard, data app, or interactive tool | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/references/material-ui.md` |
| HoloViews/hvPlot plots embedded in Panel (DynamicMap, streams, link_selections) | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/references/holoviews.md` |
| Custom JS/React/AnyWidget components | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/references/custom-components.md` |
| Playwright UI testing for Panel components | `developing-with-holoviz/skills/panel/references/custom-components.md` + `developing-with-holoviz/skills/panel/references/pytest-playwright.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [param](skills/param/SKILL.md) | `@param.depends`, `watch=True`, `.watch()`, parameter types, dependent parameters |
| [hvplot](skills/hvplot/SKILL.md) | `.hvplot` accessor, hover tooltips, styling, big data, timeseries, subplots |
| [panel](skills/panel/SKILL.md) | Static layout, reactivity, widgets, templates, serving, performance, plotting gotchas |

### Panel References

| Reference | Covers |
|---|---|
| [material-ui](skills/panel/references/material-ui.md) | `pmui.Page`, `theme_config`, `sx`, component gotchas, icons |
| [holoviews](skills/panel/references/holoviews.md) | DynamicMap, streams, link_selections, responsive sizing, jslink |
| [custom-components](skills/panel/references/custom-components.md) | JSComponent, ReactComponent, AnyWidgetComponent, MaterialUIComponent, CDN gotchas |
| [pytest-playwright](skills/panel/references/pytest-playwright.md) | Playwright UI tests, `serve_component`, `wait_until`, state sync tests |
| [widget_mapping](skills/panel/references/widget_mapping.md) | Param type → Panel/pmui widget table |
