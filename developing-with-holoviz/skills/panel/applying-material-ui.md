# Applying Material UI

Layout and structure for panel-material-ui apps. For theming (palette, typography, icons, brand assets), see [Branding Material UI](branding-material-ui.md).

## Contents

- [Key Differences from Panel](#key-differences-from-panel)
- [Page](#page)
- [Layouts](#layouts)
- [Component Gotchas](#component-gotchas)
- [Lookup](#lookup)

## Key Differences from Panel

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
- Always set `sizing_mode` on components unless intentionally fixed-size
- Use `margin` to prevent widgets touching container edges (default margins often suffice)

### Layouts

- `Grid`: use `spacing=2`+. `ncols` doesn't exist.
- `Column`/`Row`: use `size`, not `xs`/`sm`/`md`. Set spacing via `sx`, not `spacing` param.
- List layouts take positional args: `pmui.Row(a, b)`, not `pmui.Row([a, b])`.

### Components

- `Card`: prefer `Paper`. Set `collapsible=False` unless needed.
- `Tabulator`: use `"materialize"` theme, not `"material"`.
- `Box` → `Column`, `TextField` → `TextInput` (neither exists).

## Lookup

### Component Reference

Look up component docs at `https://panel-material-ui.holoviz.org/reference/{section}/{Component}.html`

Sections: `widgets`, `menus`, `layouts`, `panes`, `page`, `chat`, `indicators`, `global`

### Search

Search the web at `https://panel-material-ui.holoviz.org/search.html?q=<topic>` for pmui docs.