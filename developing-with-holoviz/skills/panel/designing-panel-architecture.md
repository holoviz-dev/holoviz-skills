# Designing Panel Architecture

How to build a Panel app that survives growth: composing the code into focused classes (design-time), and how the app behaves once served to real, multi-user load (runtime — sessions, state, caching, threading). The [Viewer Class Pattern](SKILL.md#viewer-class-pattern) covers a *single* `Viewer`; this picks up where one class stops being enough.

## Contents

Composition:

- [When to Reach for This](#when-to-reach-for-this)
- [The Composition Pattern](#the-composition-pattern)
- [Cross-Object Dependencies](#cross-object-dependencies)
- [The `from_data` Factory](#the-from_data-factory)
- [Sharing Derived Data](#sharing-derived-data)
- [Reactive Expressions (`pn.rx`)](#reactive-expressions-pnrx)
- [Computed Read-Only Params](#computed-read-only-params)
- [Wiring Shortcuts](#wiring-shortcuts)
- [Imperative vs Declarative](#imperative-vs-declarative)

Runtime and scale:

- [The Session Model](#the-session-model)
- [Server-Side State and Scheduling](#server-side-state-and-scheduling)
- [Streaming with Generators](#streaming-with-generators)
- [Caching](#caching)
- [Automatic Threading](#automatic-threading)
- [Profiling](#profiling)
- [Batching, Loading, and Memory](#batching-loading-and-memory)

## When to Reach for This

- Two or more views need the *same* filtered/derived data — don't recompute it in each.
- State (filter values, selection) is read and written by several components.
- A single `Viewer` is growing past ~150 lines or mixing data transforms with layout.

If none of these hold, stay with one `Viewer`.

## The Composition Pattern

Four roles, each its own class, wired by `param.ClassSelector`:

- **State** (`Filters`) — parameters only, plus its own widget panel. No data logic.
- **DataStore** — holds the raw `data` and a reference to the state; exposes derived data. No UI.
- **View** subclasses — presentation only; each reads from the shared `DataStore`.
- **App** — the shell that composes views and wraps them in `pmui.Page`.

```python
import panel as pn
import panel_material_ui as pmui
import param

pn.extension("tabulator", throttled=True)

class Filters(pn.viewable.Viewer):
    year = param.Range(default=(2010, 2020), bounds=(2000, 2025))
    manufacturers = param.ListSelector(default=[], objects=[])

    def __panel__(self):
        return pn.Param(
            self,
            parameters=["year", "manufacturers"],
            widgets={"manufacturers": {"type": pmui.MultiChoice}},
            width=320,
        )

class DataStore(param.Parameterized):            # plain Parameterized — no UI
    data = param.DataFrame()
    filters = param.ClassSelector(class_=Filters)

    @param.depends("data", "filters.year", "filters.manufacturers")
    def filtered(self):
        low, high = self.filters.year
        mask = self.data["year"].between(low, high)
        if self.filters.manufacturers:
            mask &= self.data["manufacturer"].isin(self.filters.manufacturers)
        return self.data.loc[mask]

class View(pn.viewable.Viewer):                  # shared base
    data_store = param.ClassSelector(class_=DataStore)

class Indicators(View):
    @param.depends("data_store.filtered")
    def __panel__(self):
        df = self.data_store.filtered()
        return pn.indicators.Number(name="Rows", value=len(df), format="{value:,.0f}")

class Table(View):
    def __panel__(self):
        return pn.widgets.Tabulator(
            self.data_store.filtered, pagination="remote", page_size=12,
            sizing_mode="stretch_width",
        )

class App(pn.viewable.Viewer):
    title = param.String(default="Wind Explorer")
    data_store = param.ClassSelector(class_=DataStore)
    views = param.List()

    def __panel__(self):
        main = pn.Column(*(view(data_store=self.data_store) for view in self.views))
        if pn.state.served:
            page = pmui.Page(title=self.title)
            page.sidebar.append(self.data_store.filters)
            page.main.append(main)
            return page
        return pn.Row(self.data_store.filters, main)

# Wire it up
df = make_data()
store = DataStore(data=df, filters=Filters.from_data(df))
App(data_store=store, views=[Indicators, Table]).servable()
```

The payoff: `DataStore.filtered()` is testable without rendering any UI, and one `DataStore` feeds every view — add a view by appending a class to `views`, nothing else.

## Cross-Object Dependencies

`@param.depends` accepts **dotted paths** to a sub-object's parameter, so a `DataStore` method can depend on its `Filters`' params:

```python
@param.depends("filters.year", "filters.manufacturers")   # sub-object params
def filtered(self): ...
```

A view then depends on the store's method by name: `@param.depends("data_store.filtered")`. This is what lets state, transform, and view live in separate classes yet stay reactive. The objects must be linked via `ClassSelector` (or passed at construction) for the path to resolve.

## The `from_data` Factory

Configure `.objects`/`.bounds` from data *outside* `__init__` with a classmethod, so the state class stays construction-agnostic and testable. Note the idiom: after setting `.objects`/`.bounds`, **assign the value to match** — otherwise the default falls outside the new options/bounds.

```python
@classmethod
def from_data(cls, df):
    f = cls()
    f.param.year.bounds = (int(df["year"].min()), int(df["year"].max()))
    f.year = f.param.year.bounds                       # assign value to match bounds
    f.param.manufacturers.objects = sorted(df["manufacturer"].unique().tolist())
    f.manufacturers = f.param.manufacturers.objects     # ...and objects
    return f
```

## Sharing Derived Data

Two ways to expose derived data from a `DataStore`:

- **Method + `@param.depends`** (above) — recomputed each time a consumer calls it. Simple; fine when one or two views read it.
- **Stored `param.DataFrame`** — when *many* components read the same derived frame, compute it once into a param with a `watch=True, on_init=True` watcher and have views depend on that param. Avoids recomputing the filter for every consumer.

```python
class DataStore(param.Parameterized):
    data = param.DataFrame()
    filters = param.ClassSelector(class_=Filters)
    filtered = param.DataFrame()                        # cached result, shared

    @param.depends("data", "filters.year", "filters.manufacturers",
                   watch=True, on_init=True)
    def _update_filtered(self):
        ...
        self.filtered = self.data.loc[mask]
```

## Reactive Expressions (`pn.rx`)

For declarative *data pipelines* — as opposed to `pn.bind`, which wires inputs to a function — `pn.rx` wraps a value (often a DataFrame) so ordinary operations build a reactive expression. Widgets become reactive refs via `widget.rx()`. Full guide: Param's [Reactive Expressions](https://param.holoviz.org/user_guide/Reactive_Expressions.html); the idioms below are the ones agents miss:

```python
rxdf = pn.rx(turbines)
view = rxdf[rxdf.p_year.between(*year.rx()) & rxdf.p_cap.between(*capacity.rx())][cols]
pn.widgets.Tabulator(view, pagination="remote", page_size=5)
```

Useful `.rx` methods (call a plain function or builtin reactively without unwrapping):

- `expr.rx.pipe(fn)` — apply an arbitrary function: `df.t_manu.unique().rx.pipe(list)`.
- `expr.rx.where(a, b)` — reactive ternary.
- `expr.rx.len()` — reactive `len()`.
- `pn.rx("# Hello {}").format(widget.param.value)` — reactive string formatting.

Reach for `pn.rx` when the transform reads naturally as an expression; reach for `pn.bind`/`@param.depends` when it's a function or method.

## Computed Read-Only Params

Mark a derived parameter `constant=True` so external code can't write it, then update it only inside `param.edit_constant`:

```python
class Calculator(param.Parameterized):
    left = param.Number(default=1)
    op = param.Selector(default="+", objects=["+", "-", "*", "/"])
    result = param.Number(default=0, constant=True)     # read-only to the outside

    @param.depends("left", "op", watch=True, on_init=True)
    def _calculate(self):
        with param.edit_constant(self):
            self.result = ...
```

## Wiring Shortcuts

Beyond `.from_param()` (see [Using Material UI](using-material-ui.md#key-differences-from-panel) for which widget matches each Param type):

- **Pass a `Parameter` or widget directly as a constructor arg** to bind it reactively — no callback:

  ```python
  card = pmui.Card(title=state.param.title, visible=state.param.visible)
  table = pn.widgets.Tabulator(df, page_size=self.param.page_size)
  ```

- **`widget.link(target, value="param_name")`** for one-way sync into another object's param when you only need one direction (cleaner than a manual `.param.watch`):

  ```python
  manufacturers_widget.link(filters, value="manufacturers")
  ```

## Imperative vs Declarative

Default to **declarative** (`@param.depends`, `pn.bind`, `pn.rx`) for data/UI derivations — easier to test and compose. Keep **imperative** `.param.watch` only for true side effects: logging, persisting settings, notifications.

```python
def log_filter_change(event):
    print(f"[filters] {event.name} -> {event.new}")

filters.param.watch(log_filter_change, ["year", "manufacturers"])
```

---

The rest covers runtime behavior once the app is served. It captures the **gotchas and when-to-use judgment** only — for full signatures and options, follow the linked Panel guides rather than relying on this page.

## The Session Model

Each browser tab that connects to a served app gets its own **session** backed by a separate Bokeh `Document`; the app code runs once per session.

- **Gotcha — module-level mutable globals are shared across all sessions.** A list, dict, or DataFrame created at module scope is one object for every user; mutating it leaks state between sessions. Keep per-user state on instances (your `Viewer`/`Parameterized` objects), and use `pn.state.cache` *only* for intentionally shared, read-mostly data.
- `pn.state` is the per-session runtime handle (`served`, `curdoc`, `session_args`, `cache`, scheduling, lifecycle). Don't stash per-user mutable state on it casually.

`panel serve app.py` (CLI) is the standard way to deploy; reach for `pn.serve(...)` only when you need to launch from inside Python. See Panel's [server guide](https://panel.holoviz.org/how_to/server/index.html).

## Server-Side State and Scheduling

Periodic callbacks, deferred execution (`pn.state.execute`), and session lifecycle hooks (`onload`, `on_session_created`/`on_session_destroyed`, `schedule_task`) all live on `pn.state` — see Panel's [Callbacks guide](https://panel.holoviz.org/how_to/callbacks/index.html). What agents get wrong:

- `pn.state.add_periodic_callback(fn, period=...)` — `period` is in **milliseconds**, and the returned handle must be `.stop()`-ed. Tie it to the session so it stops on disconnect.
- Use `pn.state.execute(fn)` to defer heavy work off a callback so the UI stays responsive instead of blocking until the handler returns.

## Streaming with Generators

For incremental feedback during long work, bind `pn.bind` to a **generator** (sync or async) — each `yield` replaces the rendered output, so you avoid manual callbacks and state flags. Full guide: [Binding generators](https://panel.holoviz.org/how_to/interactivity/bind_generators.html).

The one rule agents miss: **a bound generator may `yield` repeatedly but must never `return` a value** — use a bare `return` only to stop early.

```python
def runner(run):
    if not run:
        yield "Not run yet"; return        # bare return — no value
    for i in range(101):
        yield pn.Column(f"{i}%", pn.indicators.Progress(value=i))
    yield "Done ✅"

pn.Row(button, pn.bind(runner, button))
```

## Caching

Panel has three tiers (full API in the [Caching guide](https://panel.holoviz.org/how_to/caching/index.html)) — the choice is the part worth knowing:

- **`pn.state.cache`** — a plain process-global dict shared across sessions. For a one-time dataset load shared by everyone.
- **`pn.state.as_cached(key, fn, ttl=..., **kwargs)`** — same intent, no manual `if`-check; reruns only when the hashed `kwargs` change.
- **`@pn.cache`** — memoize a function on its arguments; reach for it when results depend on inputs (supports `ttl`, `max_items`, `policy`, `to_disk`, `per_session`).

Warm the cache before the first visitor with `panel serve --warm` (and `--setup script.py` to populate from a separate script).

## Automatic Threading

`pn.extension(nthreads=N)` dispatches every event onto a thread pool automatically — no manual thread management (details in the [Concurrency guide](https://panel.holoviz.org/how_to/concurrency/index.html)). The non-obvious bit: `nthreads=0` auto-sizes to `min(32, os.cpu_count() + 4)`. Use threading for CPU-bound callbacks; prefer `async`/`await` for I/O.

## Profiling

Profile a callback with `@pn.io.profile("name", engine=...)` (engines: `pyinstrument`, `snakeviz`, `memray`); results appear in the `/admin` dashboard (`panel serve --admin`). **The function is `pn.io.profile`, not `pn.io.profiler`** — a common hallucination.

## Batching, Loading, and Memory

- **Batch updates:** wrap multiple component assignments in `pn.io.hold()` so they trigger a single redraw instead of one per assignment.

  ```python
  with pn.io.hold():
      self.chart = new_chart
      self.table = new_table
      self.summary = new_summary
  ```

- **Defer heavy components:** `pn.extension(defer_load=True, loading_indicator=True)` renders the page first and loads slow panes afterward with a spinner.
- **Loading spinner:** wrap a slow update in the component's `loading` flag — `with self._main.param.update(loading=True): ...` sets it on enter and reverts on exit. **Caveat:** a synchronous callback won't flush the spinner until it returns; make the slow work `async` if you need it visible *during* the load.
- **Memory:** cap streaming history, call `pn.state.clear_caches()` when appropriate, and schedule periodic restarts for long-running deployments.
