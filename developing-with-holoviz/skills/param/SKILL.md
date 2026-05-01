---
name: param
description: Define Python classes with typed, validated, reactive parameters using Param. Use when building classes with constrained attributes, reactive dependencies between values, or dynamic option cascading. Load alongside the Panel skill for any Panel app using Parameterized classes.
metadata:
  version: "1.0.0"
  author: holoviz
---

# Using Param effectively

Correct patterns and common pitfalls for Param — the reactive parameter library that underpins Panel, HoloViews, and the HoloViz ecosystem.

## Parameterized Classes

Notes:
1. Add `# pyright: reportAssignmentType=false` at the top — Param's descriptors conflict with static type checkers.
2. Add type annotations (`target: str = param.String(...)`) for IDE autocomplete — Param doesn't enforce them at runtime.
3. **Never use `name` as a parameter** — reserved by Param for the instance name.
4. `self.param.name` is the Parameter object; `self.name` is the current value. Use `self.param.name` with `.from_param()` and pane constructors.

```python
# pyright: reportAssignmentType=false
import param

class DataConfig(param.Parameterized):
    source: str = param.Selector(default="CSV", objects=["CSV", "Parquet", "SQL"], doc="Data source type")
    limit: int = param.Integer(default=1000, bounds=(1, 100_000), doc="Max rows to load")
    filters: list = param.List(default=[], item_type=str, doc="Column filters to apply")
```

## Reactive Dependencies (@param.depends)

Notes:
1. Without `watch=True`: lazy, called only when something reads the result. Returns content. With `watch=True`: eager, fires every time the parameter changes. Use for side effects only.
2. Don't use `watch=True` to update UI — causes flickering (the `panel` skill covers this).
3. `on_init=True` runs the method once at instantiation. Use with `watch=True` to set initial state.
4. A method without `watch=True` may run multiple times if multiple panes depend on it. Use `watch=True` to update a parameter instead, then bind panes to that parameter.

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

Notes:
1. When updating `.objects`, always check if the current value is still valid — reset it if not.

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

Notes:
1. `param.update()` applies multiple changes atomically — watchers fire once, not once per change. Also works as a context manager: `with self.param.update(): self.x = 1; self.y = 2`.
2. Use the most specific type (`param.Integer` not `Number`, `param.Selector` not `String`). Specificity drives widget selection in Panel's `.from_param()`.
3. `softbounds` suggests a range for UI sliders without hard enforcement. `step` hints the increment. `label` overrides the display name. `precedence` controls ordering (lower = first).
4. `param.List(item_type=str)` validates contents. `param.Dict` does not validate values.
5. `param.DataFrame()` accepts pandas only. For Polars, use `param.Parameter()`.
6. `param.Event()` resets to `False` after firing watchers. Use for "run now" buttons.
7. `default_factory` for mutable/dynamic defaults — without it, all instances share the same object. Alternative: `instantiate=True`.
8. Param does **not** auto-coerce types (unlike Pydantic). `param.Integer(value="25")` raises `ValueError`.

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

## .watch() vs @param.depends

`self.param.watch(callback, ["param_name"])` is the imperative equivalent of `@param.depends(watch=True)`. Prefer the decorator for methods on your own class. Use `.watch()` when: you're reacting to parameters on an instance you didn't define, you need to wire watchers conditionally at runtime, or you need the `Event` object (`.name`, `.old`, `.new`) for logging or undo logic.

```python
def on_change(event):
    print(f"{event.name}: {event.old} → {event.new}")

config = DataConfig()
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