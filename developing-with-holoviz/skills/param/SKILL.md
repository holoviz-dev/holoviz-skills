---
name: param
description: Define Python classes with typed, validated, reactive parameters using Param. Use when building classes with constrained attributes, reactive dependencies between values, or dynamic option cascading. Load alongside the Panel skill for any Panel app using Parameterized classes.
metadata:
  version: "1.0.2"
  author: holoviz
---

# Using Param

Correct patterns and common pitfalls for Param — the reactive parameter library that underpins Panel, HoloViews, and the HoloViz ecosystem.

## Contents

- [Parameterized Classes](#parameterized-classes)
- [Reactive Dependencies (@param.depends)](#reactive-dependencies-paramdepends)
- [Dependent Parameters](#dependent-parameters)
- [Parameter Types](#parameter-types)
- [Reactive Expressions (rx)](#reactive-expressions-rx)
- [.watch() vs @param.depends vs .link()](#watch-vs-paramdepends-vs-link)
- [allow_refs](#allow_refs)
- [Custom Parameter Types](#custom-parameter-types)

## Parameterized Classes

- Add `# pyright: reportAssignmentType=false` at the top — Param's descriptors conflict with static type checkers.
- Add type annotations (`target: str = param.String(...)`) for IDE autocomplete — Param doesn't enforce them at runtime.
- **Never use `name` as a parameter** — reserved by Param for the instance name.
- `self.param.param_key` is the Parameter object; `self.param_key` is the current value. Use `self.param.param_key` with `.from_param()` and pane constructors.

```python
# pyright: reportAssignmentType=false
import param

class DataConfig(param.Parameterized):
    source: str = param.Selector(default="CSV", objects=["CSV", "Parquet", "SQL"], doc="Data source type")
    limit: int = param.Integer(default=1000, bounds=(1, 100_000), doc="Max rows to load")
    filters: list = param.List(default=[], item_type=str, doc="Column filters to apply")
```

## Reactive Dependencies (@param.depends)

- Without `watch=True`: lazy, called only when something reads the result. Returns content. With `watch=True`: eager, fires every time the parameter changes. Use for side effects only.
- Don't use `watch=True` to update UI — causes flickering (the `panel` skill covers this).
- `on_init=True` runs the method once at instantiation. Use with `watch=True` to set initial state.
- A method without `watch=True` may run multiple times if multiple panes depend on it. Use `watch=True` to update a parameter instead, then bind panes to that parameter.

```python
import param

class Analysis(param.Parameterized):
    query: str = param.String(default="SELECT *")
    result = param.DataFrame()

    @param.depends("result")
    def summary(self):
        if self.result is None:
            return "No data loaded."
        return f"**{len(self.result)} rows**, {len(self.result.columns)} columns"

    @param.depends("query", watch=True, on_init=True)
    def _run_query(self):
        self.result = execute_query(self.query)
```

## Dependent Parameters

- When updating `.objects`, always check if the current value is still valid — reset it if not.

```python
import param

class CountrySelector(param.Parameterized):
    _countries = {
        "Europe": ["France", "Germany", "Spain"],
        "Asia": ["China", "Japan", "India"],
    }

    continent: str = param.Selector(default="Europe", objects=["Europe", "Asia"])
    country: str = param.Selector(default="France", objects=["France", "Germany", "Spain"])

    @param.depends("continent", watch=True, on_init=True)
    def _update_countries(self):
        countries = self._countries[self.continent]
        self.param.country.objects = countries
        if self.country not in countries:
            self.country = countries[0]
```

## Parameter Types

- `param.update()` applies multiple changes atomically on one object — watchers fire once, not once per change. Also works as a context manager: `with self.param.update(): self.x = 1; self.y = 2`.
- Use the most specific type (`param.Integer` not `Number`, `param.Selector` not `String`). Specificity drives widget selection in Panel's `.from_param()`.
- `softbounds` suggests a range for UI sliders without hard enforcement. `step` hints the increment. `label` overrides the display name. `precedence` controls ordering (lower = first).
- `param.List(item_type=str)` validates contents. `param.Dict` does not validate values.
- `param.DataFrame()` accepts pandas only. For Polars, use `param.Parameter()`.
- `param.Event()` resets to `False` after firing watchers. Use with `Button.from_param()` + `@param.depends(watch=True)` when you need a declarative trigger.
- **Single source of truth**: For navigation buttons (back/next), have handlers modify one shared parameter (e.g., `active_step`), then watch that parameter once. All UI state derives from one place.
- **Reassign, don't mutate**: In-place operations (`+=`, `list.append()`, `dict.update()`) don't trigger watchers. Always reassign: `self.x = self.x + 1`, `self.items = self.items + [new]`, `self.data = {**self.data, key: val}`.
- `default_factory` for mutable/dynamic defaults — without it, all instances share the same object. Alternative: `instantiate=True`.
- Param does **not** auto-coerce types (unlike Pydantic). `param.Integer(value="25")` raises `ValueError`.

```python
import uuid
import param

class TrackedItem(param.Parameterized):
    id: str = param.String(default_factory=lambda: str(uuid.uuid4()))
    tags: list = param.List(default=[], instantiate=True)
    temperature: float = param.Number(
        default=0.7, bounds=(0, 2), softbounds=(0, 1),
        step=0.1, label="LLM Temperature", precedence=1,
    )
    submit: bool = param.Event(doc="Trigger processing")

config = DataConfig()
config.param.update(source="Parquet", limit=500)  # one notification, not two

# Context manager form — useful when updating conditionally
with config.param.update():
    config.source = "SQL"
    config.limit = 200
```

For the `param.Event` + `Button.from_param()` + `@param.depends(watch=True)` button pattern, see the declarative example under [.watch() vs @param.depends vs .link()](#watch-vs-paramdepends-vs-link).

## Reactive Expressions (rx)

`param.rx()` / `.rx()` creates reactive expressions that automatically update when dependencies change. **A `lambda` is to a Python function as `rx` is to `pn.bind`.** Use rx instead of lambdas and `pn.bind` for cleaner, more declarative code.

```python
import panel as pn

# ✅ Concise rx — replaces verbose pn.bind callback
button = pn.widgets.Button(name="Add " + select.param.value.rx())

# ❌ Verbose pn.bind equivalent
button = pn.widgets.Button(name=pn.bind(lambda x: f"Add {x}", select))
```

### Core Operations

```python
# Chain operations — indexing, slicing, methods all work
menu = MenuList(active=(0,))
step = menu.param.active.rx()[0]  # extract first element reactively

# Conditional with rx.where (replaces if/else lambdas)
bar_color = toggle.param.value.rx.where("success", "warning")

# Boolean operations
visible = items.param.value.rx.len() > 0
hidden = toggle.param.value.rx.not_()

# Transform with rx.pipe — passes value as first arg
formatted = value.rx.pipe(format_func, extra_arg)

# Side effects with rx.watch (use sparingly)
expr.rx.watch(callback_func)  # callback receives the value, not an event
```

### Syncing Parameters

For syncing widget parameters to class parameters, use `pn.bind(..., watch=True)`:

```python
class Wizard(pn.viewable.Viewer):
    active_step = param.Integer(default=0)

    def __init__(self, **params):
        self._menu = MenuList(items=[...], active=(0,))
        pn.bind(self._on_menu_select, self._menu.param.active, watch=True)
        super().__init__(**params)

    def _on_menu_select(self, active):
        if active and active[0] != self.active_step:
            self.active_step = active[0]
```

Avoid `allow_refs=True` with rx binding (`self.x = widget.param.value.rx()`) when you also need to directly assign to that parameter — the binding breaks on direct assignment.

### Gotchas

- **Update via namespace**: `expr.rx.value = new_value` — direct assignment `expr = new_value` breaks reactivity
- **Accessor vs method**: `.rx.value` gets current value, `.rx()` returns reactive expression for chaining
- **String concat**: `"prefix " + widget.param.value.rx()` works; for complex cases wrap literals with `pn.rx("text")`
- **Dict access for conflicts**: Use `obj.param["objects"].rx.len()` when parameter name conflicts with rx methods

## .watch() vs @param.depends vs .link()

Reactive wiring, most to least preferred:

1. **`@param.depends("p1", "p2")` (no `watch`)** — pure; returns content for display, no side effects. Use whenever a value or pane is *derived* from params.
2. **`@param.depends("p", watch=True)`** — a side effect (update another param, sync state) driven by the object's *own* params. Declarative, no `event` argument.
3. **`pn.bind(fn, obj.param.x, watch=True)`** — a side effect driven by *another* instance's param (e.g. a widget) where `@param.depends` can't reach. Still declarative; `fn` receives the value.
4. **`.param.watch(fn, "x")`** — last resort: when you need `.old`/`.new` (logging, undo), or must wire/unwire watchers conditionally at runtime.

`watch=True` in any form is for **side effects only** — never to produce content for display (that's option 1).

For syncing parameters between objects, use `.link()` or `.rx()`:

```python
# Direct property sync — no callback needed
text_input.link(markdown_pane, value='object')

# Bind parameter to rx expression (requires allow_refs=True)
class Wizard(param.Parameterized):
    active_step = param.Integer(default=0, allow_refs=True)

    def __init__(self, **params):
        self._menu = MenuList(items=[...], active=(0,))
        super().__init__(**params)
        self.active_step = self._menu.param.active.rx()[0]  # menu -> step sync
```

For inline reactive string formatting, prefer `.rx()` over a `pn.bind`/lambda callback — see [Reactive Expressions (rx)](#reactive-expressions-rx).

```python
# ✅ Preferred — declarative, no event argument
class Wizard(param.Parameterized):
    go_next = param.Event()
    step = param.Integer(default=0)

    @param.depends("go_next", watch=True)
    def _on_go_next(self):
        self.step = self.step + 1

# ❌ Avoid — imperative, requires event argument
def on_change(event):
    print(f"{event.name}: {event.old} → {event.new}")

config.param.watch(on_change, ["source", "limit"])
```

## allow_refs

`allow_refs=True` lets a parameter track another Parameter object, staying in sync automatically.

```python
import param

class Source(param.Parameterized):
    value: int = param.Integer(default=10)

class Consumer(param.Parameterized):
    input_value: int = param.Integer(default=0, allow_refs=True)

source = Source()
consumer = Consumer(input_value=source.param.value)
source.value = 20
print(consumer.input_value)  # 20
```

## Custom Parameter Types

Subclass and override `_validate_value`. Always call `super()._validate_value()` first.

```python
import param

class EvenInteger(param.Integer):
    def _validate_value(self, val, allow_None):
        super()._validate_value(val, allow_None)
        if val is not None and val % 2 != 0:
            raise ValueError(f"Must be even, got {val!r}.")
```
