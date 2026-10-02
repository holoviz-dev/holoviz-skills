# Reproducing Browser Bugs

A Playwright script an agent runs to confirm a bug that only shows up in the
browser, such as a rendering glitch, a broken interaction or a JavaScript error.
Unlike the paste-and-run snippet in the [minimal-example skill](SKILL.md), it
takes a screenshot at each step and checks for the bug in code, so the same
script reports the bug on `main` and reports it gone on the fix branch. The
reproducer traps in that skill still apply to the app inside the script.

## 1. Understand the Bug

Read a GitHub issue, given as a URL or number, with:

```bash
gh issue view <number> --repo holoviz/<repo> --json title,body,comments
```

Use a description as given. With neither, use the bug already under
discussion in the conversation rather than asking the user to restate it.

Ask only for what's still missing to trigger the bug, then pull out the
description, code snippets, steps to reproduce, and expected versus actual
behavior.

## 2. Create the MRE Directory

```
.mre/<id>_<slug>/
├── reproduce_<id>.py
└── step*.png        (written when the script runs)
```

`<id>` is the issue number when there is one, otherwise a short slug for the
bug. Create it at the root of the repo you're debugging, and ignore `.mre/`
locally through git's exclude file, which leaves the repo's `.gitignore` alone.
Ask git for that file's path, because in a worktree `.git` is a file rather than
a directory. Then install Chromium through the interpreter that will run the
script, so the browser matches that environment's Playwright version; it skips
the download when the browser is already there:

```bash
mkdir -p .mre/<id>_<slug>
exclude="$(git rev-parse --git-path info/exclude)"
grep -qx '.mre/' "$exclude" || echo '.mre/' >> "$exclude"
python -m playwright install chromium
```

## 3. Script Structure

```python
"""
Playwright reproducer for <TITLE>

<ISSUE_URL — omit this line if there is no issue>

Run with: python reproduce_<ID>.py

The bug: <ONE_LINE_DESCRIPTION>
"""

import os
import time
from pathlib import Path

import holoviews as hv
import panel as pn
from playwright.sync_api import sync_playwright

hv.extension("bokeh")
pn.extension()

SCREENSHOT_DIR = Path(__file__).parent


def create_app():
    """Create minimal app that demonstrates the bug.

    Use EXACT code from the issue/description when possible, or simplify
    while preserving the bug trigger conditions.
    """
    # ... app setup
    return app


def main():
    print("=" * 60)
    print("Reproducer for <TITLE>")
    print("<SHORT_DESCRIPTION>")
    print("=" * 60)

    port = 5006
    server = pn.serve(create_app(), port=port, show=False, threaded=True)
    time.sleep(2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=os.environ.get("MRE_HEADLESS", "1") != "0",
                slow_mo=100,
            )
            page = browser.new_page()
            page.goto(f"http://localhost:{port}")

            # Bokeh renders inside Shadow DOM, which Playwright's CSS selectors pierce.
            # Wait on .bk-Canvas (capitalized), not .bk-canvas or .bk-events, and take
            # .first: a layout has one per plot, and wait_for() raises on several matches.
            page.locator(".bk-Canvas").first.wait_for(state="visible", timeout=15000)
            time.sleep(2)

            # === STEP 1: Initial State ===
            print("\n--- Step 1: Initial state ---")
            page.screenshot(path=str(SCREENSHOT_DIR / "step1_initial.png"))
            # Capture/print relevant state

            # === STEP 2: Trigger the Bug ===
            print("\n--- Step 2: <ACTION_DESCRIPTION> ---")
            # Interact with the page:
            # page.locator('button:text("Click")').click()
            # page.mouse.click(x, y)
            # page.keyboard.press("Enter")
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOT_DIR / "step2_action.png"))

            # === STEP 3: Verify Bug ===
            print("\n--- Step 3: Check for bug ---")
            page.screenshot(path=str(SCREENSHOT_DIR / "step3_result.png"))

            # Bug detection - adapt to your specific bug
            bug_detected = check_for_bug(page)

            print("\n" + "=" * 60)
            if bug_detected:
                print("BUG CONFIRMED!")
                print("  - <DESCRIBE_WHAT_IS_WRONG>")
            else:
                print("Bug not detected (may be fixed)")
            print("=" * 60)

            print(f"\nScreenshots saved in: {SCREENSHOT_DIR}")
            time.sleep(2)
            browser.close()
    finally:
        server.stop()

    print("\nDone.")


def check_for_bug(page):
    """Programmatically verify the bug exists.

    Return True if bug is present, False if not.
    """
    # Example: Check via JavaScript
    # result = page.evaluate("() => { return someCheck(); }")
    # return result["buggy_condition"]

    # Example: Check DOM state
    # element = page.locator(".problematic-element")
    # return element.is_visible() when it shouldn't be

    return False


if __name__ == "__main__":
    main()
```

## 4. Common Interaction Patterns

**Click buttons/elements:**

```python
page.locator('button:text("Submit")').click()
page.locator('[data-testid="my-button"]').click()
page.locator('input[type="checkbox"]').check()
```

**Mouse interactions:**

```python
bbox = page.locator(".canvas").bounding_box()
page.mouse.click(bbox["x"] + 100, bbox["y"] + 100)
page.mouse.dblclick(x, y)
page.mouse.move(x, y)
page.mouse.down()
page.mouse.up()
```

**Keyboard:**

```python
page.keyboard.press("Enter")
page.keyboard.type("text")
page.locator("input").fill("value")
```

**Wait for state** (CSS selectors pierce Bokeh's Shadow DOM either way; take
`.first` when several elements match, since a locator action raises on more
than one):

```python
page.locator(".element").first.wait_for(state="visible")
page.wait_for_selector(".element")
page.wait_for_timeout(500)
```

## 5. Bug Detection Patterns

**JavaScript inspection for Bokeh renderers:**

```python
GET_RENDERERS_JS = """() => {
    const doc = window.Bokeh?.documents?.[0];
    if (!doc) return {error: 'No Bokeh document'};

    const renderers = [];
    for (const model of doc._all_models.values()) {
        if (model.type === 'GlyphRenderer') {
            let dataLen = 0;
            if (model.data_source?.data) {
                const keys = Object.keys(model.data_source.data);
                if (keys.length > 0) {
                    dataLen = model.data_source.data[keys[0]].length;
                }
            }
            renderers.push({
                name: model.name || 'unnamed',
                visible: model.visible,
                glyph_type: model.glyph?.type || 'unknown',
                data_length: dataLen
            });
        }
    }
    return {renderers: renderers};
}"""

result = page.evaluate(GET_RENDERERS_JS)
# Check renderer visibility states
patches_hidden = any(
    r["glyph_type"] == "Patches" and not r["visible"] for r in result["renderers"]
)
```

**DOM-based checks:**

```python
element = page.locator(".should-be-hidden")
bug_detected = element.is_visible()  # Bug if visible when shouldn't be
```

**Screenshot comparison (visual bugs):**

```python
import numpy as np
from PIL import Image


# Pixel-diff two screenshots — large diff means rendering changed (e.g. initial vs reset)
def screenshot_diff(path_a, path_b, threshold=10):
    a = np.array(Image.open(path_a).convert("RGB"))
    b = np.array(Image.open(path_b).convert("RGB"))
    diff = np.abs(a.astype(int) - b.astype(int)).max(axis=2)
    return int((diff > threshold).sum())


page.screenshot(path="before.png")
# ... trigger action ...
page.screenshot(path="after.png")
diff = screenshot_diff("before.png", "after.png")
bug_detected = diff > 5000  # tune threshold to the expected change size
```

**DOM queries inside Bokeh Shadow DOM:**

Bokeh renders inside a Shadow DOM. `page.locator()` CSS selectors auto-pierce
Shadow DOM; `page.evaluate()` JS does not. To query the DOM from JS you must
walk `shadowRoot` manually:

```python
# Works — locator() pierces Shadow DOM automatically (.first: one per plot)
page.locator(".bk-tool-icon-reset").first.click()
canvas_bb = page.locator(".bk-Canvas").first.bounding_box()

# Fails — querySelectorAll does not pierce Shadow DOM
# page.evaluate("() => document.querySelectorAll('.bk-Canvas').length")  # returns 0

# Works — walk shadowRoot in JS
all_text = page.evaluate("""() => {
    function collect(root) {
        const texts = [];
        root.querySelectorAll('text').forEach(t => texts.push(t.textContent.trim()));
        root.querySelectorAll('*').forEach(el => {
            if (el.shadowRoot) texts.push(...collect(el.shadowRoot));
        });
        return texts;
    }
    return collect(document);
}""")
```

Bokeh model data is on `window.Bokeh.documents[0]._all_models` (not in the
DOM), so `page.evaluate()` works fine for inspecting model state without
touching the Shadow DOM.

## 6. What Makes a Good Browser Reproducer

The traps in the [minimal-example skill](SKILL.md) cover keeping it minimal,
self-contained and faithful to the issue's code. On top of those:

- Screenshot every step, so a reader can see the bug without running anything.
- Let `check_for_bug` decide rather than the screenshots. It should return
  `True` on `main` and `False` with the fix, or the script can't confirm one.

## 7. After Creating

1. Run the script and check that it reproduces the bug.
2. Check that the screenshots show the problem clearly.
3. Confirm that `check_for_bug` returns `True`.
4. Show the user the output and screenshots.
5. Once there's a fix, rerun it on that branch. It should report the bug gone,
   and the before and after screenshots are the old-versus-new visuals the
   [pr-description skill](../pr-description/SKILL.md) asks for. Turn the check
   into a regression test per the [testing skill](../testing/SKILL.md); Panel's
   UI-test helpers (`serve_component`, `wait_until`) are in the panel skill's
   Using Pytest Playwright reference.

End with a command the user can paste to watch it run in a visible browser:

```bash
MRE_HEADLESS=0 python .mre/<id>_<slug>/reproduce_<id>.py
```
