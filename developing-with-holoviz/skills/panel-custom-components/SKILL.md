---
name: panel-custom-components
description: Build custom Panel components bridging Python and JavaScript. Use when wrapping JS libraries (D3, Leaflet, FullCalendar), creating interactive widgets with JSComponent/ReactComponent/AnyWidgetComponent, or debugging ESM import and CDN issues.
metadata:
  version: "1.1.0"
  author: holoviz
---

# Panel Custom Components

Build custom Panel components that bridge Python and JavaScript.

## Which Component Type

| Criteria | JSComponent | ReactComponent | AnyWidgetComponent | MaterialUIComponent |
|---|---|---|---|---|
| Best For | Vanilla JS, D3, Leaflet | React ecosystem, complex state | Cross-platform (Jupyter+Panel) | `panel-material-ui` apps |
| State Sync | `model.value`, `model.on('param', cb)` | `model.useState("param")` | `model.get/set/save_changes` | `model.useState("param")` |
| Export | `export function render({model, el})` | `export function render({model, el})` | `export default { render }` | `export function render({model, el})` |
| ESM attr | `_esm` | `_esm` | `_esm` | `_esm_base` |

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
