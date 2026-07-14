# Using Material UI

Build and theme panel-material-ui (pmui) apps: layout, `Page` structure, and component gotchas, plus theming — palette, typography, icons, brand assets, and chart theming. For converting an *existing* plain-Panel app, see [Migrating to Material UI](migrating-to-material-ui.md).

## Contents

Building:

- [Lookup](#lookup) — where to fetch pmui docs as markdown
- [Key Differences from Panel](#key-differences-from-panel)
- [Page](#page) — incl. [header / AppBar color](#page-header--appbar-color)
- [Layouts](#layouts)
- [Component Gotchas](#component-gotchas)

Theming:

- [Styling Layers](#styling-layers)
- [Palette](#palette)
- [Typography](#typography)
- [Shape](#shape)
- [Component Overrides](#component-overrides)
- [Icons](#icons)
- [Brand Assets](#brand-assets)
- [Chart Theming](#chart-theming)
- [Complete Themed Example](#complete-themed-example)
- [Deep Dives](#deep-dives) — full theming guides as markdown

## Lookup

Fetch pmui docs as markdown, not HTML: prefix any pmui doc path with `/markdown/` and change `.html`/`.ipynb` → `.md` (also for links found inside pages). If the result is empty, the page moved — use the index.

Base: `https://panel-material-ui.holoviz.org/markdown/` — append the endpoints below.

- **Doc map / index**: `https://panel-material-ui.holoviz.org/llms.txt` (site root, *not* under `markdown/`)
- **Component**: `reference/{section}/{Component}.md`
  Sections: `widgets`, `menus`, `layouts`, `panes`, `wrappers`, `page`, `chat`, `indicators`, `global`
- **Section index** (lists every component): `reference/{section}/index.md`
- **How-to guides**: `how_to/{guide}.md` (index: `how_to/index.md`)
- **Search**: web-search the topic, then convert the `.html` hit to its `/markdown/…​.md` URL.

## Key Differences from Panel

- Import `panel_material_ui as pmui`. Don't add `"panel_material_ui"` or `"bokeh"` to `pn.extension()`. Don't set `design='material'`.
- Prefer `pmui.Column`/`Row`/`Grid`/`Container` over `pn.*` equivalents — they support `spacing`, breakpoints, and theme inheritance. Fall back to `pn.*` only when no pmui equivalent exists (e.g. `pn.pane.HoloViews`). If an existing app already uses `pn.*` layouts, keep them rather than migrating.
- Use `pmui.Page` instead of `pn.template.FastListTemplate`.
- Use new param names (`label`, `color`, `variant`) not legacy aliases (`name`, `button_type`, `button_style`).
- Quick preview with `python app.py` + `.show()` works for pmui (unlike standard Panel).
- **Widget from a Param:** pmui has no auto `Param` pane, so pick the widget class yourself with `pmui.<Widget>.from_param(obj.param.x)` (or `pn.Param(obj, widgets={"x": {"type": pmui.Select}})` to override auto-generated types). The Param-type → widget baseline matches Panel's own defaults ([Param pane reference](https://panel.holoviz.org/reference/panes/Param.html)); the pmui-specific things to know: `param.Boolean` → `pmui.Switch` (Panel defaults to `Checkbox`), and `param.Array` / `param.DataFrame` have **no** pmui widget — keep `pn.widgets.ArrayInput` / `pn.widgets.Tabulator`.

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

- Title goes in `Page.title` — don't repeat in `main`.
- `Page.sidebar`, `Page.main`, `Page.header` require lists — not bare components or `list(layout)`.
- Don't add `ThemeToggle` — built in.
- `header` is only 100px — buttons, indicators, nav links only.
- Add `margin=10` to outer `main` layouts so they stand out from sidebar.
- Only use a sidebar when there are multiple control widgets. For a single selector, use inline `RadioButtonGroup` or `Select` in the main area with `pmui.Container` — avoids wasting viewport on a near-empty sidebar.
- Sidebar order: logo → description → widgets → docs.
- **Page not rendering (no header/sidebar)**: if `__panel__` returns the `Page` only under `if pn.state.served:`, that guard can evaluate `False` when `__panel__` runs, silently giving you the bare fallback layout with no top bar. For an app that is always served, build the `Page` once in `__init__` and return it unconditionally from `__panel__`.

```python
# ✅ Lists
pmui.Page(sidebar=[widget1, widget2], main=[content])

# ❌ Bare component — fails silently
pmui.Page(sidebar=widget1, main=content)
```

### Page header / AppBar color

The `Page` header is an MUI `AppBar color="primary"`. If `theme_config` sets no
`palette.primary.main`, it falls back to a hardcoded blue (`#0072b5`) with a white title — which
clashes with a dark app. Either set `palette.primary.main`, or override the header directly via the
`.header` class (use this when you want the header a different color from the brand primary, e.g. a
dark panel tone):

```python
pmui.Page(
    sx={"& .header": {
        "backgroundColor": "#14141b",  # match the app's panel color
        "backgroundImage": "none",
        "boxShadow": "none",
    }},
    ...
)
```

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

### Centering in Page

The `pmui.Page` main area does not support CSS flexbox centering. Use margins instead:

- **Horizontal**: wrap content in `pmui.Container(width_option="sm")` for narrow centered cards
- **Vertical**: use integer tuple margins like `margin=(100, 0, 0, 0)` for top spacing. `margin="auto"` and `pn.Spacer()` don't work for vertical centering in Page

```python
pmui.Page(
    main=[
        pmui.Container(
            pmui.Column(
                pmui.Paper(content, sx={"p": 5}),
                sizing_mode="stretch_width",
                margin=(100, 0, 0, 0),  # Push down from top
            ),
            width_option="sm",  # Center horizontally with narrow width
        )
    ],
)
```

## Component Gotchas

### Spacing and Alignment

- `pn.layout.HSpacer()` pushes items left/right in a Row
- `pn.layout.VSpacer()` pushes items top/bottom in a Column
- Always set `sizing_mode` on components unless intentionally fixed-size; fixed default widths are why widgets "aren't responsive".
- Use `margin` to prevent widgets touching container edges (default margins often suffice). Default margins are inconsistent (most `10`; `Typography` `(5,10)`; `Chip`/`Avatar`/containers `0`), so loose text/buttons won't align with margin-0 `Grid`/`Paper` blocks — pick one baseline.
- Align a whole body: make each section an item of ONE `Grid(container=True, spacing=2)` with children `margin=0` — shared padding aligns them and `spacing` makes the gaps (also stops cards touching):

  ```python
  pmui.Grid(pmui.Grid(title, size={"xs": 12}),
            pmui.Grid(card, size={"xs": 12, "sm": 6, "md": 3}), ...,
            container=True, spacing=2, sizing_mode="stretch_width")
  ```

- Slider thumb hits the edge → add horizontal margin, e.g. `margin=(10, 20)`.
- Mixed-height rows: `align="center"`; set gaps with `sx={"gap": "12px"}`, not per-item margins.

### Layouts

- `Grid`: use `spacing=2`+. `ncols` doesn't exist.
- `Column`/`Row`: use `size`, not `xs`/`sm`/`md`. Set spacing via `sx`, not `spacing` param.
- List layouts take positional args: `pmui.Row(a, b)`, not `pmui.Row([a, b])`.

### Components

- `Card`: prefer `Paper`. Set `collapsible=False` unless needed.
- `Tabulator`: use `"materialize"` theme, not `"material"`.
- `Box` → `Column`, `TextField` → `TextInput` (neither exists).
- `Chip`: use `label=`, not `object=` (deprecated). Chips default to `margin=10`, which blows out tight stacked layouts — set `margin=0` when packing several together. Translucent-pill look: `sx={"color": c, "backgroundColor": f"{c}22"}`.
- `Accordion` header text: the title renders as a Typography *inside* the summary, so a rule on `.MuiAccordionSummary-root` won't reach it. Target the content to restyle the label: `sx={"& .MuiAccordionSummary-content *": {"fontSize": "13px", "color": "#6d5cff"}}`.
- `CheckButtonGroup`/`RadioButtonGroup` styling: in sidebars use `orientation="vertical"`, `color="primary"`, `variant="outlined"`.
- Button groups (`RadioButtonGroup`, `CheckButtonGroup`) work with `.from_param()` like any widget — just create them **after** `super().__init__()`; built before it, their value syncs but `@param.depends`/watchers won't fire (the [ordering rule](SKILL.md#viewer-class-pattern); before/after fix in [Troubleshooting](troubleshooting.md#widgets-change-but-nothing-updates-init-ordering)).
- `Rating` (and other icon widgets): stretch to fill their container under the default `sizing_mode="stretch_width"`, rendering enormous. Pin them: `pmui.Rating(end=5, size="small", width=170, sizing_mode="fixed")`.
- `Dialog`: for secondary detail that would crowd the page (or overflow the narrow `Page` contextbar), use a dialog and toggle `.open`. `close_on_click=True` dismisses on backdrop click:

  ```python
  self._details = pmui.Dialog(content, title="Details",
                              width_option="md", open=False, close_on_click=True)
  # open from a button: self._details.open = True
  ```

## Styling Layers

| Layer | Scope | Use |
|-------|-------|-----|
| `theme_config` | Global (flows to children) | App-wide palette, typography, shape, component defaults |
| `sx` | Local instance | One-off styling, nested selectors, dark/light mode overrides |
| `styles` | Local instance | Outer container box (spacing, borders, backgrounds) |
| `stylesheets` | Local instance | Classic Panel internals via CSS selectors |

### sx Examples

```python
# Basic styling
pmui.Button(label="Custom", sx={"color": "white", "backgroundColor": "black"})

# Hover states
pmui.Button(sx={"&:hover": {"backgroundColor": "gray"}})

# Dark/light mode overrides
pmui.Button(sx={"&.mui-dark:hover": {"backgroundColor": "orange"}})

# Target nested MUI parts
pmui.FloatSlider(sx={"& .MuiSlider-thumb": {"borderRadius": 0}})
```

## Palette

Each color category has four tokens: `main`, `light`, `dark`, `contrastText`. Only `main` is required; others auto-compute.

```python
theme_config = {
    "palette": {
        "primary": {"main": "#6200ea"},
        "secondary": {"main": "#03dac6"},
        "error": {"main": "#b00020"},
    }
}
```

### Token Reference

| Token | Use |
|-------|-----|
| `primary.main` | Primary brand color |
| `primary.contrastText` | Text on primary background |
| `text.primary` | Main text color |
| `text.secondary` | Muted/secondary text |
| `background.default` | Page background |
| `background.paper` | Card/paper background |

### Accessibility

```python
theme_config = {
    "palette": {
        "contrastThreshold": 4.5,  # WCAG 2.1 compliance (default: 3)
        "tonalOffset": 0.2,        # Light/dark variant shift
        "primary": {"main": "#3f50b5"},
    }
}
```

## Typography

```python
theme_config = {
    "typography": {
        "fontFamily": "Montserrat, Helvetica Neue, Arial, sans-serif",
        "fontSize": 14,  # Base size in px
        "h1": {"fontSize": "2.5rem", "fontWeight": 700},
        "body1": {"fontWeight": 500},
        "button": {"fontStyle": "italic"},
    }
}
```

Variants: `h1`-`h6`, `subtitle1`, `subtitle2`, `body1`, `body2`, `button`, `caption`, `overline`.

### Responsive Typography

```python
pmui.Typography("Responsive", sx={
    "fontSize": "1.2rem",
    "@media (min-width: 600px)": {"fontSize": "1.5rem"},
    "@media (min-width: 900px)": {"fontSize": "2.4rem"},
})
```

## Shape

```python
theme_config = {
    "shape": {"borderRadius": 8}  # Default corner radius for all components
}
```

## Component Overrides

Override defaults for all instances of a component type:

```python
theme_config = {
    "components": {
        "MuiButton": {
            "defaultProps": {"disableRipple": True},
            "styleOverrides": {"root": {"fontSize": "1rem"}},
        },
        "MuiPaper": {
            "styleOverrides": {"root": {"padding": "16px"}},
        },
    }
}
```

### Variant-Based Overrides

```python
theme_config = {
    "components": {
        "MuiCard": {
            "styleOverrides": {
                "root": {
                    "variants": [{
                        "props": {"variant": "outlined"},
                        "style": {"borderWidth": "3px"},
                    }]
                }
            }
        }
    }
}
```

## Icons

Use Material Icons from [fonts.google.com/icons](https://fonts.google.com/icons?icon.set=Material+Icons).

### Icon Parameter

Buttons and some widgets accept `icon` directly:

```python
pmui.Button(label="Save", icon="save")
pmui.Button(label="Delete", icon="delete_outlined")  # Outlined variant
pmui.ButtonIcon(icon="settings")
```

### Token Syntax in Labels

Embed icons in text with `:material/icon_name:`:

```python
pmui.Select(options=["Zoom :material/zoom:", "Pan :material/pan_tool:"])
pmui.Button(label="Warning :material/warning@color=warning:")
```

Token options: `@size=large`, `@color=warning`, `@variant=outlined`.

### HTML/Markdown

```python
pmui.Typography('<span class="material-icons">lightbulb</span> Idea')
```

## Brand Assets

### Logo and Favicon

```python
pmui.Page.param.logo.default = "/path/to/logo.png"
pmui.Page.favicon = "/path/to/favicon.ico"
pmui.Page.meta.name = "My App"
```

### Custom CSS

```python
pmui.Page.config.raw_css.append("body { font-family: Montserrat; }")
pmui.Page.config.css_files.append(
    "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap"
)
```

### Component Defaults

```python
pn.pane.Image.stylesheets = ["img {border-radius: 8px}"]
pn.widgets.Tabulator.param.theme.default = "materialize"
pmui.Button.param.disable_elevation.default = True
```

## Chart Theming

Plots auto-theme when using `pmui.Page` or `pmui.ThemeToggle`.

### Categorical Palette

```python
primary = "#6200ea"
colors = pmui.theme.generate_palette(primary)

df.hvplot.scatter(x="x", y="y", color="category", cmap=colors)
```

### Continuous Colormap

```python
cmap = pmui.theme.linear_gradient("#ffffff", "#6200ea", n=256)
```

## Complete Themed Example

```python
import panel as pn
import panel_material_ui as pmui

pn.extension()

THEME = {
    "light": {
        "palette": {
            "primary": {"main": "#4099da"},
            "secondary": {"main": "#644c76"},
        },
        "typography": {
            "fontFamily": "Montserrat, sans-serif",
            "fontSize": 14,
        },
        "shape": {"borderRadius": 8},
    },
    "dark": {
        "palette": {
            "primary": {"main": "#64b5f6"},
            "secondary": {"main": "#9575cd"},
        },
        "typography": {
            "fontFamily": "Montserrat, sans-serif",
            "fontSize": 14,
        },
        "shape": {"borderRadius": 8},
    },
}

pmui.Page(
    title="Branded App",
    theme_config=THEME,
    sidebar=[pmui.Button(label="Action", icon="bolt", color="primary")],
    main=[pmui.Typography("Welcome", variant="h4")],
).servable()
```

## Deep Dives

Full theming guides as markdown. Base: `https://panel-material-ui.holoviz.org/markdown/how_to/` — append:

- `customize_palette.md` — palette tokens, `contrastThreshold`, `tonalOffset`
- `customize_typography.md` — typography
- `theme_components.md` — per-component theming (`components` key)
- `control_dark_mode.md` — dark mode
- `theme_plotting_libraries.md` — theme-aware plots (Bokeh/hvPlot/HoloViews/Plotly)
- `using_mui_icons.md` — Material icons
- `index.md` — full guide index
