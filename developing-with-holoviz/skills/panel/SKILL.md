---
name: panel
description: Build interactive dashboards, tools, and data apps with HoloViz Panel. Use when the user needs widgets, layouts, templates, or reactive server-side Python web applications. Do not use for standalone plots without widgets (use hvPlot).
metadata:
  version: "1.0.3"
  author: holoviz
---

# Using Panel

Panel is a Python library for building interactive dashboards, data apps, and tools entirely in Python — no JavaScript required. It connects widgets to plots, tables, and text with reactive callbacks, and serves the result as a web application.

Always use a `pn.viewable.Viewer` class to structure apps. This keeps state, layout, and logic organized and avoids flickering from recreated components. Once an app outgrows one class — multiple views over shared data, state several components touch — split it into composable classes (see [Designing Panel Architecture](designing-panel-architecture.md)).

## Contents

- [References](#references) — iterative development, Material UI, plotting, custom components, Playwright testing, app structure & scaling, review
- [Viewer Class Pattern](#viewer-class-pattern)
- [Widgets and Extensions](#widgets-and-extensions)
- [Templates and Layouts](#templates-and-layouts)
- [Serving Workflow](#serving-workflow)
- [Performance](#performance)

## References

Read these for specialized topics. Each is a standalone document you can load with the `view` tool.

- [Iterating on Panel Apps](iterating-on-panel-apps.md) — serve with logging, screenshot with Playwright, review and debug agentic loop
- [Designing Panel Architecture](designing-panel-architecture.md) — composing larger apps (State/DataStore/View/App, `param.ClassSelector`, cross-object `@param.depends`, `from_data`, `pn.rx`) and runtime/scale (per-session model, `pn.state` scheduling, generator streaming, caching tiers, `nthreads`, profiling)
- [Building Custom Components](building-custom-components.md) — Python-vs-JS decision ladder; pure-Python `Viewer`/`PyComponent`; JSComponent, ReactComponent, AnyWidgetComponent, MaterialUIComponent; CDN selection, event handling, state sync lifecycle
- [Using Material UI](using-material-ui.md) — building pmui apps (`pmui.Page`, `Container`/`Grid` layouts, centering, component gotchas) and theming (`theme_config` palette, typography, icons, brand assets, chart theming)
- [Migrating to Material UI](migrating-to-material-ui.md) — converting an existing plain-Panel app to pmui: template→Page, widget swaps, pane/interaction upgrades, what to leave alone
- [Converting Designs to Material UI](converting-designs-to-material-ui.md) — workflow for turning a screenshot/design/React app into a pmui app: capture references, map to components, build component-first with mock data, assemble, theme last
- [Plotting in Panel](plotting-in-panel.md) — embedding plots from any library: HoloViews/hvPlot (DynamicMap zoom/pan, responsive sizing), Matplotlib, Plotly, ECharts, Bokeh toolbar tools
- [Using Tabulator](using-tabulator.md) — `add_filter` with widgets, checkbox selection, row content, function-based filtering
- [Using Pytest Playwright](using-pytest-playwright.md) — `serve_component`/`wait_until` utilities, JS↔Python sync tests, complete test patterns for custom components
- [Reviewing Panel Apps](reviewing-panel-apps.md) — anti-pattern checklist for code review: flickering, missing hold, watcher gaps, reactive-wiring priority, from_param super() ordering, mutation bugs
- [Troubleshooting Panel Apps](troubleshooting.md) — symptom→cause→fix for apps that serve but misbehave silently: init ordering, dead-app, blank Page, responsive/spinner issues, version & deprecation diagnosis

## Viewer Class Pattern

- Recreating panes or layouts inside `@param.depends` causes flickering. Create them once in `__init__`, bind to reactive content.
- **`super().__init__()` ordering matters, in two opposite directions.** Panes/placeholders an `on_init=True` watcher references must be created *before* `super().__init__(**params)` (else `AttributeError` during init). But `.from_param()` widgets must be created *after* it: made before super, a widget's value still syncs to its param, but `@param.depends`/`.watch()` callbacks never fire on widget changes — so dependent plots silently never update. This is the usual cause of a "widgets move but nothing updates" app. Rule of thumb: bare panes before `super()`, `from_param` widgets after.
- Use `pn.pane.Placeholder` when the content type varies (string → plot → widget). Swap with `.update()` or `.object =`.
- Implement `__panel__` to return the layout. When served, wrap in `pmui.Page` (see [Using Material UI](using-material-ui.md)); otherwise return the bare component.
- **Shared UI state**: Add a param (`disabled`, `loading`, `visible`) to a base class and bind widgets to it (e.g., `disabled=self.param.disabled`). Set once to update all widgets — useful for form submit, loading states, or toggling visibility.
- **Organize `__init__`**: Separate component instantiation from wiring (respecting the `super()` ordering rule above), then group `on_click`, `pn.bind`, and `.watch()` calls together. Makes it clear what exists vs. how it's connected.
- **Method naming**: `_on_*` for event handlers (`_on_click`, `_on_submit`), `_update_*` for watchers that sync state (`_update_view`, `_update_button_state`), `_sync_*` for bidirectional syncs.
- **Wizard/pipeline pattern**: For multi-step flows, see `examples/wizard.py` — `pmui.StepperMenu` driving navigation and per-step state (completed/error/active, `non_linear`), `pn.pane.Placeholder` step swapping, shared `disabled` state, `pn.io.hold()` batching, inline `pmui.Alert` validation, `pmui.Tooltip`, and `pmui.Page`.
- **KPI dashboard pattern**: For metric dashboards, see `examples/dashboard.py` — `pn.indicators.Trend` KPI cards, `pmui.Badge` selection counter, `pmui.SpeedDial` quick actions, `pmui.Alert` empty-state, `pmui.Tooltip` hints, `pmui.Grid` responsive layout, DynamicMap with trigger pattern, Tabulator `add_filter` + checkbox selection cross-filtering, `pn.bind(watch=True)` wiring, `param.DataFrame` as single source of truth, and `pmui.Page`.

```python
import hvplot.pandas  # noqa
import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True)

penguins = hvplot.sampledata.penguins("pandas").dropna()
species_list = sorted(penguins["species"].unique())

# ✅ Static panes, reactive content
class Dashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    def __init__(self, **params):
        # Panes referenced by an on_init=True watcher must exist BEFORE super()
        self._chart_pane = pn.pane.HoloViews(sizing_mode="stretch_width")
        super().__init__(**params)
        # from_param widgets must be created AFTER super() — before it, widget
        # changes update the param silently but never fire watchers (dead app).
        self._species_widget = pmui.CheckBoxGroup.from_param(self.param.species)
        with pn.config.set(sizing_mode="stretch_width"):
            self._sidebar = pmui.Column(self._species_widget)
            self._main = pmui.Column(self._summary, self._chart_pane)

    def _filtered(self):
        return penguins[penguins["species"].isin(self.species)]

    @param.depends("species")
    def _summary(self):
        return f"**{len(self._filtered())}** penguins selected"

    @param.depends("species", watch=True, on_init=True)
    def _update_chart(self):
        self._chart_pane.object = self._filtered().hvplot.scatter(
            x="bill_length_mm", y="bill_depth_mm", by="species",
        )

    def __panel__(self):
        if pn.state.served:
            return pmui.Page(
                title="Penguin Explorer",
                sidebar=[self._sidebar],
                main=[self._main],
            )
        return self._main

# ❌ Recreates layout on every change — causes flickering
class BadDashboard(pn.viewable.Viewer):
    species = param.ListSelector(default=species_list, objects=species_list)

    @param.depends("species")
    def view(self):
        filtered = penguins[penguins["species"].isin(self.species)]
        return pn.Column(
            pn.pane.Markdown(f"**{len(filtered)}** penguins selected"),
            pn.pane.HoloViews(filtered.hvplot.scatter(x="bill_length_mm", y="bill_depth_mm", by="species")),
        )
```

## Widgets and Extensions

- Call `pn.extension(throttled=True)` with any needed JS extensions (`"tabulator"`, `"plotly"`). Never add `"bokeh"`.
- `.from_param()` auto-creates the right widget type from a parameter — syncs value, bounds, and objects. Create `from_param` widgets *after* `super().__init__()` (button groups included) or their `@param.depends`/watchers won't fire — see the [ordering rule](#viewer-class-pattern) and the [review checklist](reviewing-panel-apps.md#from_param-widgets-created-before-super).
- Prefer `pn.bind(self._update, widget1.param.value, widget2.param.value, watch=True)` over lambda-based `.param.watch()` for wiring multiple widgets to a single update method.
- Default to `sizing_mode="stretch_width"` via `pn.config.set`.

## Templates and Layouts

For new apps, use `pmui.Page` from panel-material-ui (see [Using Material UI](using-material-ui.md) for Page rules, sidebar order, and layout helpers). If an existing codebase already uses a different template (e.g. `FastListTemplate`), keep it rather than migrating. Use `FlexBox`/`GridSpec`/`GridBox` for complex layouts, and set `min_*`/`max_*` sizing to prevent layout collapse.

## Serving Workflow

- Keep a dev server running: `panel serve app.py --dev --show`. Don't restart after edits.
- Don't use `--autoreload` (legacy). Don't use `python app.py`.

## Performance

- Batch multiple updates into one redraw with `pn.io.hold()`; defer heavy components with `pn.extension(defer_load=True, loading_indicator=True)`; memoize expensive work with `@pn.cache`.
- For caching tiers, automatic threading, generator streaming, profiling, the loading-spinner pattern, and memory management, see [Designing Panel Architecture](designing-panel-architecture.md).

## Lookup

### Component Reference

Look up component docs at `https://panel.holoviz.org/reference/{section}/{Component}.html`

Sections: `panes`, `widgets`, `layouts`, `chat`, `global`, `indicators`, `templates`, `custom_components`

### Search

Search the web at `https://panel.holoviz.org/search.html?q=<topic>` for additional information.
