# Iterating on Panel Apps

Agentic workflow for developing and debugging Panel apps. For agents with shell access: serve with logging, screenshot with Playwright, review the image, and iterate without requiring user intervention.

## Contents

- [Development Loop](#development-loop)
- [Decouple from the Backend](#decouple-from-the-backend)
- [Serving with Logs](#serving-with-logs)
- [Screenshotting with Playwright](#screenshotting-with-playwright)
- [Common Errors](#common-errors)

## Development Loop

1. **Serve** the app with logs captured to a file
2. **Screenshot** with Playwright to see the current state
3. **Review** the screenshot for layout/styling issues
4. **Check logs** for Python errors (tracebacks show invalid params and valid options)
5. **Edit** the code to fix issues
6. **Repeat** — the `--dev` flag auto-reloads on file changes

## Decouple from the Backend

When the app reads from a slow or unavailable backend (a database, an internal service, an external API), put data access behind a small source interface and inject a **mock source** via an env flag. You can then serve, screenshot, and test the full UI without the live system.

```python
class BaseSource:
    def list_items(self): ...
    def load(self, key): ...

class MockSource(BaseSource):   # synthetic rows + tiny inline assets
    ...

SOURCE = MockSource() if os.environ.get("APP_MOCK") == "1" else LiveSource()
```

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

Take screenshots of a running Panel app to review layout without manual browser interaction:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:5007/app_name")
    page.wait_for_timeout(3000)  # Wait for render
    page.screenshot(path="/tmp/screenshot.png")
    browser.close()
```

For multi-step flows, use `wait_until` from `panel.tests.util` to wait for state changes instead of fixed timeouts:

```python
from playwright.sync_api import sync_playwright
from panel.tests.util import wait_until

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:5007/app_name")
    page.wait_for_timeout(2000)
    page.screenshot(path="/tmp/step1.png")

    # Wait for button to be enabled before clicking
    wait_until(lambda: page.locator("text=Continue").is_enabled(), page)
    page.click("text=Continue")

    # Wait for next step to render
    page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/step2.png")

    browser.close()
```

The `wait_until(fn, page)` function polls the callback until it returns `True` or times out (default 5s). Pass the `page` fixture to use Playwright's timeout instead of `time.sleep`.

## Common Errors

### on_init=True AttributeError

```
AttributeError: 'MyViewer' object has no attribute '_some_widget'
```

`@param.depends(..., on_init=True)` watchers fire during `super().__init__()`. Create any panes they reference *before* the `super().__init__(**params)` call.

### Selector with default=None

Radio widgets (`RadioBoxGroup`, `RadioButtonGroup`) visually highlight the first option even when `value=None`. Clicking that option doesn't fire a change event — users can't select the first option and `@param.depends` callbacks never trigger. Always set a real default value for radio widgets.
