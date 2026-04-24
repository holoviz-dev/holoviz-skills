---
name: developing-with-holoviz
description: "Routes to library-specific sub-skills for ALL HoloViz tasks: creating plots, building dashboards and data apps, composing interactive visualizations, or building custom components. Provides guidance for HoloViz libraries. Trigger phrases: panel, hvplot, holoviews, param, dashboard, data app, interactive plot, widget, layout, template, pane, .hvplot, hv.element, pn.widgets, pn.pane, pn.layout, pn.template, panel serve."
---

# Developing with HoloViz Tools

This is a **routing skill** that directs you to the right HoloViz sub-skill for the task at hand.

## Workflow

```
Step 1: Identify which HoloViz library is involved
    ↓
Step 2: Load the matching sub-skill
    ↓
Step 3: Apply the sub-skill guidance to implement or answer the request
```

### Step 1: Identify the Library

A single user request may span multiple libraries
(e.g. plotting data with hvPlot and then embedding the result in a Panel app) —
identify all relevant libraries in that case.

### Step 2: Load the Sub-skill

> **Path note:** Sub-skills are siblings of this skill in your agent's skills directory.
> Use paths relative to this file: `skills/hvplot/SKILL.md`.

| User Need                                                       | Sub-skill to Load              |
| --------------------------------------------------------------- | ------------------------------ |
| Quick exploratory plots from DataFrames / xarray with `.hvplot` | `read skills/hvplot/SKILL.md`  |

### Step 3: Apply Sub-skill Guidance

Follow the instructions in the loaded sub-skill(s) to implement or answer the
request. Each sub-skill contains best practices, DOs/DON'Ts, code patterns, and
dependency information specific to that library.

## Skill Map

| Sub-skill                        | Covers                                                                        |
| -------------------------------- | ----------------------------------------------------------------------------- |
| [hvplot](skills/hvplot/SKILL.md) | Quick interactive plots from DataFrames / xarray using the `.hvplot` accessor |

## Resources

- [HoloViz Documentation](https://holoviz.org/)
- [Panel Documentation](https://panel.holoviz.org/)
- [hvPlot Documentation](https://hvplot.holoviz.org/)
- [HoloViews Documentation](https://holoviews.org/)
- [GeoViews Documentation](https://geoviews.org/)
- [Datashader Documentation](https://datashader.org/)
- [Lumen Documentation](https://lumen.holoviz.org/)
- [Param Documentation](https://param.holoviz.org/)
- [Colorcet Documentation](https://colorcet.holoviz.org/)
- [Panel Material UI Documentation](https://panel-material-ui.holoviz.org/)
