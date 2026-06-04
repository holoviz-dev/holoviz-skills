# Branding Material UI

Customize panel-material-ui apps with consistent theming, colors, typography, and brand assets.

## Contents

- [Styling Layers](#styling-layers)
- [Palette](#palette)
- [Typography](#typography)
- [Shape](#shape)
- [Component Overrides](#component-overrides)
- [Icons](#icons)
- [Brand Assets](#brand-assets)
- [Chart Theming](#chart-theming)

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

## Complete Example

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

Full theming references as clean markdown — fetch directly:

- Palette tokens, `contrastThreshold`, `tonalOffset`: `https://panel-material-ui.holoviz.org/markdown/how_to/customize_palette.md`
- Typography: `…/markdown/how_to/customize_typography.md`
- Per-component theming (`components` key): `…/markdown/how_to/theme_components.md`
- Dark mode: `…/markdown/how_to/control_dark_mode.md`
- Theme-aware plots (Bokeh/hvPlot/HoloViews/Plotly): `…/markdown/how_to/theme_plotting_libraries.md`
- Material icons: `…/markdown/how_to/using_mui_icons.md`

Full guide index: `https://panel-material-ui.holoviz.org/markdown/how_to/index.md`.
