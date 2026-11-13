# Using Panel UI

`panel.ui` requires Panel 1.10 or later; on 1.9.x `pn.ui` does not exist. Check `pn.__version__` before writing `pn.ui` code, and upgrade Panel if it is older.

Build `panel.ui` apps: what differs from plain Panel, `Page` structure, layouts, and component gotchas. For palette, typography, fonts, icons, brand assets and chart colors, see [Theming Panel UI](theming-panel-ui.md); for converting an *existing* plain-Panel app, see [Migrating to Panel UI](migrating-to-panel-ui.md).

## Contents

- [Lookup](#lookup) — where to find `panel.ui` documentation
- [Key Differences from Panel](#key-differences-from-panel)
- [Page](#page) — incl. [header / AppBar color](#page-header-appbar-color)
- [Layouts](#layouts)
- [Component Gotchas](#component-gotchas)

## Lookup

Use Panel's API reference for `panel.ui`: `https://panel.holoviz.org/api/panel.ui.html`. Component documentation uses the same `https://panel.holoviz.org/reference/{section}/{Component}.html` convention as the rest of Panel. Search `https://panel.holoviz.org/search.html?q=<topic>` when the component location is unclear.

## Key Differences from Panel

- Import Panel once and reference components as `pn.ui.X`. Do not import the implementation package directly, add it or `"bokeh"` to `pn.extension()`, or set `design='material'`.
- Use `pn.ui.Column`/`pn.ui.Row` in `panel.ui` apps so the whole app reads from one namespace and every layout accepts `sx`. Native `pn.Column`/`pn.Row` still work and need no migration in existing code. The one exception is the layout *directly* wrapping a tile/geo plot, which must be native until the [tile plot renders blank](troubleshooting-panel-apps.md#tilemap-plot-renders-blank-inside-a-panelui-layout) bug is fixed.
- Fall back to `pn.*` whenever no `panel.ui` equivalent exists. If an existing app already uses `pn.*` layouts, keep them rather than migrating. Many `pn.ui` names are plain re-exports of the classic class (`pn.ui.Number is pn.indicators.Number`, likewise `pn.ui.Tabulator`, `pn.ui.Markdown`, `pn.ui.PNG`); others are distinct Material classes with different params (`pn.ui.ChatInterface`, `pn.ui.LoadingSpinner`, `pn.ui.Progress` uses `color`, not `bar_color`). Check `pn.ui.X.__module__` when it matters.
- Use `pn.ui.Page` instead of `pn.template.FastListTemplate`.
- Use new param names (`label`, `color`, `variant`) not legacy aliases (`name`, `button_type`, `button_style`).
- **Params don't generalize across components — don't infer one from a sibling widget.** `variant`, `color` and `size` each exist on only *some* components, and the allowed values differ where they do. Check before writing: `'variant' in pn.ui.X.param`, `pn.ui.X.param.variant.objects`, `sorted(pn.ui.X.param)`. The ones that actually bite are tabled in [Troubleshooting](troubleshooting-panel-apps.md#typeerror-unexpected-keyword-argument-panelui-params-arent-universal).
- Quick preview with `python app.py` + `.show()` works the same as for standard Panel. For iterating, prefer `panel serve app.py --dev --show` (see [Serving Workflow](SKILL.md#serving-workflow)).
- **Widget from a Param:** pick one widget with `pn.ui.<Widget>.from_param(obj.param.x)`, or generate a whole form with `pn.ui.Param(obj, parameters=[...], widgets={"x": pn.ui.Select})`, which builds Material widgets (`pn.Param` builds classic ones). `pn.ui.panel` and `pn.ui.HoloViews` likewise generate Material widgets for a DynamicMap's key dimensions. The Param-type → widget mapping matches Panel's own defaults ([Param pane reference](https://panel.holoviz.org/reference/panes/Param.html)): `param.Boolean` → `Checkbox` (use `pn.ui.Switch.from_param` if you want a switch), `param.DataFrame` → `Tabulator`, `param.Array` → `pn.ui.ArrayInput`.

```python
import param
import panel as pn

pn.extension(throttled=True)

class MyApp(pn.viewable.Viewer):
    value = param.Integer(default=5, bounds=(0, 10))

    def __init__(self, **params):
        super().__init__(**params)
        with pn.config.set(sizing_mode="stretch_width"):
            self._slider = pn.ui.IntSlider.from_param(self.param.value, margin=(10, 20))
            self._output = pn.ui.Column(self._display)
        # Build the Page once here — __panel__ returns it unconditionally.
        self._page = pn.ui.Page(
            title="My App",
            sidebar=[self._slider],
            main=[self._output],
        )

    @param.depends("value")
    def _display(self):
        return f"Value: {self.value}"

    def __panel__(self):
        return self._page
```

## Page

- For a flat script, `pn.extension(template="page")` creates a global `Page` (`pn.state.template`); add to it with `.servable(target=...)`, where targets are `"main"` (default), `"sidebar"`, `"header"` and `"contextbar"`. There is no `"modal"`; use `pn.ui.Dialog`. Don't also call `.servable()` on a `Page` you built yourself. In a `Viewer` app build the `Page` explicitly as below.
- Title goes in `Page.title` — don't repeat in `main`.
- `Page.sidebar`, `Page.main`, `Page.header` require lists — not bare components or `list(layout)`.
- Don't add `ThemeToggle` — built in.
- `header` is a single toolbar row — buttons, indicators, nav links only.
- Add `margin=10` to outer `main` layouts so they stand out from sidebar.
- Only use a sidebar when there are multiple control widgets. For a single selector, use inline `RadioButtonGroup` or `Select` in the main area with `pn.ui.Container` — avoids wasting viewport on a near-empty sidebar.
- Sidebar order: logo → description → widgets → docs.
- **Page not rendering (no header/sidebar)**: gating the `Page` construction/return on `if pn.state.served:` inside `__panel__` is a bug: the guard is **always** `False` there, even under `panel serve`, so you silently get the blank/fallback layout with no top bar. `pn.state.served` checks whether its *immediate caller's* module is the served script, and it is Panel that calls `__panel__`, not your module. Always build the `Page` once in `__init__` (e.g. `self._page = pn.ui.Page(...)`) and return it unconditionally from `__panel__` (`return self._page`). `pn.state.served` remains correct at **module level** of the served script (`if pn.state.served: App().servable()`) — see [Troubleshooting](troubleshooting-panel-apps.md#pnuipage-renders-blank-no-headersidebar).

```python
# ✅ Lists
pn.ui.Page(sidebar=[widget1, widget2], main=[content])

# ❌ Bare component — fails silently
pn.ui.Page(sidebar=widget1, main=content)
```

### Page header / AppBar color

The `Page` header is an MUI `AppBar color="primary"`. If `theme_config` sets no
`palette.primary.main`, it falls back to a hardcoded blue (`#0072b5`) with a white title — which
clashes with a dark app. Either set `palette.primary.main`, or override the header directly via the
`.header` class (use this when you want the header a different color from the brand primary, e.g. a
dark panel tone):

```python
pn.ui.Page(
    sx={"& .header": {
        "backgroundColor": "#14141b",  # match the app's panel color
        "backgroundImage": "none",
        "boxShadow": "none",
    }},
    ...
)
```

## Layouts

- Prefer `pn.ui.Column`/`pn.ui.Row` for plain stacking ([tile plot exception](#key-differences-from-panel)). Set gaps through `sx`; there is no `spacing` param.
- `pn.ui.Container(width_option="lg")` clamps content max width — prevents wide-screen stretching.
- `pn.ui.Grid` with `size=` breakpoints for responsive multi-column layouts (not `ncols`, not bare `xs`/`sm`/`md`), and `spacing=2` or more. Nest items inside `Grid(container=True)`. KPI cards: `size={"xs": 6, "md": 3}`. Side-by-side charts: `size={"xs": 12, "md": 6}`. `size="grow"` for auto-sized items.
- Set `sizing_mode="stretch_width"` on children inside `Grid` items so they fill the cell.
- List layouts take positional args: `pn.ui.Paper(a, b)`, not `pn.ui.Paper([a, b])`.

```python
# 2-column responsive layout
pn.ui.Grid(
    pn.ui.Grid(left_card, size={"xs": 12, "md": 6}),
    pn.ui.Grid(right_card, size={"xs": 12, "md": 6}),
    container=True, spacing=2,
)

# Width-clamped page content
pn.ui.Container(pn.ui.Column(...), width_option="lg")
```

### Centering in Page

The `pn.ui.Page` main area does not support CSS flexbox centering. Use margins instead:

- **Horizontal**: wrap content in `pn.ui.Container(width_option="sm")` for narrow centered cards
- **Vertical**: use integer tuple margins like `margin=(100, 0, 0, 0)` for top spacing. `margin="auto"` and `pn.Spacer()` don't work for vertical centering in Page

```python
pn.ui.Page(
    main=[
        pn.ui.Container(
            pn.ui.Column(
                pn.ui.Paper(content, sx={"p": 5}),
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
  pn.ui.Grid(pn.ui.Grid(title, size={"xs": 12}),
            pn.ui.Grid(card, size={"xs": 12, "sm": 6, "md": 3}), ...,
            container=True, spacing=2, sizing_mode="stretch_width")
  ```

- Slider thumb hits the edge → add horizontal margin, e.g. `margin=(10, 20)`.
- Mixed-height rows: `align="center"`; set gaps with `sx={"gap": "12px"}`, not per-item margins.
  `align` is a **Panel** parameter on the layout and defaults to `"start"`; it sets the flex
  alignment on the container, so it beats `sx={"alignSelf": "center"}` on the child. Reaching
  for `alignSelf` first is the usual reason a short label still sits high against taller
  buttons.

### Components

- `Card`: prefer `Paper`. Set `collapsible=False` unless needed.
- `AutocompleteInput` over `Select` past ~20 options — a long `Select` is a scroll hunt — and
  it's the only single-select widget that stays empty for `value=None` ([why that
  matters](troubleshooting-panel-apps.md#first-option-cant-be-selected-selection-widget-with-defaultnone)):

  ```python
  pn.ui.AutocompleteInput.from_param(
      obj.param.city, placeholder="Type to search…",
      restrict=True,               # keeps free text out of a validated Selector
      search_strategy="includes",  # "wa" matches Yakima, not just names starting with it
      min_characters=0,            # show the full list on focus (default is 2)
  )
  ```
- **`pn.indicators.Number` styles its title and value together.** It takes one `styles`
  dict for the whole component, so a mono face or alert colour meant for the value cascades
  onto the label too — you get an orange monospace *caption*. For a KPI card, compose two
  Typographies instead, which also lets the label use `overline`:

  ```python
  # WRONG: mono + colour leak onto the label
  pn.indicators.Number(name="Cities over AQI 100", value=6, default_color="#ef6c00",
                       styles={"font-family": MONO})
  # CORRECT: quiet label, loud value
  pn.ui.Paper(pn.ui.Typography("Cities over AQI 100", variant="overline", sx={"color": SOFT}),
             pn.ui.Typography("6", variant="kpi", sx={"color": "#ef6c00"}))
  ```

  Also note `Number.format` is a **Python** format spec (`"{value:,.0f}"`), not numeral.js —
  `"{value:0,0}"` looks plausible next to Bokeh's formatters and raises `ValueError`.
- `Tabulator`: use `"materialize"` theme, not `"material"`.
- `Box` → `Column`, `TextField` → `TextInput` (neither exists).
- `Chip`: use `label=`, not `object=` (deprecated). Chips default to `margin=10`, which blows out tight stacked layouts — set `margin=0` when packing several together. Translucent-pill look: `sx={"color": c, "backgroundColor": f"{c}22"}`.
- `Accordion` header text: the title renders as a Typography *inside* the summary, so a rule on `.MuiAccordionSummary-root` won't reach it. Target the content to restyle the label: `sx={"& .MuiAccordionSummary-content *": {"fontSize": "13px", "color": "#6d5cff"}}`.
- `RadioButtonGroup`/`CheckButtonGroup` are MUI `ToggleButtonGroup`s, so they take **no
  `variant`** ([why, and the other params that surprise](troubleshooting-panel-apps.md#typeerror-unexpected-keyword-argument-panelui-params-arent-universal))
  — only `color`, `size`, `orientation`, `disabled`, `label`, `sx`. In a sidebar go vertical,
  and get borders from `sx`:

  ```python
  pn.ui.RadioButtonGroup.from_param(
      obj.param.mode, orientation="vertical", color="primary", size="small",
      sx={"& .MuiToggleButton-root": {"borderColor": "divider"}},
  )
  ```

  `CheckBoxGroup`/`RadioBoxGroup` differ again: no `orientation` and no `size` — they take
  `inline` (`False` stacks, `True` runs horizontally). Stacked is right in a sidebar, inline
  above a wide table. With any of these four, don't add your own `Typography` label alongside —
  the widget renders its own `label` and you get the text twice.
- Button groups (`RadioButtonGroup`, `CheckButtonGroup`) follow the same `.from_param()` after-`super()` ordering rule as any widget — see [panel/SKILL.md](SKILL.md#viewer-class-pattern) for why.
- `Rating` (and other icon widgets): stretch to fill their container under the default `sizing_mode="stretch_width"`, rendering enormous. Inline `Markdown`/`HTML` labels next to an `HSpacer` in the same `Row` fail the other way — they collapse to near-zero width and wrap one character per line. Pin both with an explicit `width` plus `sizing_mode="fixed"`:

  ```python
  # ❌ Rating fills the row (giant stars); the label wraps vertically
  pn.Row(pn.pane.Markdown("**Rating:**"), pn.ui.Rating(end=5), pn.layout.HSpacer())

  # ✅ pinned
  pn.Row(
      pn.pane.HTML("<b>Rating:</b>", width=64, sizing_mode="fixed"),
      pn.ui.Rating(end=5, size="small", width=170, sizing_mode="fixed"),
      pn.layout.HSpacer(),
  )
  ```
- `Dialog`: for secondary detail that would crowd the page (or overflow the narrow `Page` contextbar), use a dialog and toggle `.open`. `close_on_click=True` dismisses on backdrop click:

  ```python
  self._details = pn.ui.Dialog(content, title="Details",
                              width_option="md", open=False, close_on_click=True)
  # open from a button: self._details.open = True
  ```

### Notifications

Toast-style alerts that float over the page rather than living in a fixed layout slot — the right choice for transient feedback ("saved", "request failed") where an inline `Alert` would shift layout. Enable once with `pn.extension(notifications=True)` (or `pn.config.notifications = True`), then call from any callback:

```python
pn.state.notifications.success("Saved", duration=3000)
pn.state.notifications.error("Request failed", duration=0)   # duration=0 stays until dismissed
pn.state.notifications.info("...")
pn.state.notifications.warning("...")
pn.state.notifications.send("Custom", background="#ff0000", icon="local_fire_department")
pn.state.notifications.clear()
```

The API is identical in plain Panel and `panel.ui` — no separate `panel.ui` import needed, and `pn.state.notifications.position = "top-right"` controls placement.

**Gotcha — threading:** under `pn.extension(nthreads=...)`, calling a `pn.state.notifications.*` method from code running on a worker thread can silently stop executing the rest of that callback with no error surfaced (server and other callbacks keep running; only that one callback goes dark). If a callback that fires a notification stops having its later side effects apply once threading is enabled, this is the first thing to suspect — move the notification call off the threaded path, or verify the specific call actually completes.
