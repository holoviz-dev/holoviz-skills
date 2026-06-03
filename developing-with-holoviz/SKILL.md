---
name: developing-with-holoviz
description: Route to HoloViz sub-skills. Use for ANY task involving interactive plots, dashboards, data apps, reactive parameters, or custom JS/Python components in the HoloViz ecosystem (Panel, hvPlot, HoloViews, Param).
---

# Developing with HoloViz

This is a **routing skill**. You MUST use the `view` tool to read every sub-skill file listed in the table below that matches the task BEFORE writing any code or giving any answer. Do not skip this step.

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
| Dashboard, data app, or interactive tool | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/applying-material-ui.md` |
| HoloViews elements, opts, tooltips, formatters, tools | `developing-with-holoviz/skills/holoviews/SKILL.md` |
| HoloViews/hvPlot plots embedded in Panel (DynamicMap, responsive sizing) | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/interacting-with-holoviews.md` + `developing-with-holoviz/skills/holoviews/SKILL.md` |
| Custom JS/React/AnyWidget components | `developing-with-holoviz/skills/param/SKILL.md` + `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/building-custom-components.md` |
| Playwright UI testing for Panel components | `developing-with-holoviz/skills/panel/building-custom-components.md` + `developing-with-holoviz/skills/panel/using-pytest-playwright.md` |
| Review or audit a Panel app | `developing-with-holoviz/skills/panel/SKILL.md` + `developing-with-holoviz/skills/panel/reviewing-panel-apps.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [param](skills/param/SKILL.md) | `@param.depends`, `watch=True`, `.watch()`, parameter types, dependent parameters |
| [hvplot](skills/hvplot/SKILL.md) | `.hvplot` accessor, hover tooltips, styling, big data, timeseries, subplots |
| [holoviews](skills/holoviews/SKILL.md) | Elements, `.opts()`, hover tooltips, formatters, Bokeh tools, DynamicMap, streams, link_selections |
| [panel](skills/panel/SKILL.md) | Static layout, reactivity, widgets, templates, serving, performance, plotting gotchas |

### Panel References

| Reference | Covers |
|---|---|
| [iterating-on-panel-apps](skills/panel/iterating-on-panel-apps.md) | Serve with logging, screenshot with Playwright, debug loop |
| [applying-material-ui](skills/panel/applying-material-ui.md) | `pmui.Page`, `Container`/`Grid` layouts, centering, component gotchas |
| [branding-material-ui](skills/panel/branding-material-ui.md) | `theme_config` palettes, typography, icons, brand assets, chart theming |
| [interacting-with-holoviews](skills/panel/interacting-with-holoviews.md) | DynamicMap trigger pattern in Panel, `pn.pane.HoloViews` config, responsive sizing |
| [using-tabulator](skills/panel/using-tabulator.md) | `add_filter` with widgets, checkbox selection, row content, function-based filtering |
| [building-custom-components](skills/panel/building-custom-components.md) | JSComponent, ReactComponent, AnyWidgetComponent, MaterialUIComponent, CDN gotchas |
| [using-pytest-playwright](skills/panel/using-pytest-playwright.md) | Playwright UI tests, `serve_component`, `wait_until`, state sync tests |
| [mapping-widgets](skills/panel/mapping-widgets.md) | Param type → Panel/pmui widget table |
| [reviewing-panel-apps](skills/panel/reviewing-panel-apps.md) | Review checklist: flickering, missing hold, watcher gaps, bind vs watch, mutation bugs |
