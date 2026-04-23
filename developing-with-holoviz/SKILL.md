---
name: developing-with-holoviz
description: "Use for ALL HoloViz tasks: creating plots, building dashboards and data apps, composing interactive visualizations, building custom components, or using the holoviz-mcp CLI. Provides guidance for HoloViz libraries. Trigger phrases: panel, hvplot, holoviews, param, dashboard, data app, interactive plot, widget, layout, template, pane, .hvplot, hv.element, pn.widgets, pn.pane, pn.layout, pn.template, panel serve, holoviz-mcp."
---

# Developing with HoloViz Tools

This skill provides guidance for working with the HoloViz ecosystem of tools.

## When to Use

Invoke this skill for any HoloViz-related task including:

- **Panel**: dashboards, data apps, widgets, panes, layouts, templates, custom components (JS/React)
- **hvPlot**: interactive plots using `.hvplot` on DataFrames or xarray
- **HoloViews**: composing elements, overlays, or layouts
- **Param**: parameterized classes with validated, reactive parameters
- **Panel Material UI**: Material UI components
- **holoviz-mcp CLI**: documentation or component introspection

**Trigger phrases:** `panel`, `hvplot`, `holoviews`, `param`, `dashboard`, `data app`,
`interactive plot`, `widget`, `layout`, `template`, `pane`, `.hvplot`, `hv.element`,
`pn.widgets`, `pn.pane`, `pn.layout`, `pn.template`, `panel serve`, `holoviz-mcp`

## Workflow

```
Step 1: Identify which HoloViz library is involved
    ↓
Step 2: Apply library-specific guidance (sub-skills coming soon)
    ↓
Step 3: Implement or answer the request using HoloViz best practices
```

### Step 1: Identify the Library

A single user request may span multiple libraries
(e.g. plotting data with hvPlot and then embedding the result in a Panel app) —
identify all relevant libraries in that case.

### Step 2: Apply Library-Specific Guidance

> **Note:** Detailed sub-skills for each HoloViz library will be available at
> `skills/panel/SKILL.md`, `skills/hvplot/SKILL.md`, etc. in a future update.
> For now, refer to the official documentation linked in the Resources section below.

### Step 3: Implement the Solution

Use HoloViz best practices, official documentation, and examples to implement or answer the
request. Each library has specific patterns for creating visualizations, building apps,
and composing interactive elements.

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
