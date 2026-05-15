# Using Pytest Playwright

Test custom Panel components in a real browser with Playwright.

## Contents

- [Key Utilities](#key-utilities)
- [Complete Example](#complete-example)
- [Key Patterns](#key-patterns)
- [External Resources](#external-resources)
- [Running Tests](#running-tests)

## Key Utilities

- `serve_component(page, component)` — serves component, navigates browser. Returns `(msgs, port)`.
- `wait_until(fn, page, timeout=5000)` — polls callback until it returns `True` or times out. Essential for JS → Python sync.
- `async_wait_until(fn, page, timeout=5000)` — async version for async tests.

### wait_until

The callback can return `True`/`False`, or use an `assert` (returns `None` on success):

```python
# Lambda returning bool
wait_until(lambda: component.value == expected, page)

# Function with assert
def check_state():
    assert len(feed.objects) == 3
    assert feed.objects[-1].object == "Done"
wait_until(check_state, page)
```

Always pass `page` in Playwright tests — it uses `page.wait_for_timeout()` instead of `time.sleep()` to avoid stale state.

## Complete Example

```python
import pytest
pytest.importorskip("playwright")

import panel as pn
import param
from panel.custom import JSComponent
from panel.tests.util import serve_component, wait_until
from playwright.sync_api import expect

pytestmark = pytest.mark.ui

DEFAULT_TIMEOUT = 2_000
LOAD_TIMEOUT = 5_000


class CounterButton(JSComponent):
    value = param.Integer(default=0)
    _esm = """
    export function render({ model, el }) {
        const button = document.createElement('button');
        button.id = 'counter-btn';
        function update() { button.textContent = `Count: ${model.value}`; }
        button.onclick = () => { model.value += 1; };
        model.on('value', update);
        update();
        el.appendChild(button);
    }
    """


class TextInput(JSComponent):
    value = param.String(default="")
    _esm = """
    export function render({ model, el }) {
        const input = document.createElement('input');
        input.id = 'text-input';
        input.type = 'text';
        input.value = model.value;
        input.oninput = (e) => { model.value = e.target.value; };
        model.on('value', () => { if (input.value !== model.value) input.value = model.value; });
        el.appendChild(input);
    }
    """


# CRITICAL: Always include — resets threaded Panel servers so pytest exits cleanly
@pytest.fixture(autouse=True)
def server_cleanup():
    try:
        yield
    finally:
        pn.state.reset()


# CRITICAL: Always include — verifies Panel/Bokeh infrastructure works
def test_no_console_errors(page):
    msgs, _ = serve_component(page, CounterButton(value=0))
    info_messages = [m for m in msgs if m.type == "info"]
    assert any("document idle" in m.text.lower() for m in info_messages)
    real_errors = [m for m in msgs if m.type == "error" and "favicon" not in m.text.lower()]
    assert len(real_errors) == 0, f"JS errors: {[m.text for m in real_errors]}"


def test_component_renders(page):
    serve_component(page, CounterButton(value=42))
    expect(page.locator("#counter-btn")).to_have_text("Count: 42", timeout=LOAD_TIMEOUT)


def test_js_to_python_sync(page):
    text_input = TextInput(value="")
    serve_component(page, text_input)
    page.locator("#text-input").fill("Hello World")
    wait_until(lambda: text_input.value == "Hello World", page)


def test_python_to_js_sync(page):
    counter = CounterButton(value=10)
    serve_component(page, counter)
    expect(page.locator("#counter-btn")).to_have_text("Count: 10", timeout=LOAD_TIMEOUT)
    counter.value = 99
    expect(page.locator("#counter-btn")).to_have_text("Count: 99", timeout=DEFAULT_TIMEOUT)


def test_bidirectional_sync(page):
    counter = CounterButton(value=5)
    serve_component(page, counter)
    expect(page.locator("#counter-btn")).to_have_text("Count: 5", timeout=LOAD_TIMEOUT)
    page.locator("#counter-btn").click()
    wait_until(lambda: counter.value == 6, page)
    counter.value = 100
    expect(page.locator("#counter-btn")).to_have_text("Count: 100", timeout=DEFAULT_TIMEOUT)
```

## Key Patterns

| Pattern | Code |
|---|---|
| Serve component | `msgs, port = serve_component(page, component)` |
| Assert text | `expect(locator).to_have_text("text", timeout=X)` |
| Wait for Python state | `wait_until(lambda: condition, page)` |
| User interaction | `page.locator("#id").click()` / `.fill("text")` |

## External Resources

Components loading CDN libraries need longer timeouts and explicit dimensions:

```python
def test_external_resource(page):
    viewer = ModelViewer(src="https://example.com/model.glb", style={"min-height": "400px"})
    serve_component(page, viewer)
    expect(page.locator("#model-viewer")).to_be_visible(timeout=5_000)
```

## Running Tests

```bash
pytest path/to/test_file.py -n auto        # parallel (recommended)
pytest path/to/test_file.py -x             # sequential, stop on first failure
pytest path/to/test_file.py --headed --slowmo 500  # debug mode
```