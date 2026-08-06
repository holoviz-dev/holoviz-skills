---
name: developing-with-holoviz
description: Route to HoloViz sub-skills. Use for ANY task involving interactive plots, dashboards, data apps, reactive parameters, or custom JS/Python components in the HoloViz ecosystem (Panel, hvPlot, HoloViews, Param) — including tasks that name Bokeh, Matplotlib, or Plotly, since HoloViz embeds those figures and this skill covers how.
user-invocable: true
argument-hint: "[what to build — e.g. dashboard, plot a DataFrame, custom component]"
metadata:
  version: "2026.08.06"
  author: holoviz
---

# Developing with HoloViz

This is a **routing skill**. You MUST read every sub-skill file listed in the table below that matches the task BEFORE writing any code or giving any answer. Do not skip this step!

## Contents

- [Instructions](#instructions)
- [Loading Table](#loading-table)
- [Skill Map](#skill-map)

## Instructions

1. Identify which sub-skill(s) apply from the Loading Table below.
2. Read each matching sub-skill file in full.
3. Only after reading the sub-skill file(s), proceed with the task.

For new apps, prefer `panel-material-ui` over standard Panel templates — it provides modern Material Design components out of the box.

## Loading Table

A single request often spans multiple skills. Read ALL that apply. Paths below are relative to this file's directory (`developing-with-holoviz/`).

| User Need | File(s) to read |
|---|---|
| Typed, validated, reactive parameters | `skills/param/SKILL.md` |
| Quick exploratory plots from DataFrames / xarray | `skills/hvplot/SKILL.md` |
| Compose a layered, faceted view to compare a metric across groups | `skills/hvplot/SKILL.md` + `skills/hvplot/composing-exploratory-plots.md` |
| Make a chart explanatory for an audience (one message, presentation-ready) | `skills/hvplot/SKILL.md` + `skills/hvplot/distilling-explanatory-plots.md` |
| Build a data story / graphic article (charts + narrative) | `skills/hvplot/distilling-explanatory-plots.md` + `skills/panel/SKILL.md` + `skills/panel/using-material-ui.md` + `skills/panel/data-storytelling.md` |
| Dashboard, data app, or interactive tool | `skills/param/SKILL.md` + `skills/panel/SKILL.md` + `skills/panel/using-material-ui.md` |
| Convert a design / screenshot / React app into a Material UI (pmui) app | `skills/panel/SKILL.md` + `skills/panel/using-material-ui.md` + `skills/panel/converting-designs-to-material-ui.md` (+ `skills/panel/building-custom-components.md` for rich/clickable pieces) |
| HoloViews elements, opts, tooltips, formatters, tools | `skills/holoviews/SKILL.md` |
| Remove chart junk / clean a plot — hide or autohide toolbar, disable wheel-zoom, one-axis gridlines, share axes, place legend | `skills/holoviews/SKILL.md` + `skills/holoviews/decluttering-plots.md` |
| Embedding plots in Panel (HoloViews/hvPlot, Matplotlib, Plotly, ECharts; DynamicMap, responsive sizing) | `skills/param/SKILL.md` + `skills/panel/SKILL.md` + `skills/panel/plotting-in-panel.md` + `skills/holoviews/SKILL.md` |
| Stop repeating the same option on every component or chart — session defaults, `pn.config`, `hv.opts.defaults`, class param defaults | `skills/panel/SKILL.md` + `skills/holoviews/SKILL.md` |
| Display, filter, sort, or select rows in a data table | `skills/panel/SKILL.md` + `skills/panel/using-tabulator.md` |
| Plot points or tracks on a map basemap (tiles, Web Mercator, no geo stack) | `skills/holoviews/SKILL.md` + `skills/hvplot/SKILL.md` |
| Custom components — pure-Python (Viewer/PyComponent) or JS/React/AnyWidget | `skills/param/SKILL.md` + `skills/panel/SKILL.md` + `skills/panel/building-custom-components.md` |
| Playwright UI testing for Panel components | `skills/panel/building-custom-components.md` + `skills/panel/using-pytest-playwright.md` |
| Review or audit a Panel app | `skills/panel/SKILL.md` + `skills/panel/reviewing-panel-apps.md` |
| Serve, screenshot, verify rendered output, benchmark startup, and debug a Panel app in a dev loop | `skills/panel/SKILL.md` + `skills/panel/iterating-on-panel-apps.md` |
| Structure or scale a larger app — multiple views over shared state, sessions, caching, threading, deployment | `skills/panel/SKILL.md` + `skills/panel/designing-panel-architecture.md` |
| Migrate an existing plain-Panel app to Material UI / pmui | `skills/panel/SKILL.md` + `skills/panel/migrating-to-material-ui.md` |
| Debug a Panel app that serves but misbehaves — nothing updates, blank Page, flicker, screenshot spinner, version/deprecation surprises | `skills/panel/SKILL.md` + `skills/panel/troubleshooting.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [param](skills/param/SKILL.md) | `@param.depends`, `watch=True`, `.watch()`, parameter types, dependent parameters |
| [hvplot](skills/hvplot/SKILL.md) | `.hvplot` accessor, hover tooltips, styling, big data, timeseries, subplots |
| [holoviews](skills/holoviews/SKILL.md) | Elements, `.opts()`, session defaults (`hv.opts.defaults`), hover tooltips, formatters, Bokeh tools, DynamicMap, streams, link_selections. Carries the Decluttering Plots reference. |
| [panel](skills/panel/SKILL.md) | Static layout, reactivity, widgets, defaults, templates, serving, performance, plotting gotchas; 12 topic references indexed in its own References section |
