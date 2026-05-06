---
name: panel-material-ui
description: Build Material UI themed Panel apps with panel-material-ui (pmui). Use when the user wants Material Design components, MUI theming (palette, sx, theme_config), or the pmui.Page template. Covers only where pmui diverges from standard Panel.
metadata:
  version: "1.0.0"
  author: holoviz
---

# Using Panel Material UI effectively

## Key Differences from Panel

Notes:
- Import `panel_material_ui as pmui`. Don't add `"panel_material_ui"` or `"bokeh"` to `pn.extension()`. Don't set `design='material'`.
- Prefer `pmui.Column`/`Row`/`Grid`/`Container` over `pn.*` equivalents — they support `spacing`, breakpoints, and theme inheritance. Fall back to `pn.*` only when no pmui equivalent exists (e.g. `pn.pane.HoloViews`). If an existing app already uses `pn.*` layouts, keep them rather than migrating.
- Use `pmui.Page` instead of `pn.template.FastListTemplate`.
- Use new param names (`label`, `color`, `variant`) not legacy aliases (`name`, `button_type`, `button_style`).
- Quick preview with `python app.py` + `.show()` works for pmui (unlike standard Panel).

```python
import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True)

class MyApp(pn.viewable.Viewer):
    value = param.Integer(default=5, bounds=(0, 10))

    def __init__(self, **params):
        super().__init__(**params)
        with pn.config.set(sizing_mode="stretch_width"):
            self._slider = pmui.IntSlider.from_param(self.param.value, margin=(10, 20))
            self._output = pmui.Column(self._display)

    @param.depends("value")
    def _display(self):
        return f"Value: {self.value}"

    def __panel__(self):
        if pn.state.served:
            return pmui.Page(
                title="My App",
                sidebar=[self._slider],
                main=[self._output],
            )
        return pmui.Row(pmui.Column(self._slider, max_width=300), self._output)
```

## Page

Notes:
- Title goes in `Page.title` — don't repeat in `main`.
- `Page.sidebar`, `Page.main`, `Page.header` require lists — not bare components or `list(layout)`.
- Don't add `ThemeToggle` — built in.
- `header` is only 100px — buttons, indicators, nav links only.
- Add `margin=10` to outer `main` layouts so they stand out from sidebar.
- Only use a sidebar when there are multiple control widgets. For a single selector, use inline `RadioButtonGroup` or `Select` in the main area with `pmui.Container` — avoids wasting viewport on a near-empty sidebar.

```python
# ✅ Lists
pmui.Page(sidebar=[widget1, widget2], main=[content])

# ❌ Bare component — fails silently
pmui.Page(sidebar=widget1, main=content)
```

## Styling Layers

Notes:
- Preference order: `theme_config` → `sx` → `styles` → `stylesheets`.
- `theme_config`: app-wide palette, typography, shape. Define on top-level container; children inherit. Use `"light"`/`"dark"` keys.
- `sx`: local Mui styling. Selectors like `& .MuiSlider-thumb`, `.mui-dark`/`.mui-light` for mode overrides.
- `styles`: outer Panel wrapper only — spacing, borders, backgrounds.
- `stylesheets`: last resort for classic Panel internals.

```python
app_theme = {
    "light": {
        "palette": {"primary": {"main": "#6a1b9a"}},
        "shape": {"borderRadius": 12},
    },
    "dark": {
        "palette": {"primary": {"main": "#9575cd"}},
        "shape": {"borderRadius": 12},
    },
}

pmui.Page(
    main=[
        pmui.Paper(
            pmui.Button("Submit", color="primary", sx={"fontWeight": 700}),
            styles={"padding": "8px"},
        )
    ],
    theme_config=app_theme,
)
```

## Chart Theming

Notes:
- pmui auto-themes Bokeh/hvPlot/HoloViews when using `Page` or `ThemeToggle` — respects primary color, font, and dark/light mode.
- For cleaner chart chrome, set `hv.renderer("bokeh").theme = "light_minimal"` at module level.
- `pmui.theme.generate_palette(primary_color)` for categorical palettes; `pmui.theme.linear_gradient(start, end, n=256)` for continuous colormaps.
- Define a `PRIMARY` color constant and reuse across chart `color=`, KPI `styles`, and `theme_config` for cohesion.

## Layouts

Notes:
- `pmui.Container(width_option="lg")` clamps content max width — prevents wide-screen stretching.
- `pmui.Grid` with `size=` breakpoints for responsive multi-column layouts. Nest items inside `Grid(container=True)`. KPI cards: `size={"xs": 6, "md": 3}`. Side-by-side charts: `size={"xs": 12, "md": 6}`.
- `size="grow"` for auto-sized items.
- Set `sizing_mode="stretch_width"` on children inside `Grid` items so they fill the cell.

```python
# 2-column responsive layout
pmui.Grid(
    pmui.Grid(left_card, size={"xs": 12, "md": 6}),
    pmui.Grid(right_card, size={"xs": 12, "md": 6}),
    container=True, spacing=2,
)

# Width-clamped page content
pmui.Container(pmui.Column(...), width_option="lg")
```

## Component Gotchas

Notes:
- `Grid`: use `spacing=2`+. `ncols` doesn't exist.
- `Column`/`Row`: use `size`, not `xs`/`sm`/`md`. Set spacing via `sx`, not `spacing` param.
- List layouts take positional args: `pmui.Row(child1, child2)`, not `pmui.Row([child1, child2])`.
- `Paper`: set `pmui.Paper.param.margin.default = 10`.
- `Switch`: add `margin=(10, 20)` in sidebars. Sliders: margin left/right.
- Sidebar widgets need `sizing_mode="stretch_width"` explicitly, or wrap sidebar construction with `pn.config.set(sizing_mode="stretch_width")`.
- `Card`: prefer `Paper`. Set `collapsible=False` unless needed.
- `Tabulator`: use `"materialize"` theme, not `"material"` (doesn't exist).
- `Box` → use `Column`. `TextField` → use `TextInput`. Neither exists.

## Icons

Notes:
- Prefer Material UI icons over emojis.
- Standalone decorative icons: use `Typography`, not `IconButton`.
- Widget labels/options: embed with `:material/...:` token syntax.

```python
pmui.Typography(
    '<span class="material-icons" style="font-size: 4rem;">lightbulb</span>',
    sizing_mode="fixed", width=60, height=60, sx={"color": "primary.main"},
)

pmui.Select(
    label="Mode",
    options=["Zoom :material/zoom:", "Explore :material/explore@size=large,color=warning:"],
)
```