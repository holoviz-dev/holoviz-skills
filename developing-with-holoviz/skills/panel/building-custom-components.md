# Building Custom Components

Build custom Panel components — pure-Python ones that compose existing widgets,
and JS-backed ones that bridge Python and JavaScript.

## Contents

- [Choosing an Approach (Python vs JS)](#choosing-an-approach-python-vs-js)
- [Pure-Python Components: `Viewer` and `PyComponent`](#pure-python-components-viewer-and-pycomponent)
- [Which JS Component Type](#which-js-component-type)
- [When a JS Component Is Warranted](#when-a-js-component-is-warranted)
- [Recipe: a Clickable Rich Row (JSComponent)](#recipe-a-clickable-rich-row-jscomponent)
- [Development: POC First](#development-poc-first)
- [Python Class Structure](#python-class-structure)
- [CDN Selection Guide (Critical)](#cdn-selection-guide-critical)
- [Event Handling](#event-handling)
- [The `_rename` Dict](#the-_rename-dict)
- [Child and Children](#child-and-children)
- [JSComponent: State Sync and Lifecycle](#jscomponent-state-sync-and-lifecycle)
- [ReactComponent: useState](#reactcomponent-usestate)
- [AnyWidgetComponent: get/set/save_changes](#anywidgetcomponent-getsetsave_changes)
- [MaterialUIComponent](#materialuicomponent)
- [Key DOs and DON'Ts](#key-dos-and-donts)

## Choosing an Approach (Python vs JS)

Most custom components need no JavaScript. Work down this ladder; stop at the
first rung that works — each one below costs more (JS file, CDN debugging,
state-sync lifecycle):

1. **Native pmui / Panel widget** — no code; most "rich" UI is layout over `Paper`, `Chip`, `Grid`, `Accordion`, `Button`, `MenuList`.
2. **Pure-Python composite** (`Viewer` or `PyComponent`) — wire *existing* widgets into one reusable, Param-synced unit. No JS. See below.
3. **JS component** — only for rendering no Panel widget provides (JS charting/mapping lib, bespoke DOM, fully-clickable rich row). See [Which JS Component Type](#which-js-component-type).

The common mistake is jumping to rung 3 and reimplementing a slider or
multi-select Panel already ships.

## Pure-Python Components: `Viewer` and `PyComponent`

Compose existing Panel objects into one reusable component with its own Param API
— no `.js`, CDN, or bundler. Both need a `__panel__` returning the layout, and
sync outer params to inner widgets with `@param.depends(..., watch=True)`.

- **`Viewer`** (`from panel.viewable import Viewer`) — a reusable layout block;
  lowest ceremony. Pattern: [Custom Viewer](https://panel.holoviz.org/how_to/custom_components/custom_viewer.html).
- **`PyComponent`** (`from panel.custom import PyComponent`) — when the result
  must *be* a first-class `Widget`/`Pane` (a `.value`, works with `.from_param`).
  Inherit the type base first, impl second: `class FeatureInput(WidgetBase, PyComponent)`.
  Pattern: [Build a Widget in Python](https://panel.holoviz.org/how_to/custom_components/python/create_custom_widget.html).

Shape (a `Viewer` wrapping two `FloatInput`s; sync runs both ways):

```python
class EditableRange(Viewer):
    value = param.Range(default=(0, 1))

    def __init__(self, **params):
        self._start, self._end = pn.widgets.FloatInput(), pn.widgets.FloatInput()
        super().__init__(**params)
        ...  # build self._layout = pn.Row(self._start, self._end)

    def __panel__(self): return self._layout

    @param.depends("value", watch=True)        # outer → inner
    def _sync_widgets(self): self._start.value, self._end.value = self.value

    @param.depends("_start.value", "_end.value", watch=True)   # inner → outer
    def _sync_params(self): self.value = (self._start.value, self._end.value)
```

## Which JS Component Type

| Criteria | JSComponent | ReactComponent | AnyWidgetComponent | MaterialUIComponent |
|---|---|---|---|---|
| Best For | Vanilla JS, D3, Leaflet | React ecosystem, complex state | Cross-platform (Jupyter+Panel) | `panel-material-ui` apps |
| State Sync | `model.value`, `model.on('param', cb)` | `model.useState("param")` | `model.get/set/save_changes` | `model.useState("param")` |
| Export | `export function render({model, el})` | `export function render({model, el})` | `export default { render }` | `export function render({model, el})` |
| ESM attr | `_esm` | `_esm` | `_esm` | `_esm_base` |

## When a JS Component Is Warranted

The ladder above keeps you on rungs 1–2 whenever possible; reach for a *JS* component
(almost always a vanilla-JS `JSComponent`) only when native widgets genuinely can't express the
interaction. The clearest trigger: a **fully-clickable element with rich multi-part content** —
e.g. a list row showing text plus several colored chips, where clicking anywhere selects it.
`pmui.Button` takes only a string `label`, so it can't host that content, and `MenuList` items
flatten rich content into label/secondary/icon.

- **❌ Anti-pattern — the overlay button (wastes hours).** Don't layer a transparent full-size
  `pmui.Button` over a composed visual row to "capture the click." The Panel wrapper around the
  inner MUI button stays in normal document flow, so `height: 100%` / `inset: 0` in `sx` resolves
  against an auto-height parent and the hit area **collapses to zero height** — clicks never land,
  silently. (`pointer-events`, `z-index`, and `styles` vs `sx` juggling don't reliably fix it.)
- **✅ Do — one clickable `JSComponent`.** Render the whole row as a single `<div>` with an
  `onclick`. Full control, one event path, no overlay. See the recipe below.

## Recipe: a Clickable Rich Row (JSComponent)

A reusable pattern for "selectable list row with rich content." Python side — plain params, derived
fields as `@staticmethod`s so the component is self-contained and constructible from a domain dict:

```python
# pyright: reportAssignmentType=false
from pathlib import Path
import param
from panel.custom import JSComponent

class AccountRow(JSComponent):
    account  = param.String(default="")
    subline  = param.String(default="")
    pills    = param.List(default=[])      # [{"label": "...", "color": "#..."}]
    deal_id  = param.String(default="")
    active   = param.Boolean(default=False)
    _esm = Path(__file__).parent / "account_row.js"

    def __init__(self, deal=None, **params):
        if deal is not None:
            params.setdefault("account", deal["account"])
            params.setdefault("subline", self.subline_for(deal))
            params.setdefault("pills", self.pills_for(deal))
            params.setdefault("deal_id", deal["id"])
        super().__init__(**params)

    @staticmethod
    def pills_for(deal):  # field-derivation lives on the class, not module scope
        ...
```

JS side (`account_row.js`) — build one clickable `<div>`, emit a `select` event, restyle on `active`:

```javascript
export function render({ model, el }) {
  function build() {
    el.innerHTML = "";
    const row = document.createElement("div");
    // ...set text from model.account / model.subline, append chips from model.pills...
    row.style.borderColor = model.active ? "#6d5cff" : "transparent";
    row.onclick = () => model.send_event("select", {});   // → Python
    el.appendChild(row);
  }
  build();
  model.on("active", build);                 // re-style on selection
  model.on("account subline pills", build);  // rebuild if content changes
}
```

## Development: POC First

Build in two phases. Getting JS imports and responsive sizing working takes significant debugging.

**Phase 1**: Minimal POC with your actual target library. Validate: (1) imports load without CORS/export errors, (2) library renders visible output, (3) Python-JS state syncs, (4) component displays responsively. Test via Playwright smoke tests.

**Phase 2**: Full component — all parameters, full library integration, error handling, CSS.

## Python Class Structure

```python
import param
from panel.custom import JSComponent
from pathlib import Path

class MyComponent(JSComponent):
    value = param.Integer(default=0, bounds=(0, 100))
    _esm = Path(__file__).parent / "my_component.js"  # external file for dev + hot reload
    _importmap = {
        "imports": {
            "lodash": "https://esm.sh/lodash@4.17.21",
        }
    }
    _stylesheets = [Path(__file__).parent / "my_component.css"]
```

## CDN Selection Guide (Critical)

Libraries with plugin architectures (FullCalendar, ProseMirror, TipTap) break on esm.sh because each plugin gets its own copy of shared internals — prototype chain breaks silently.

- **Plugin-based libraries** → use `cdn.skypack.dev`. It deduplicates shared internals.
- **Standalone or React libraries** → `esm.sh` is fine. Use `?external=react,react-dom` for React.
- **CSS files or raw packages** → `cdn.jsdelivr.net`.

Signs you hit this: toolbar renders but content is blank, `"Class constructor X cannot be invoked without 'new'"`, works in plain HTML but breaks in Panel.

```python
# ❌ FAILS with esm.sh — each plugin gets own copy of core
_importmap = {"imports": {
    "@fullcalendar/core": "https://esm.sh/@fullcalendar/core@6.1.15",
    "@fullcalendar/daygrid": "https://esm.sh/@fullcalendar/daygrid@6.1.15",
}}

# ✅ WORKS with skypack — deduplicates core
_importmap = {"imports": {
    "@fullcalendar/core": "https://cdn.skypack.dev/@fullcalendar/core@6.1.15",
    "@fullcalendar/daygrid": "https://cdn.skypack.dev/@fullcalendar/daygrid@6.1.15",
}}
```

## Event Handling

Two patterns: **structured events** for simple actions, **message passing** for complex bidirectional communication.

### Structured Events (JS → Python)

```javascript
button.onclick = () => model.send_event('button_click', { timestamp: Date.now() });
```
```python
def _handle_button_click(self, event):  # handler name must be _handle_{event_name}
    print(f"Clicked at {event.data['timestamp']}")
```

### Python → JS Commands

```python
def trigger_animation(self):
    self._send_msg({'action': 'animate', 'duration': 500})  # CRITICAL: _send_msg, not send_msg
```
```javascript
model.on('msg:custom', (event) => {
    if (event.data.action === 'animate') runAnimation(event.data.duration);
});
```

### Message Passing (complex bidirectional)

```javascript
// JS: multiple callback types routed through send_msg
eventClick(info) { model.send_msg({ clicked_event: JSON.stringify(info.event) }); },
datesSet(info) { model.send_msg({ current_date: info.startStr }); },
```
```python
def _handle_msg(self, msg):  # single handler dispatches by key
    if "clicked_event" in msg:
        self.clicked_event = json.loads(msg["clicked_event"])
    if "current_date" in msg:
        self.current_date = msg["current_date"]
```

## The `_rename` Dict

Exclude Python-only parameters (callables, read-only state) from JS sync:

```python
_rename = {
    "event_click_callback": None,  # None = exclude from JS
    "events_in_view": None,
}
```

## Child and Children

```python
from panel.custom import JSComponent, Child, Children

class Container(JSComponent):
    header = Child()
    items = Children()
    _esm = """
    export function render({ model, el }) {
        el.appendChild(model.get_child("header"));
        for (const item of model.get_child("items")) el.appendChild(item);
    }
    """
```

## JSComponent: State Sync and Lifecycle

```javascript
export function render({ model, el }) {
    // Read/write: direct property access
    const val = model.value;
    model.value = 42;  // syncs to Python

    // Subscribe to changes
    model.on('value', () => { el.textContent = model.value; });
}

// after_render — for measurements needing DOM dimensions
export function after_render({ model, el }) {
    initChart(el, el.clientWidth, el.clientHeight);
}

// Lifecycle events
model.on('resize', ({ width, height }) => { chart.resize(width, height); });
model.on('remove', () => { clearInterval(interval); });
```

## ReactComponent: useState

```javascript
export function render({ model }) {
    const [value, setValue] = model.useState("value");   // syncs to Python
    const [local, setLocal] = React.useState(false);     // UI-only

    return <button onClick={() => setValue(value + 1)}>Count: {value}</button>;
}
```

- Don't import React — it's globally available.
- Use `?external=react,react-dom` for external React libraries in `_importmap`.

## AnyWidgetComponent: get/set/save_changes

```javascript
export default {
    render({ model, el }) {
        const val = model.get("value");
        model.set("value", 42);
        model.save_changes();  // REQUIRED — without it, changes don't sync to Python
        model.on("change:value", () => { /* update UI */ });
    }
}
```

- Always pin React versions: `?deps=react@18.2.0,react-dom@18.2.0`. Without pinning, esm.sh serves React 19 with breaking changes.

## MaterialUIComponent

Uses `_esm_base` (not `_esm`) — builds on the panel-material-ui JS bundle. `@mui/material/` is pre-configured.

```python
from panel_material_ui import MaterialUIComponent

class StyledButton(MaterialUIComponent):
    label = param.String(default="Click me")
    _esm_base = """
    import Button from "@mui/material/Button";
    export function render({ model }) {
        const [label] = model.useState("label");
        return <Button variant="contained" onClick={() => model.send_event("click", {})}>{label}</Button>;
    }
    """
```

### MUI Icons

Use explicit icon imports with `?external=react`. Don't use trailing slash pattern with query params.

```python
_importmap = {"imports": {
    "@mui/icons-material/Favorite": "https://esm.sh/@mui/icons-material@5.16.7/Favorite?external=react",
}}
```

Use inline `style` props for icon dimensions — MUI CSS classes may not load properly.

## Key DOs and DON'Ts

- Use external `.js`/`.jsx` files + `panel serve --dev` for hot reload. Use `panel compile` for production.
- Don't use `_` prefix for parameters needed in JS — private params don't sync.
- Prefer ESM imports over `__javascript__` — ESM is synchronous, `__javascript__` races with `render()`.
- Don't mix API patterns between component types (e.g., `model.get()` in ReactComponent).
- Set descriptive element IDs for Playwright testing.
- Handle resize events for responsive components.
- Clean up resources (intervals, listeners) in the `remove` lifecycle.
- **`send_event` carries no source.** The Python handler receives a bare `DOMEvent` with **no
  `.obj`** — reaching for `event.obj.some_id` raises `AttributeError`. When many instances share one
  event name, bind a per-instance closure that captures the id, rather than reading it off the event:

  ```python
  # ❌ AttributeError: 'DOMEvent' object has no attribute 'obj'
  row.on_event("select", lambda e: setattr(self, "selected", e.obj.deal_id))

  # ✅ capture the id in a closure
  def _make_handler(self, deal_id):
      def handler(event):
          self.selected = deal_id
      return handler
  row.on_event("select", self._make_handler(deal_id))
  ```
- **Shadow DOM defeats DOM scraping.** pmui renders into shadow roots, so Playwright
  `document.querySelector` / `getByText` often can't reach inside a component and `boundingBox()` can
  read `0×0`. Verify behavior by asserting on **Python-side param/state** (or a visible status pane
  you bind for the test), not by scraping the rendered DOM.
- **Keep components self-contained with `@staticmethod`.** Put field-derivation (e.g. `pills_for`,
  `subline_for`) on the class as static methods, not module-level helpers, so the component carries
  its own domain-dict → params mapping and can be constructed as `Row(record)`.
