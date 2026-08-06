# Iterating on Panel Apps

Agentic workflow for developing and debugging Panel apps. For agents with shell access: run a static preflight check before first serve, serve with logging, iterate by reading logs after each edit, run a live-browser layout lint before reaching for a screenshot, benchmark time to first paint, and screenshot only when you need to verify something a number can't capture — all without requiring user intervention. Where panel-live-server's MCP tools are connected, prefer them for rendering and screenshotting snippets.

## Contents

- [Development Loop](#development-loop)
- [Verifying with panel-live-server](#verifying-with-panel-live-server) — MCP tools that render and screenshot a snippet for you
- [Decouple from the Backend](#decouple-from-the-backend)
- [Serving with Logs](#serving-with-logs)
- [Benchmarking Startup](#benchmarking-startup)
- [Layout Linting](#layout-linting)
- [Inspecting the Plot Model](#inspecting-the-plot-model)
- [Screenshotting with Playwright](#screenshotting-with-playwright)
  - [When to Screenshot](#when-to-screenshot)
- [Common Errors](#common-errors)

## Development Loop

0. **Preflight** the code before the first serve: run the `preflight.py` script that ships in this skill's `scripts/` directory, resolved relative to wherever you read this file from (skills are installed at different paths per tool, e.g. `.claude/skills/developing-with-holoviz/skills/panel/scripts/preflight.py` — don't assume it's reachable via a bare relative path from the app's own working directory). This is a static, dependency-free check for the mechanical anti-patterns already documented in [Reviewing Panel Apps](reviewing-panel-apps.md) and [Troubleshooting](troubleshooting.md) — flicker-causing `@param.depends` returns, `from_param` before `super()`, missing `pn.io.hold()`, mutated params, `Radio*Group` defaults, missing `throttled`. It costs nothing and catches most bugs before a server is even running, so run it before spending a log-tail cycle or a screenshot on something greppable. `scripts/test_preflight.py` is the check suite for the linter itself, built from this doc's own WRONG/CORRECT pairs — `cd` into `scripts/` and run `python test_preflight.py` (no pytest required) after editing any check in `preflight.py`.
1. **Serve** the app once with logs captured to a file — the `--dev` flag auto-reloads on file changes, so you don't restart per edit
2. **Edit** the code to fix issues
3. **Check logs** for Python errors after each edit (tracebacks show invalid params and valid options) — this is fast and cheap, so do it every iteration
4. **Repeat** edit + log check until the logs are clean
5. **Layout lint** once the logs are clean: run `scripts/layout_lint.py` against the served URL (see [Layout Linting](#layout-linting)) — it catches geometry and contrast issues as text, before they'd otherwise cost a screenshot
6. **Inspect the plot model** if a chart looks wrong — axis ranges, layer count, and applied options are readable as numbers from the Bokeh model, no browser needed (see [Inspecting the Plot Model](#inspecting-the-plot-model))
7. **Benchmark startup** — time to first paint is invisible in clean logs and in a screenshot, so measure it explicitly (see [Benchmarking Startup](#benchmarking-startup))
8. **Screenshot** with Playwright only when you need to confirm something visual that isn't geometry or contrast (see [when to screenshot](#when-to-screenshot)), then **review** the image for hierarchy/styling judgment calls

Drive iteration from preflight, the logs, and layout lint — not from screenshots. Reach for a screenshot at milestones — once preflight, the logs, and layout lint are all clean, when debugging a specifically visual problem those can't reveal, or for a final check — not on every edit.

If [panel-live-server](#verifying-with-panel-live-server) is connected, use its `screenshot` tool for step 8 instead of hand-rolling Playwright, and its `evaluate` tool wherever this loop calls for reading a value out of Python. It takes **snippets, not files**, so it does not replace `panel serve` for an app you're editing on disk — see below for which job each tool is for.

## Verifying with panel-live-server

[panel-live-server](https://panel-extensions.github.io/panel-live-server/tutorials/mcp-server/) exposes an MCP server (`pls mcp`) that executes a Python snippet and renders it, managing the Panel server itself. Check whether these tools are available before hand-rolling the equivalent; all three take a `code` string, so they suit **self-contained snippets** — a chart, a repro, a small dashboard — not an app you are iterating on as a file.

| Tool | Goes to | Use for |
|------|---------|---------|
| `evaluate(code)` | you, text | Facts about objects: whether a param exists, what columns a frame has, what range Bokeh computed. No browser, no render. |
| `screenshot(code=…)` | you, image | Checking your own draft. Renders and returns the PNG **privately** — nothing reaches the user, so iterate here as many rounds as needed. |
| `show(code=…, name=…)` | the user, live URL | Finished work only. Validates, renders, returns a URL to present as a Markdown link. |

`show` is a handoff, not a verification step. Don't call it to obtain a `snippet_id` to screenshot — that parades every draft past the user. Use `screenshot(code=…)` while iterating, then `show` once. (`screenshot(snippet_id=…)` answers a follow-up about something already shown.)

Two rules for choosing between the other two:

- **Appearance questions go through `screenshot`.** Where the peak sits, which bar is tallest, whether the legend overlaps — read it off the image. Recomputing from the data is unreliable *because* the render disagrees with it: axes invert, categories sort, heatmap rows flip, values get binned.
- **Everything textual goes through `evaluate`.** Rendering a value into a Markdown pane to read it back out of a PNG costs a browser launch and an image, and tells you nothing the text wouldn't have — the same read-it-as-text-first principle as [layout linting](#layout-linting) and [plot-model inspection](#inspecting-the-plot-model).

Notes: pass the code as the `code` argument — don't write a scratch file and point at it, there is no path parameter. Anything importing Panel to build a dashboard needs `method="server"` plus `.servable()`; the default `"inline"` renders the last expression and needs top-level statements fully dedented. `screenshot` needs Chromium once via `pls install-browser`. The snippets run in the server's own environment, which the agent can't install into — check what's there with `pls list packages`.

## Decouple from the Backend

When the app reads from a slow or unavailable backend (a database, an internal service, an external API), put data access behind a small source interface and inject a **mock source** via an env flag. You can then serve, screenshot, and test the full UI without the live system.

```python
class BaseSource:
    def list_items(self): ...
    def load(self, key): ...

class MockSource(BaseSource):
    """Synthetic rows + tiny inline assets, with knobs to rehearse slow/broken states."""

    def __init__(self, latency: float = 0.0, fail: bool = False):
        self.latency = latency  # seconds to sleep before returning — rehearses loading states
        self.fail = fail        # raise instead of returning — rehearses error states

    def list_items(self):
        if self.latency:
            time.sleep(self.latency)
        if self.fail:
            raise RuntimeError("mock backend failure")
        return [...]  # synthetic rows

SOURCE = (
    MockSource(latency=float(os.environ.get("APP_LATENCY", 0)),
               fail=os.environ.get("APP_FAIL") == "1")
    if os.environ.get("APP_MOCK") == "1" else LiveSource()
)
```

Exercise the loading spinner or the error/Alert state from the command line, without touching app code:

```bash
APP_MOCK=1 APP_LATENCY=2 panel serve app.py --dev --show   # loading state
APP_MOCK=1 APP_FAIL=1 panel serve app.py --dev --show      # error state
```

Catch the raised error in the calling watcher and surface it as a `pmui.Alert` or a notification (see [Notifications](using-material-ui.md#notifications)) instead of letting it crash the callback silently — an app with no exercised error path is untested, not robust. `time.sleep` is fine for a headless smoke test, but for the spinner to actually show *during* a live-served request the slow call needs to run `async` (see the loading-spinner caveat in [Designing Panel Architecture](designing-panel-architecture.md#batching-loading-and-memory)).

Then drive a headless smoke test by setting widget/param values and asserting the panes updated — no browser needed:

```python
app = MyApp()
app._toggle.value = "lines"                 # simulate a click
assert app.chart_type == "lines"            # watcher fired
assert "lines" in app._chart_pane.object    # render propagated
```

Serve it the same way — `APP_MOCK=1 panel serve app.py --dev --show` — so the real UI renders with fake data.

## Serving with Logs

Start the dev server with output captured for debugging:

```bash
panel serve app.py --dev --port 5007 2>&1 | tee /tmp/panel.log &
```

After edits, check for errors:

```bash
tail -20 /tmp/panel.log
```

Errors include full tracebacks with the invalid parameter and valid options — check these before guessing at param names or values.

To restart cleanly:

```bash
pkill -f "panel serve.*app.py" 2>/dev/null; sleep 1
panel serve app.py --dev --port 5007 2>&1 | tee /tmp/panel.log &
```

## Benchmarking Startup

Time to first paint is the one quality this loop otherwise never surfaces: the logs stay
clean and the screenshot looks right while the app takes fifteen seconds to appear. Measure
it deliberately, because the usual cause is invisible by construction — work done eagerly
for something that isn't on screen yet. A tab whose data is computed in `__init__` instead
of on first activation, or a baseline averaged over a wide window, can easily cost an order
of magnitude more than everything the first screen actually shows.

Measure it with no browser and no server, by timing the phases separately:

```python
import time

t0 = time.perf_counter()
import app                            # module scope: imports + any module-level data load
t1 = time.perf_counter()
dashboard = app.MyDashboard()         # construction: widgets, watchers, initial reloads
t2 = time.perf_counter()
print(f"import {t1 - t0:.2f}s  construct {t2 - t1:.2f}s")
```

Then time the individual data calls the constructor makes, and weigh each against how much
of the first screen it feeds. Anything expensive that the first screen does not show is the
thing to move. Defer it to first use, keyed so it runs once and only when its inputs change:

```python
def _on_tab(self, active):            # wired via self._tabs.param.watch(..., "active")
    if active == EXPENSIVE_TAB:
        self._ensure_expensive(force=True)

def _ensure_expensive(self, force):
    key = (self.source, self.window)
    if key == self._expensive_key:
        return                        # already computed for these inputs
    if not (force or self._tabs.active == EXPENSIVE_TAB):
        return                        # still unseen — leave it stale, opening the tab computes it
    self._pane.loading = True         # the wait is now visible, and off the startup path
    try:
        self._data = expensive_aggregate(*key)
    finally:
        self._pane.loading = False
    self._expensive_key = key
```

Re-measure after each change, and keep the number the way you keep the logs clean. Two
things distort the reading:

- **`--dev` reloads are warm.** A reload re-executes the module, so `@pn.cache` entries and
  module-level data are rebuilt — but the OS file cache and any live HTTP session are not
  cold. Measure a true cold start with the script above, or a plain `panel serve`.
- **Network-bound loads vary run to run.** Time them apart from computation so one unlucky
  fetch doesn't get misread as slow code.

## Layout Linting

Before reaching for a screenshot, run `scripts/layout_lint.py` against the served URL — it loads the page in a real headless browser at three widths (1400/768/390 by default) and inspects the rendered DOM/CSSOM as text, the same way `preflight.py` inspects source as text:

```bash
python scripts/layout_lint.py http://localhost:5007/app_name
```

It checks viewport overflow, touch targets under 44px, WCAG text contrast under 4.5:1, unintentional element overlap, siblings that should share a left edge but don't, and font-size sprawl (informational). Exits 0 with no output if clean; otherwise prints one line per violation, e.g. `[768px] [TOUCH_TARGET_TOO_SMALL] ...`. Resolve the script path the same way as `preflight.py` — relative to wherever this file was read from, not the app's own working directory. `scripts/test_layout_lint.py` is its check suite, built the same way as `test_preflight.py` (hand-built WRONG/CORRECT fixtures) — run from inside `scripts/`.

This is the DOM-as-text replacement for the majority of what a screenshot is otherwise needed for: geometry and contrast are numbers, not judgment calls, so read them directly instead of looking at a picture. What it does **not** replace: hierarchy, whitespace rhythm, whether the page reads as an untouched template — anything requiring taste rather than a threshold. Reach for a screenshot ([below](#screenshotting-with-playwright)) for those.

## Inspecting the Plot Model

Layout lint reads the DOM as text; the same move works one level in, on the chart itself. For
HoloViews/hvPlot output, most "is this plot right?" questions have numeric answers you can read
server-side, with no browser and no served app. `hv.render` returns the Bokeh figure:

```python
import holoviews as hv

state = hv.render(overlay, backend="bokeh")     # bokeh.plotting figure
state.x_range.start, state.x_range.end          # the actual axis range
len(state.renderers)                            # one per layer — did every element survive?
[t.__class__.__name__ for t in state.toolbar.tools]
state.toolbar.autohide, state.toolbar_location
```

Reach for it to answer, deterministically:

- **Is the range what I think it is?** A degenerate range is the usual cause of a plot that
  draws its chrome — title, legend, toolbar — and no data. An element with no rows yields
  exactly `(0, 1)`, which on a Web Mercator tile map is a one-metre extent; Bokeh then logs
  `tile extent is not fully defined`, fails to set initial ranges, and the figure never
  recovers. Seeing `(0, 1)` in Python names that instantly.
- **Did every layer survive composition?** Compare `len(state.renderers)` with the number of
  elements you overlaid. A tile source counts as one. This catches a layer dropped by an
  `.opts()` mistake, which a picture shows only as "something missing".
- **Did an option actually apply?** Options set on the wrong level of a composite frequently
  don't stick (see [Decluttering Plots](../holoviews/decluttering-plots.md#apply-at-the-top-level)).
  Read it off the model instead of inferring it from pixels.

Note that HoloViews computes ranges eagerly and hands Bokeh a `Range1d` even when you set no
`xlim`, so the range *type* tells you little — it's the start/end values that carry the signal.
Assert on them in a headless test (see [Decouple from the Backend](#decouple-from-the-backend))
so a fix stays fixed.

**What this does not tell you.** It verifies the *model*, not the render. A plot can be provably
well formed server-side and still draw nothing in the browser: a `responsive=True` figure laid
out at zero width inside tabs yields correct bounds and a correct renderer count while showing
an empty frame. So when the model checks out and the chart is still wrong, the remaining
information is client-side — read the browser JS console, where Bokeh logs layout and tile
failures, before spending another screenshot. A screenshot of a blank plot looks the same
whatever the cause, which makes it the weakest evidence available at exactly the moment it's
most tempting.

## Screenshotting with Playwright

Screenshots are the expensive step — each one launches a headless browser and adds an image to review. Use them deliberately, not as the default per-edit feedback. Use the code below for an app served from a file; for a self-contained snippet, panel-live-server's [`screenshot` tool](#verifying-with-panel-live-server) gets the same picture with none of the wait-condition boilerplate.

Take a screenshot of a running Panel app to review layout without manual browser interaction:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:5007/app_name", wait_until="networkidle")
    # defer_load / loading_indicator (and any pane with loading=True) overlay a
    # spinner on a grey box until content renders — a fixed sleep races it and
    # captures the spinner. Wait for every Panel loading overlay to clear.
    page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=30000)
    page.wait_for_timeout(300)  # brief settle for final paint
    page.screenshot(path="/tmp/screenshot.png")
    browser.close()
```

Don't rely on a fixed `wait_for_timeout` for render — it's the usual cause of a screenshot showing a half-loaded app (see [Common Errors](#common-errors)).

For multi-step flows, use `wait_until` from `panel.tests.util` to wait for state changes instead of fixed timeouts:

```python
from playwright.sync_api import sync_playwright
from panel.tests.util import wait_until

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:5007/app_name", wait_until="networkidle")
    page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=30000)
    page.screenshot(path="/tmp/step1.png")

    # Wait for button to be enabled before clicking
    wait_until(lambda: page.locator("text=Continue").is_enabled(), page)
    page.click("text=Continue")

    # Wait for the next step to finish rendering (spinner cleared) before capture
    page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=30000)
    page.screenshot(path="/tmp/step2.png")

    browser.close()
```

The `wait_until(fn, page)` function polls the callback until it returns `True` or times out (default 5s). Pass the `page` fixture to use Playwright's timeout instead of `time.sleep`.

### When to Screenshot

Screenshot when the feedback you need is genuinely visual, for example:

- After the logs are clean and you want to confirm the app actually renders
- When debugging a layout, styling, or positioning issue that logs can't reveal
- After a multi-step interaction, to verify the resulting UI state
- As a final check before handing the app back

Skip the screenshot when:

- You just made an edit and haven't checked the logs yet — read the logs first
- The change is non-visual (data wrangling, param names, callbacks) — a headless smoke test (see [Decouple from the Backend](#decouple-from-the-backend)) confirms behavior without a browser
- The issue is geometry or contrast (overflow, touch targets, misalignment, WCAG contrast) — [layout lint](#layout-linting) catches these as text, faster and cheaper than a screenshot
- The question is whether a chart is well formed — axis ranges, missing layers, options that didn't apply — [inspect the plot model](#inspecting-the-plot-model) instead; and if a plot renders blank, check the browser console before screenshotting it again, since every cause looks identical in the image
- A traceback is already in the logs — fix that first; the screenshot will only show an error page

When you do capture multiple states, batch them into a single Playwright session (as above) rather than launching a browser per shot.

## Common Errors

Init-ordering failures (`on_init` `AttributeError`; the "widgets move but nothing updates" dead app) and per-component silent bugs (radio `default=None`, `Selector.objects`, date comparisons) are symptom-indexed in [Troubleshooting Panel Apps](troubleshooting.md). The error specific to *this* screenshot loop:

### Screenshot shows a loading spinner

A grey box with a spinner (often over a chart) means the capture beat the render — you waited on a fixed `wait_for_timeout` instead of the app's actual loading state. `defer_load=True`, `loading_indicator=True`, and any pane with `loading=True` add the `pn-loading` class to an overlay while content renders, then remove it once done. Wait for that to clear rather than guessing a duration:

```python
page.goto(url, wait_until="networkidle")
page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=30000)
```

For plots that draw to a `<canvas>` (Bokeh/HoloViews), `page.wait_for_selector("canvas")` is another good signal. Raise the timeout when the data source is slow.
