# Wrapping React Apps

Make an existing React front-end *be* the Panel app: one `ReactComponent`
renders the entire UI from a `.jsx` file, and Panel components (chat, tables,
plots) are embedded into its JSX tree as children. Params are the only wire
between them.

This is the opposite direction from
[Converting Designs to Material UI](converting-designs-to-material-ui.md), which
rebuilds a React UI in pmui. For the component-type decision ladder and CDN
rules, see [Building Custom Components](building-custom-components.md) — this
document is only about the whole-app case.

## Contents

- [When This Shape Is Right](#when-this-shape-is-right)
- [Two Classes: Shell and App](#two-classes-shell-and-app)
- [Params Are the Only Transport](#params-are-the-only-transport)
- [Embedding Panel Components as Children](#embedding-panel-components-as-children)
- [Request/Response Param Pairs](#requestresponse-param-pairs)
- [Shadow DOM and Stylesheets](#shadow-dom-and-stylesheets)
- [The `_importmap` Query-String Trap](#the-_importmap-query-string-trap)
- [Compiling the Bundle](#compiling-the-bundle)
- [Owning the Whole Page](#owning-the-whole-page)
- [Key DOs and DON'Ts](#key-dos-and-donts)

## When This Shape Is Right

Reach for it only when the React UI is the asset and Python is the service layer:

- A substantial React/JSX UI already exists — thousands of lines, bespoke CSS,
  many views — and rebuilding it in pmui is the larger job.
- The UI is mostly *chrome*: navigation, modals, cards, toasts, filters. The
  parts that need Python are few and well-bounded (a chat, a data table, a plot).
- You need CSS control that Material's theme system doesn't give you.

Rebuild in pmui instead when the design is mostly widgets pmui already ships, or
when nearly every interaction needs Python. Every param is a websocket round
trip, so a UI where Python must respond to each click is slower and more code
this way than in pmui. The failure mode is choosing the React shell for a
dashboard and then re-implementing `Select`, `Tabs`, and `DataFrame` in JSX.

## Two Classes: Shell and App

Split the Python side in two. The `ReactComponent` is a *declarative param
surface* that mirrors the JSX and holds no logic; a `Viewer` owns the data, the
watchers, and the async work.

```python
import pathlib

import panel as pn
import panel_material_ui as pmui
import param
from panel.custom import Child, ReactComponent


class Shell(ReactComponent):
    """Param surface only — no watchers, no IO."""

    data = param.Dict(default={})
    current_view = param.Selector(default="Dashboard", objects=["Dashboard", "Detail"])
    theme = param.Selector(default="dark", objects=["dark", "light"])
    favorites = param.List(default=[])
    chat = Child()

    _esm = "shell.jsx"
    _stylesheets = ["shell.css"]
    _bundle = pathlib.Path(__file__).parent / "shell.bundle.js"


class App(pn.viewable.Viewer):
    def __init__(self, **params):
        super().__init__(**params)
        self._chat = pmui.ChatInterface(callback=self._chat_callback, sizing_mode="stretch_both")
        self.shell = Shell(data=load_data(), chat=self._chat, sizing_mode="stretch_both")
        self.shell.param.watch(self._persist, ["theme", "favorites"])

    def __panel__(self):
        return self.shell
```

Keeping them separate pays off three ways: the shell class stays readable as the
contract the JSX consumes, side effects live somewhere testable without a
browser, and the shell can be driven by a different data source (fixtures, a
second app) without touching it.

## Params Are the Only Transport

`model.useState("param_name")` gives a React-hook-shaped tuple wired
bidirectionally to the Python param. A whole-app shell needs nothing else — no
custom messages, no `_handle_msg`, no events.

```javascript
export function render({ model, view }) {
  const [data] = model.useState("data");                    // Python owns it
  const [view_, setView] = model.useState("current_view");  // both sides write
  const [menuOpen, setMenuOpen] = React.useState(false);    // UI-only, stays local
  ...
}
```

Two rules that matter more at app scale than for a single widget:

- **Don't import React.** Panel provides it as a global. An `import React from
  "react"` line resolves to a second copy and hooks throw *Invalid hook call*.
- **Only promote state to a param if Python needs it.** Hover state, which
  accordion is open, a dropdown's open flag — these belong in `React.useState`.
  Every `model.useState` param costs a round trip and a re-render on change, so
  a shell that puts `menuOpen` on the Python class pays network latency to open
  a menu. Expect roughly a 2:1 split of local to synced state.

## Embedding Panel Components as Children

Declare `Child()` (one) or `Children()` (a list) and render with
`model.get_child`, which returns a React element you can place in JSX:

```python
chat = Child()
theme_toggle = Child()
```

```jsx
<aside className="chat">{model.get_child("chat")}</aside>
```

The child is a real Panel component with real Python callbacks — a
`pmui.ChatInterface` with an async streaming callback, a `Tabulator` with
`add_filter`, a HoloViews pane. Give children `sizing_mode="stretch_both"` and a
CSS container with an explicit height; a child in an auto-height flex box
collapses to nothing.

There is also an escape hatch for writing straight to a child's Bokeh model from
JS, bypassing params:

```javascript
view.model.data.theme_toggle.data.value = new_theme === "dark";
```

Use it only to drive a hidden control you deliberately mounted — the standard
case being a `pmui.ThemeToggle(visible=False)` so pmui's own theming follows the
shell's theme switch. It is unvalidated and untyped, so anything you can express
as a param should be one.

## Request/Response Param Pairs

React cannot call Python. Model each call as a request param the JSX writes and
a response param it reads:

```python
suggest_request = param.String(default="")
suggest_response = param.String(default="")
```

```python
def _on_suggest(self, event):
    payload = (event.new or "").strip()
    if not payload:
        return
    self.shell.suggest_request = ""   # reset so an identical repeat re-fires
    pn.state.execute(partial(self._run_suggest, payload))

async def _run_suggest(self, payload):
    self.shell.suggest_response = await self._llm.suggest(payload)
```

Both lines in that watcher are load-bearing:

- **Reset the request param immediately.** Params fire watchers only on
  *change*, so submitting the same request twice in a row is silently a no-op
  unless you clear it. This is the usual cause of "it works once".
- **Don't do async work in the watcher.** Watchers are synchronous; awaiting
  there blocks the session. `pn.state.execute` schedules the coroutine on the
  session's event loop so the UI stays live.

For long operations add a third param the Python side writes progress into
(`sync_message`, `sync_report`) and render it in React — that's how you get a
progress bar without a second channel.

## Shadow DOM and Stylesheets

`ReactComponent.use_shadow_dom` defaults to `True`, and it only takes effect
when the parent is *not* another React component — which is exactly the
whole-app case. Consequences that cost the most debugging time:

- **Page-level CSS does not reach inside.** Every stylesheet the shell needs
  must be in `_stylesheets` (local path or CDN URL). `pn.config.raw_css` and
  `<style>` blocks in the template do nothing for shell markup.
- **Libraries that inject CSS into `document.head` at runtime render
  unstyled**, because the head is outside the shadow root. FontAwesome is the
  common case: disable its auto-injection and load the stylesheet explicitly.

  ```javascript
  import { config, library } from "@fortawesome/fontawesome-svg-core";
  config.autoAddCss = false;   // its runtime <style> can't reach into the shadow root
  library.add(/* ...icons */);
  ```

  ```python
  _stylesheets = [
      "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/svg-with-js.min.css",
      "shell.css",
  ]
  ```
- **Anything portalled to `document.body` escapes your CSS.** Render modals,
  dropdowns, and toasts inside the component tree rather than through
  `ReactDOM.createPortal`, or they appear unstyled.
- **`document.querySelector` won't find your own nodes.** Use refs.

## The `_importmap` Query-String Trap

Panel appends `?deps=react@<v>,react-dom@<v>&external=react,react-dom` to every
`esm.sh` URL in `_importmap` that has no `?` of its own. Add any query string and
you opt out of that entirely — so you must declare the externals yourself, or
the package ships its own React and every hook throws *Invalid hook call*.

```python
_importmap = {
    "imports": {
        # ✅ no "?" — Panel adds deps + external=react automatically
        "@fortawesome/fontawesome-svg-core": "https://esm.sh/@fortawesome/fontawesome-svg-core@6.7.2",

        # ❌ has a "?", so the auto-suffix is skipped — this bundles a second React
        "@fortawesome/react-fontawesome": "https://esm.sh/@fortawesome/react-fontawesome@3.1.1?bundle",

        # ✅ opted out, so externals are declared explicitly — including peer deps
        "@fortawesome/react-fontawesome": (
            "https://esm.sh/@fortawesome/react-fontawesome@3.1.1"
            "?external=react,@fortawesome/fontawesome-svg-core"
        ),
    }
}
```

List *every* shared peer dependency in `external=`, not just React. Two copies of
an icon library means `library.add()` populates one registry while the components
read the other, and icons silently don't render.

## Compiling the Bundle

`_bundle` points at precompiled esbuild output. Which of `_bundle` and `_esm`
actually gets served depends on the serve mode, and this asymmetry is the trap:

| Serve mode | What's served |
|---|---|
| `panel serve --dev` (sets `config.autoreload`) | Raw `.jsx`, transpiled in-browser, deps fetched from CDN per `_importmap`. `_bundle` is **ignored**. |
| `panel serve` (production) | `_bundle`. `_esm` and `_importmap` are **ignored**. |

So editing the `.jsx` and verifying with `--dev` looks perfect while production
keeps serving the stale bundle. Recompile before every deploy, and treat the
bundle as a reviewable build artifact.

```bash
panel compile path/to/shell.py:Shell
```

- Requires `node`, `npm`, and `esbuild` on `PATH`.
- Writes to `_bundle` when set; otherwise `<ClassName>.bundle.js` beside the module.
- **It imports the module**, so module-level code must be import-safe. Guard app
  construction with `if __name__.startswith("bokeh"):` rather than running it at
  import time.
- esbuild bundles with no externals, so React ends up *inside* the bundle
  (expect a few hundred KB) and nothing is fetched from a CDN at runtime.
- Version pins in `_importmap` URLs become the npm dependency pins — a URL
  without a version resolves to `latest`, so pin deliberately.
- `--unminified` to read the output, `--build-dir` plus `--skip-npm` to
  recompile without reinstalling `node_modules`.

## Owning the Whole Page

A shell like this *is* the page and should not be wrapped in a template. Set the
document up in `server_doc`:

```python
from panel_material_ui.base import BASE_TEMPLATE


class Shell(ReactComponent):
    ...

    def server_doc(self, doc=None, title=None, location=True):
        doc = super().server_doc(doc, title, location)
        doc.title = title or "My App"
        doc.template = BASE_TEMPLATE
        doc.template_variables["is_page"] = True
        doc.template_variables["favicon"] = "https://example.com/favicon.ico"
        return doc
```

`is_page=True` marks `<html data-theme-managed="true">` and suppresses Panel's
bundled theme stylesheet, handing theming to the component. pmui components do
this for themselves when a `ThemeToggle` is in the tree, but a plain
`ReactComponent` inherits Panel's `server_doc` and must opt in. Skipping it
leaves Panel's theme CSS fighting your own.

Pair it with `sizing_mode="stretch_both"` on the shell instance and serve with
the usual `__name__` guard:

```python
if __name__.startswith("bokeh"):
    App().servable()
elif __name__ == "__main__":
    pn.serve(App)
```

## Key DOs and DON'Ts

- **DO** keep the shell class a pure param surface and put watchers on a separate
  `Viewer`.
- **DO** clear request params inside their watcher, and schedule async work with
  `pn.state.execute`.
- **DO** recompile the bundle before deploying, and check the compiled artifact
  into review.
- **DON'T** import React, or add a query string to an `esm.sh` URL without also
  passing `external=react`.
- **DON'T** promote UI-only state (hover, open/closed) to a Python param.
- **DON'T** assume page CSS reaches the shell — shadow DOM is on, so use
  `_stylesheets`.
- **DON'T** choose this shape for a UI that pmui components already cover.
