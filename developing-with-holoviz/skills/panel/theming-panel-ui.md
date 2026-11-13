# Theming Panel UI

Theme a `panel.ui` app: the `theme_config` palette, typography, web fonts, shape, component overrides, icons, brand assets, and charts that match. For layout, `Page` and component gotchas, see [Using Panel UI](using-panel-ui.md), whose [Lookup](using-panel-ui.md#lookup) section says where to find `panel.ui` documentation.

## Contents

- [Styling Layers](#styling-layers)
- [Palette](#palette)
- [Typography](#typography)
- [Web Fonts](#web-fonts) — why a webfont silently doesn't load, and how to verify
- [Shape](#shape)
- [Component Overrides](#component-overrides)
- [Icons](#icons)
- [Brand Assets](#brand-assets)
- [Chart Theming](#chart-theming) — incl. [plot fonts](#plot-fonts-bokeh-inherits-nothing)
- [Complete Themed Example](#complete-themed-example)
- [Deep Dives](#deep-dives) — theming API guidance

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
pn.ui.Button(label="Custom", sx={"color": "white", "backgroundColor": "black"})

# Hover states
pn.ui.Button(sx={"&:hover": {"backgroundColor": "gray"}})

# Dark/light mode overrides: the mui-dark class sits on an ancestor, not the styled root
pn.ui.Button(sx={".mui-dark &:hover": {"backgroundColor": "orange"}})

# Target nested MUI parts
pn.ui.FloatSlider(sx={"& .MuiSlider-thumb": {"borderRadius": 0}})
```

## Palette

Each color category has four tokens: `main`, `light`, `dark`, `contrastText`. Only `main` is required; others auto-compute. Colors must be hex, `rgb()` or `hsl()` strings: MUI's color parser throws on CSS names like `"teal"` and the Page fails to render.

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

Declare the whole type scale once in `theme_config["typography"]`, in **rem**, and reference
it by variant name. Don't scatter `font-size` px into `sx` or hand-written HTML.

```python
SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

TYPOGRAPHY = {
    "fontFamily": SANS,
    "fontSize": 14,                  # base, in px; everything else in rem
    "h6": {"fontSize": "1.05rem", "fontWeight": 600},
    "caption": {"fontSize": "0.78rem", "lineHeight": 1.6},
    "overline": {"fontSize": "0.68rem", "fontWeight": 600, "letterSpacing": "0.09em"},
    # Custom variants are allowed alongside the built-in thirteen.
    "kpi": {"fontFamily": MONO, "fontSize": "1.6rem", "fontWeight": 600,
            "fontVariantNumeric": "tabular-nums", "whiteSpace": "nowrap"},
}
pn.ui.Typography(f"{value:,.0f}", variant="kpi")
```

- **rem, never px or pt.** MUI sizes in rem so a reader who raises their browser's default
  font size scales the whole app; hardcoded px ignores them, and `pt` is a print unit that
  has no business here. Keys use camelCase (`fontVariantNumeric`), not CSS hyphens.
- **Custom variants make mono semantic.** Adding a `kpi`/`data` variant says "this is a
  machine reading" once, instead of repeating `font-family: MONO` inline. Keep mono for
  measured values, IDs and timestamps only — putting it on *labels* and prose spends the
  signal and makes the page read like a terminal.
- **Mono is wider per character.** A nine-digit figure at 1.9rem wraps mid-number
  (`3,350,6 / 55`) inside a `Grid` card and takes that card's height with it. Add
  `"whiteSpace": "nowrap"` to any numeric variant, and `sx={"height": "100%"}` plus a
  `minHeight` on sibling cards so one two-line label can't unlevel the row.
- **`overline` uppercases and tracks out**, so the same words need noticeably more width
  than they did at `caption` size — re-check any `width=` you set for a label.

### Variants

`h1`–`h6`, `subtitle1/2`, `body1/2`, `button`, `caption`, `overline`, plus any custom key
you add. Set `"h3": None` to disable one.

## Web Fonts

**`theme_config["fontFamily"]` only *selects* a family — it never *delivers* one.** Naming
`"IBM Plex Sans, sans-serif"` in a theme is not loading it, and CSS font fallback is silent:
the page renders in the fallback and looks entirely deliberate. This is the single easiest
way to ship a "custom typography" app that has no custom typography at all.

**Verify before believing it.** Render the target family next to a control that is certain to
exist and compare the letterforms:

```python
pn.pane.HTML("""
<div style="font-size:30px">
  <div style="font-family:'IBM Plex Sans',sans-serif">Plex Sans — Rag 138</div>
  <div style="font-family:Helvetica,Arial,sans-serif">Helvetica — Rag 138</div>
</div>""")
```

If the two lines are identical, the font did not load. (`document.fonts.check()` is the other
check, but a `<script>` in a Panel pane runs inside a shadow root, so `getElementById`
against the document won't find your target.)

Mechanisms that were tested and did **not** deliver a Google Font into a `pn.ui.Page`:
`pn.ui.Page.config.css_files.append(url)`, `pn.extension(css_files=[url])`, per-component
`stylesheets=[url]`, and `pn.config.raw_css.append("@import url(...)")`. Two of those cannot
work even in principle: Panel renders panes into **shadow roots** and `@font-face` is
document-scoped, and an appended `@import` is ignored unless it is the *first* rule in its
stylesheet.

**So prefer system stacks.** For a dashboard the design work is done by the *contrast*
between a sans for prose and a mono for data — not by one specific typeface. A system stack
delivers that with no network request, no flash of unstyled text, and no chance that a
customer's proxy blocks `fonts.googleapis.com` mid-demo. If a brand face is genuinely
required, self-host it and confirm with the specimen test above rather than assuming.

### Responsive Typography

```python
pn.ui.Typography("Responsive", sx={
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
pn.ui.Button(label="Save", icon="save")
pn.ui.Button(label="Delete", icon="delete_outlined")  # Outlined variant
pn.ui.IconButton(icon="settings")
```

### Token Syntax in Labels

Embed icons in text with `:material/icon_name:`:

```python
pn.ui.Select(options=["Zoom :material/zoom:", "Pan :material/pan_tool:"])
pn.ui.Button(label="Warning :material/warning@color=warning:")
```

Token options: `@size=large`, `@color=warning`, `@variant=outlined`.

### HTML/Markdown

```python
pn.ui.Typography('<span class="material-icons">lightbulb</span> Idea')
```

## Brand Assets

### Logo and Favicon

```python
pn.ui.Page.param.logo.default = "/path/to/logo.png"
pn.ui.Page.favicon = "/path/to/favicon.ico"
pn.ui.Page(meta_name="My App")

# Kiosk / wall-screen dashboard: fixed dark theme, no toggle, reload every 2s.
# theme= and meta_refresh= are constructor aliases for dark_theme and meta=Meta(refresh=...).
pn.ui.Page(title="Monitor", main=[...], theme="dark", theme_toggle=False, meta_refresh="2")
```

### Custom CSS

```python
pn.ui.Page.config.raw_css.append("body { font-family: Montserrat; }")
```

For loading a webfont, see [Web Fonts](#web-fonts) — `config.css_files` is **not** a
reliable way to do it.

### Component Defaults

```python
pn.pane.Image.stylesheets = ["img {border-radius: 8px}"]
pn.widgets.Tabulator.param.theme.default = "materialize"
pn.ui.Button.param.disable_elevation.default = True
```

## Chart Theming

Plots auto-theme when using `pn.ui.Page` or `pn.ui.ThemeToggle` — but that covers *colours*,
not type. See [Plot Fonts](#plot-fonts-bokeh-inherits-nothing).

### Categorical Palette

```python
primary = "#6200ea"
colors = pn.ui.theme.generate_palette(primary, n_colors=8)

df.hvplot.scatter(x="x", y="y", color="category", cmap=colors)
```

### Continuous Colormap

```python
cmap = pn.ui.theme.linear_gradient("#ffffff", "#6200ea", n=256)
```

### Plot Fonts: Bokeh inherits nothing

`theme_config["typography"]` reaches every MUI component and **no Bokeh figure**. Bokeh
draws text to a canvas, outside CSS cascade, so axis labels, tick labels, legends and
colorbars keep Bokeh's own default face while the rest of the page uses your stack. On a
dashboard that mixes prose and plots this reads as sloppiness rather than as a choice, and
nothing warns you. Push the stack on with a `hooks` function:

```python
SANS, MONO = "system-ui, sans-serif", "ui-monospace, monospace"

def font_hook(plot, element):
    fig = plot.state
    for axis in fig.axis:
        axis.axis_label_text_font = SANS      # words
        axis.major_label_text_font = MONO     # numbers
    for legend in fig.legend:
        legend.label_text_font = SANS
    for panel in fig.right:                   # colorbars live here
        if hasattr(panel, "major_label_text_font"):
            panel.major_label_text_font = MONO
            panel.title_text_font = SANS

plot.opts(hooks=[font_hook])
```

Keep the Bokeh stacks short (`"system-ui, sans-serif"`) — these become a canvas `font`
string, not a CSS declaration. `pn.widgets.Tabulator` is a Bokeh widget too, so its
`"materialize"` theme font is likewise independent of `theme_config`; closing that gap needs
CSS on the widget, not a theme key.

## Complete Themed Example

```python
import panel as pn

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

pn.ui.Page(
    title="Branded App",
    theme_config=THEME,
    sidebar=[pn.ui.Button(label="Action", icon="bolt", color="primary")],
    main=[pn.ui.Typography("Welcome", variant="h4")],
).servable()
```

## Deep Dives

`panel.ui` exposes the Material UI components through a stable Panel namespace. Its theming options use Material UI theme configuration: `palette`, `typography`, `shape`, and `components`. Consult the `Page`, `MaterialUIDesign`, and component API references for the installed Panel version rather than reaching into the implementation package.
