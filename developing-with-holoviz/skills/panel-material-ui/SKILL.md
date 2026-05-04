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
1. Import `panel_material_ui as pmui`. Don't add `"panel_material_ui"` or `"bokeh"` to `pn.extension()`. Don't set `design='material'`.
2. Use `pmui.Page` instead of `pn.template.FastListTemplate`.
3. Use new param names (`label`, `color`, `variant`) not legacy aliases (`name`, `button_type`, `button_style`).
4. Quick preview with `python app.py` + `.show()` works for pmui (unlike standard Panel).

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
1. Title goes in `Page.title` — don't repeat in `main`.
2. `Page.sidebar`, `Page.main`, `Page.header` require lists — not bare components or `list(layout)`.
3. Don't add `ThemeToggle` — built in.
4. `header` is only 100px — buttons, indicators, nav links only.
5. Add `margin=10` to outer `main` layouts so they stand out from sidebar.

```python
# ✅ Lists
pmui.Page(sidebar=[widget1, widget2], main=[content])

# ❌ Bare component — fails silently
pmui.Page(sidebar=widget1, main=content)
```

## Styling Layers

Notes:
1. Preference order: `theme_config` → `sx` → `styles` → `stylesheets`.
2. `theme_config`: app-wide palette, typography, shape. Define on top-level container; children inherit. Use `"light"`/`"dark"` keys.
3. `sx`: local Mui styling. Selectors like `& .MuiSlider-thumb`, `.mui-dark`/`.mui-light` for mode overrides.
4. `styles`: outer Panel wrapper only — spacing, borders, backgrounds.
5. `stylesheets`: last resort for classic Panel internals.

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

## Component Gotchas

Notes:
1. `Grid`: use `spacing=2`+. `ncols` doesn't exist.
2. `Column`/`Row`: use `size`, not `xs`/`sm`/`md`. Set spacing via `sx`, not `spacing` param.
3. List layouts take positional args: `pmui.Row(child1, child2)`, not `pmui.Row([child1, child2])`.
4. `Paper`: set `pmui.Paper.param.margin.default = 10`.
5. `Switch`: add `margin=(10, 20)` in sidebars. Sliders: margin left/right.
6. Sidebar widgets need `sizing_mode="stretch_width"` explicitly, or wrap sidebar construction with `pn.config.set(sizing_mode="stretch_width")`.
7. `Card`: prefer `Paper`. Set `collapsible=False` unless needed.
8. `Tabulator`: use `"materialize"` theme, not `"material"` (doesn't exist).
9. `Box` → use `Column`. `TextField` → use `TextInput`. Neither exists.

## Icons

Notes:
1. Prefer Material UI icons over emojis.
2. Standalone decorative icons: use `Typography`, not `IconButton`.
3. Widget labels/options: embed with `:material/...:` token syntax.

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