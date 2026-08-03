# Iterating on Panel Apps

Agentic workflow for developing and debugging Panel apps. For agents with shell access: run a static preflight check before first serve, serve with logging, iterate by reading logs after each edit, and screenshot with Playwright only when you need to verify something visual — all without requiring user intervention.

## Contents

- [Development Loop](#development-loop)
- [Decouple from the Backend](#decouple-from-the-backend)
- [Serving with Logs](#serving-with-logs)
- [Screenshotting with Playwright](#screenshotting-with-playwright)
  - [When to Screenshot](#when-to-screenshot)
- [Common Errors](#common-errors)

## Development Loop

0. **Preflight** the code before the first serve: `python scripts/preflight.py app.py`. This is a static, dependency-free check for the mechanical anti-patterns already documented in [Reviewing Panel Apps](reviewing-panel-apps.md) and [Troubleshooting](troubleshooting.md) — flicker-causing `@param.depends` returns, `from_param` before `super()`, missing `pn.io.hold()`, mutated params, `Radio*Group` defaults, missing `throttled`. It costs nothing and catches most bugs before a server is even running, so run it before spending a log-tail cycle or a screenshot on something greppable.
1. **Serve** the app once with logs captured to a file — the `--dev` flag auto-reloads on file changes, so you don't restart per edit
2. **Edit** the code to fix issues
3. **Check logs** for Python errors after each edit (tracebacks show invalid params and valid options) — this is fast and cheap, so do it every iteration
4. **Repeat** edit + log check until the logs are clean
5. **Screenshot** with Playwright only when you need to confirm something visual (see [when to screenshot](#when-to-screenshot)), then **review** the image for layout/styling issues

Drive iteration from preflight and the logs, not from screenshots. Reach for a screenshot at milestones — once preflight is clean and the logs are clean, when debugging a specifically visual problem, or for a final check — not on every edit.

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

## Screenshotting with Playwright

Screenshots are the expensive step — each one launches a headless browser and adds an image to review. Use them deliberately, not as the default per-edit feedback.

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
