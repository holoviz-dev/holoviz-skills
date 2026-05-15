# Iterating on Panel Apps

Agentic workflow for developing and debugging Panel apps. For agents with shell access: serve with logging, screenshot with Playwright, review the image, and iterate without requiring user intervention.

## Contents

- [Development Loop](#development-loop)
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

Run all screenshot checks inside a **single browser session** to avoid repeated launch overhead. Open one page per test scenario, capture, then close at the end:

```python
from playwright.sync_api import sync_playwright
from panel.tests.util import wait_until

BASE = "http://localhost:5007"

tests = [
    # (url_path, output_path, optional_actions)
    ("/app_name", "/tmp/initial.png", None),
    ("/app_name", "/tmp/after_click.png", lambda page: page.click("text=Run")),
    ("/other_view", "/tmp/other_view.png", None),
]

with sync_playwright() as p:
    browser = p.chromium.launch()

    for path, out, action in tests:
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{BASE}{path}")
        page.wait_for_timeout(2000)          # initial render

        if action:
            action(page)
            page.wait_for_timeout(1000)      # settle after interaction

        page.screenshot(path=out, full_page=True)   # full_page captures content below the fold
        print(f"saved {out}")
        page.close()

    browser.close()
```

**`full_page=True`** is important for Panel apps — the default viewport height (900 px) often clips timeline groups, opportunity tables, and other below-the-fold content.

For interactions that depend on app state rather than fixed delays, replace `wait_for_timeout` with `wait_until`:

```python
# Wait for a button to become enabled before clicking
wait_until(lambda: page.locator("text=Continue").is_enabled(), page)
page.click("text=Continue")
page.screenshot(path="/tmp/step_after_continue.png", full_page=True)
```

`wait_until(fn, page)` polls until the callback returns `True` or the default 5 s timeout expires. Prefer it over `time.sleep` so tests fail fast instead of hanging.

### Scroll into view before clicking

Elements that exist in the DOM but are outside the visible area will fail to click. Always call `scroll_into_view_if_needed()` before interacting with anything that might be off-screen:

```python
el = page.locator("text=Danaher").first
el.scroll_into_view_if_needed()
el.click()
```

This is especially relevant when looping over cards or rows — earlier interactions can shift layout and push later targets out of the viewport.

### Check logs between test steps

Add a log tail after each action to catch server-side errors that don't appear in the screenshot:

```python
import subprocess

def check_logs(label=""):
    out = subprocess.run(["tail", "-5", "/tmp/panel.log"], capture_output=True, text=True)
    if "Error" in out.stdout or "Traceback" in out.stdout:
        print(f"[{label}] SERVER ERROR:\n{out.stdout}")
    else:
        print(f"[{label}] logs clean")

# Use between steps:
page.click("text=Load briefing")
page.wait_for_timeout(2000)
check_logs("after load briefing")
page.screenshot(path="/tmp/enriched.png", full_page=True)
```

## Common Errors

### on_init=True AttributeError

```
AttributeError: 'MyViewer' object has no attribute '_some_widget'
```

`@param.depends(..., on_init=True)` watchers fire during `super().__init__()`. Create any panes they reference *before* the `super().__init__(**params)` call.

### Selector with default=None

Radio widgets (`RadioBoxGroup`, `RadioButtonGroup`) visually highlight the first option even when `value=None`. Clicking that option doesn't fire a change event — users can't select the first option and `@param.depends` callbacks never trigger. Always set a real default value for radio widgets.
