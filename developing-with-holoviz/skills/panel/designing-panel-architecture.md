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
- [URL State Sync](#url-state-sync)
- [Streaming with Generators](#streaming-with-generators)
- [Painting Partial Results](#painting-partial-results)
- [Caching](#caching)
- [Automatic Threading](#automatic-threading)
- [Blocking the Event Loop](#blocking-the-event-loop)
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

    def __init__(self, **params):
        super().__init__(**params)
        main = pn.Column(*(view(data_store=self.data_store) for view in self.views))
        # Build the Page once — __panel__ returns it unconditionally.
        self._page = pmui.Page(title=self.title)
        self._page.sidebar.append(self.data_store.filters)
        self._page.main.append(main)

    def __panel__(self):
        return self._page

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
- **Stored `param.DataFrame`** — when *many* components read the same derived frame, compute it once into a param with a `watch=True, on_init=True` watcher and have views depend on that param. Avoids recomputing the filter for every consumer. **Note:** this refactors `filtered` from a *method* into a *parameter* — every consumer that called `self.data_store.filtered()` (or passed the bound method, as `Table.__panel__` does above) must switch to reading `self.data_store.filtered` (the attribute, no call) or binding to `self.data_store.param.filtered`:

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

# Table.__panel__ updates accordingly — bind to the param, not a method call:
class Table(View):
    def __panel__(self):
        return pn.widgets.Tabulator(
            self.data_store.param.filtered, pagination="remote", page_size=12,
            sizing_mode="stretch_width",
        )
```

## Reactive Expressions (`pn.rx`)

For declarative *data pipelines* — as opposed to `pn.bind`, which wires inputs to a function — `pn.rx` wraps a value (often a DataFrame) so ordinary operations build a reactive expression. Widgets become reactive refs via `widget.rx()`. For the full `rx` API (`.rx.pipe`, `.rx.where`, `.rx.len()`, gotchas), see [Reactive Expressions (rx)](../param/SKILL.md#reactive-expressions-rx). The Panel-specific pattern — building a Tabulator/pane directly from a chained `pn.rx` pipeline over widget refs — is the idiom to reach for here:

```python
rxdf = pn.rx(turbines)
view = rxdf[rxdf.p_year.between(*year.rx()) & rxdf.p_cap.between(*capacity.rx())][cols]
pn.widgets.Tabulator(view, pagination="remote", page_size=5)
```

Reach for `pn.rx` when the transform reads naturally as an expression; reach for `pn.bind`/`@param.depends` when it's a function or method.

## Computed Read-Only Params

Mark a derived parameter `constant=True` so external code can't write it, then update it only inside `param.edit_constant`:

```python
import operator

class Calculator(param.Parameterized):
    left = param.Number(default=1)
    right = param.Number(default=1)
    op = param.Selector(default="+", objects=["+", "-", "*", "/"])
    result = param.Number(default=0, constant=True)     # read-only to the outside

    @param.depends("left", "right", "op", watch=True, on_init=True)
    def _calculate(self):
        ops = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
        with param.edit_constant(self):
            self.result = ops[self.op](self.left, self.right)
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

Default to **declarative** (`@param.depends`, `pn.bind`, `pn.rx`) for data/UI derivations — easier to test and compose. Keep **imperative** `.param.watch` only for true side effects: logging, persisting settings, notifications. The full priority ladder is in the [param skill](../param/SKILL.md#watch-vs-paramdepends-vs-link).

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

**Say something when the socket drops.** A session whose websocket has gone sits there indefinitely accepting clicks that reach nobody, and in an app that streams its content the user cannot tell that apart from "still loading". Four `pn.extension` options cover it:

```python
pn.extension(
    notifications=True,            # required for the two notification strings below
    reconnect=True,                # retry automatically — a lid close or VPN blip recovers
    disconnect_notification="Connection lost — reload to reconnect.",
    ready_notification="App is live.",
)
```

`ready_notification` matters most in a progressively-loading app: it marks the moment the document is live, which is when the intermediate states start meaning what they say.

**Check the option exists in your installed version — `pn.extension` does not tell you.** Verified: an unknown keyword is accepted silently, no error and no warning. So `reconnect=True` against a Panel too old to have it is a no-op you would go on believing was on, which is the worst way for a resilience feature to fail. Confirm once, cheaply:

```python
>>> [k for k in ("reconnect", "notifications", "disconnect_notification") if k in pn.config.param]
```

## Server-Side State and Scheduling

Periodic callbacks, deferred execution (`pn.state.execute`), and session lifecycle hooks (`onload`, `on_session_created`/`on_session_destroyed`, `schedule_task`) all live on `pn.state` — see Panel's [Callbacks guide](https://panel.holoviz.org/how_to/callbacks/index.html). What agents get wrong:

- `pn.state.add_periodic_callback(fn, period=...)` — `period` is in **milliseconds**, and the returned handle must be `.stop()`-ed. Tie it to the session so it stops on disconnect.
- Use `pn.state.execute(fn)` to defer heavy work off a callback so the UI stays responsive instead of blocking until the handler returns.

## URL State Sync

Share or bookmark the app's exact state by syncing param values to the URL query string with `pn.state.location.sync(obj, [...])` — pass a list to sync names as-is, or a dict mapping param name → query param name for shorter URLs:

```python
class Filters(param.Parameterized):
    year = param.Integer(default=2020)
    region = param.Selector(default="North", objects=["North", "South"])

filters = Filters()
if pn.state.location:
    pn.state.location.sync(filters, {"year": "y", "region": "r"})
```

Gotchas:

- **Guard with `if pn.state.location:`.** It's `None` outside a served app (a notebook cell, `python app.py` without a server context, some embeddings) — calling `.sync()` unconditionally raises at import time in those contexts.
- **Only *changed* parameters appear in the URL.** A freshly loaded page at its default state shows a bare URL with no query string, so "copy this link" reproduces a state the user actually altered, not the literal defaults. If every visit needs the full state in the URL, set the query params explicitly (e.g. in an `onload` hook) rather than relying on defaults to show up on their own.
- **Values are JSON-encoded going out.** A synced param holding something without a JSON representation (a custom class, a DataFrame) raises when it changes. Sync only JSON-safe types — numbers, strings, bools, and lists/dicts of those — and keep richer state (like a `param.DataFrame`) derived from the synced params rather than synced directly.
- **`Selector` options that look like integers can misresolve on load** — restoring `?region=01` coerces to the int `1` before matching against string options and fails. Prefer non-numeric option strings for anything synced to the URL.

Call `pn.state.location.unsync(obj)` to stop syncing (e.g. when a component holding synced state is torn down) — pass the same object given to `.sync()`.

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

Reach for a generator when ONE pane shows the progress of one job. When the work happens in a shared data layer that several surfaces read — and that layer should not import Panel — pass a callback instead: next section.

## Painting Partial Results

Fanning out the I/O lowers **total** time. Publishing each result as it lands lowers **time-to-first-content**, which is the number a user actually feels. Different levers, and you can take them separately: the hook below is a few lines. Its cost is not latency, it is honesty — most of this section is that cost.

Give the data layer a plain callback, not a Panel object:

```python
async def build(conn, *, on_chunk=None):
    rows = []

    def emit() -> None:
        """Publish what is assembled so far. Never raises, never blocks."""
        if on_chunk is None:
            return
        try:
            on_chunk(list(rows))          # a COPY, not the live list
        except Exception:                 # noqa: BLE001
            logger.exception("on_chunk failed")

    for group in GROUPS:                  # the boundaries the assembly already has
        rows.extend(await read(group))
        emit()
    return rows
```

Three rules in that snippet, each with a failure behind it: hand out a **copy** (the next `extend` would otherwise mutate a payload already serialised to a browser), never **await** the callback (a read is the wrong place to discover the UI is slow), and **swallow** its exceptions (a broken paint must not fail the query).

Emit at boundaries your assembly already has, and nowhere else. If anything downstream validates, hashes or cross-checks the payload — a schema, two values that must agree, a fingerprint — then every prefix you emit must already satisfy it, or the page shows an error and then un-shows it. That is a property to **test**, not a placement to eyeball:

```python
assert all(validate(c) == [] for c in chunks)                     # every prefix legal
assert all(b[:len(a)] == a for a, b in zip(chunks[:-1], chunks[1:]))  # append-only
assert chunks[-1] == final_result                                 # nothing rewritten at the end
```

### A partial result is not an empty result

This is the part that goes wrong, and it does not look like a bug. It looks like a page.

Every empty state you have ever written asserts a *completed check*: "No results." "Nothing to review." "0 issues found." Rendered over a read that is still running, that copy is not merely premature — it is false, and false in the direction that makes the user act on it: they conclude the thing does not exist and go elsewhere. One app's people-count section said, mid-read:

> There is no user figure for this account. Not zero — none.

...and twenty seconds later said one hundred and sixty-seven. Correct copy for a finished read; a lie for an unfinished one. A "still loading" banner at the top of the page does not repair it — the sentence sitting where the number goes is the one that gets read and repeated.

So sweep the whole payload, not the obvious slot. Anything reporting a finished check needs a partial variant or must be withheld:

- empty-state copy, per section **and** per cell
- counts and totals — `"6 figures"` → `"6 so far"`
- all-clears: "nothing failed", "nothing was hidden", "no conflicts"
- a search box's "no matches", which is the same claim answered on demand
- identity stamps computed over the whole payload — a digest of a prefix is well-formed, unreproducible and different on every paint. Emit `""` and let the surface handle it.

### Prefer a skeleton, then leave it alone

For a section whose content has not arrived, a shimmer placeholder beats any sentence: it says "filling in" without being read, and it cannot be mistaken for content. Panel gives you `pn.extension(defer_load=True, loading_indicator=True)` and the `loading` flag on any component; hand-rolled it is a few divs and one keyframe.

Two mistakes worth skipping straight past:

1. **Don't put the honest paragraph where the content goes.** It inherits that slot's typography — headline size, if that is what fills it — so a loading page reads as a page of findings.
2. **Don't caption the skeleton.** A caption shortened out of a full sentence loses its subject and becomes a non-sequitur ("Do not build one out of the download count." — build *what*?). Say it once, at the top, in the notice that says the read is running; the placeholder does the rest.

And then say when it **stops**. If "still loading" is a banner that disappears, a finished page reports that it finished by *having no banner* — an absence carrying a claim, which nobody can distinguish from a notice they scrolled past. Give the state a permanent home instead: one badge that reads `Still reading` or `Everything here is final`, keyed on the same state value the placeholders are keyed on so the two cannot disagree. Put the refresh control next to it, where the user is already asking "is this current?", and delete the other copy of that control if you have one.

### Check the surface handles the new state

A state the renderer does not branch on is a state that renders wrongly. In the app above, Python grew a fourth state and computed its message correctly on every chunk — while the view still read `if state === "thin"`, so the one sentence saying "this page is still filling in" was displayed *never*. When you add a state, grep the consumer for the states it tests and count them.

### Where a partial payload may not go

- **Never store it where "done" is recorded.** If presence in a cache or a dict is what makes the next visit skip the work, a prefix parked there is a permanently half-finished answer. Paint from the partial; commit only the final.
- **Keep derived emphasis stable.** Anything computed over the whole set — a lead item, a "top" row, an axis range, a colour scale — can flip as the set grows. A headline claimed and then stolen rewrites what the user is mid-way through reading, which is worse than no headline yet. Freeze it until complete, or only award it to something nothing later can outrank.
- **Gate per-read side effects to the final emit.** Audit rows, analytics events, notifications: N chunks must not become N of them.
- **Guard the paint on identity**, exactly as with any other late write — [The user moved on](#the-user-moved-on).

## Caching

Panel has three tiers (full API in the [Caching guide](https://panel.holoviz.org/how_to/caching/index.html)) — the choice is the part worth knowing:

- **`pn.state.cache`** — a plain process-global dict shared across sessions. For a one-time dataset load shared by everyone.
- **`pn.state.as_cached(key, fn, ttl=..., **kwargs)`** — same intent, no manual `if`-check; reruns only when the hashed `kwargs` change.
- **`@pn.cache`** — memoize a function on its arguments; reach for it when results depend on inputs (supports `ttl`, `max_items`, `policy`, `to_disk`, `per_session`). Handles coroutines, so it works on `async def` too.

Warm the cache before the first visitor with `panel serve --warm` (and `--setup script.py` to populate from a separate script).

**Gotcha — `@pn.cache` on a method keys on `self`.** Apps are one instance per session, so a decorated *method* caches per session and buys nothing on a reload — which is usually the exact case you wanted to speed up. Verified:

```python
class Session:
    @pn.cache(ttl=60)
    def fetch(self, owner): ...

a, b = Session(), Session()      # two sessions
a.fetch("x"); a.fetch("x")       # 1 real call  ✅ memoised
b.fetch("x")                     # 2 real calls ❌ different `self`, cache miss
```

Cache at **module level**, keyed only on plain values, for anything that should survive a reload:

```python
@pn.cache(ttl=300)
async def fetch_rows(owner: str, as_of: str): ...    # ✅ shared across sessions
```

Two more things worth knowing when picking a tier:

- **A cache is only as correct as its key.** Anything the value depends on belongs in it — an as-of date, the user whose data it is, a scope flag. A key missing one of its inputs is a correctness bug wearing a performance hat.
- **If you hand-roll a two-tier cache, check where the TTL applies.** A `ttl=` that binds only the disk tier will serve a stale in-memory hit for the life of the process. Either stamp values with a wall-clock time and validate on read, or put the expiry in the key (e.g. the as-of date). Wall clock, not `perf_counter`, for anything that outlives the process.
- **Never cache a failure.** Store the result only on the success path (`try/except/else`), or a transient outage becomes an authoritative "this account has no contacts" for the whole TTL.
- **Probe with a membership test, not a `get`.** To show which items are *already* cached — a list marking the rows that will open instantly — you only need to know a key exists. A `get` through a two-tier cache also deserializes the value and promotes it into the memory tier, and the memory tier is the one with no expiry; sixty probes on page load then hold sixty payloads for the life of the process and silently extend their TTLs. `key in disk_cache` answers the question that was asked (and honours `expire`).
- **Check the cache *before* the concurrency gate.** A cache hit puts no load on the backend, so it has nothing to be bounded by. Behind the semaphore, an item you already have waits out other users' live queries — and any "this one opens instantly" hint you show becomes a promise you break.

## Automatic Threading

`pn.extension(nthreads=N)` dispatches every event onto a thread pool automatically — no manual thread management (details in the [Concurrency guide](https://panel.holoviz.org/how_to/concurrency/index.html)). The non-obvious bit: `nthreads=0` auto-sizes to `min(32, os.cpu_count() + 4)`. Use threading for CPU-bound callbacks; prefer `async`/`await` for I/O — but see below, because `async` alone does not make I/O non-blocking.

## Blocking the Event Loop

**One event loop serves every session.** A blocking call in one user's callback freezes every other user's page for its duration — their widgets stop responding and their websockets stall. This is the highest-consequence runtime bug in a served Panel app, and it hides from ordinary logs, because logs time the *work* while the freeze is the *wait*.

### `async def` does not make I/O async

The trap is a coroutine that calls a synchronous client and `await`s only *between* calls. It has `async`, `await` and a polling loop, so it reads as non-blocking — and every line that touches the network is still on the loop.

```python
# ❌ Looks async. Every client call runs ON the loop; the sleep is the only thing
#    that yields, which is exactly what makes the rest easy to miss.
async def run_query(conn, sql):
    cur = conn.cursor()
    cur.execute_async(sql)                         # blocking HTTP POST
    while True:
        status = conn.get_query_status(cur.sfqid)   # blocking, once per poll
        if status == SUCCESS:
            return cur.fetch_pandas_all()           # blocking download + decode
        await asyncio.sleep(0.5)

# ✅ Hand each blocking call to a thread. Same logic, same semantics.
async def run_query(conn, sql):
    cur = conn.cursor()                             # cheap and local: no I/O
    await asyncio.to_thread(partial(cur.execute_async, sql))
    while True:
        status = await asyncio.to_thread(conn.get_query_status, cur.sfqid)
        if status == SUCCESS:
            await asyncio.to_thread(cur.get_results_from_sfqid, cur.sfqid)
            return await asyncio.to_thread(cur.fetch_pandas_all)
        await asyncio.sleep(delay)
```

Measured on one such query (four blocking calls of ~150 ms each): worst loop stall **469 ms → 6.3 ms**. With four queries concurrently: **1230 ms → 14 ms**, and wall clock 3.73 s → 1.07 s — because on-loop blocking *also serialises* concurrent work. A fan-out built over blocking calls is both slower and more disruptive than doing them one at a time.

Before threading a client, check it is safe to use from several threads: DB-API drivers expose `module.threadsafety` (`2` = threads may share the module and connections — give each call its own cursor). Read the driver's own source when the docs are thin; a comment like *"prevent KeyError when multiple threads remove the same id"* is a stronger guarantee than a doc page. Some drivers also ship a native asyncio API, which is better still, but adopting it usually means changing how connections are *created* — a larger change than moving the calls off the loop.

Also watch the **poll interval**. A cadence applied *before* the first status check taxes every call, however fast: at 0.5 s, eighteen sequential reads spend nine seconds asleep. Poll fast first, then back off.

### Prove it, don't assume it

A heartbeat coroutine measures the loop directly — it sleeps a known interval and reports how much longer it actually took:

```python
async def loop_monitor(interval=0.25, warn=0.5):
    while True:
        before = perf_counter()
        await asyncio.sleep(interval)
        stall = (perf_counter() - before) - interval
        if stall >= warn:
            logger.warning(f"event loop stalled {stall:.2f}s")
```

Start one task per **process**, not per session, and keep a reference to it — asyncio holds only a weak one, and a monitor that gets garbage-collected stops monitoring silently. Four wakeups a second turns "the app feels slow sometimes" into a timestamped fact. The same heartbeat is the assertion in tests: run the suspect coroutine beside it and assert the worst gap stays small — then block the loop deliberately with `time.sleep` to confirm the test has teeth.

To *name* the culprit rather than merely detect it, turn on asyncio debug mode (`loop.set_debug(True)` plus `loop.slow_callback_duration = 0.5`); asyncio then logs `Executing <Handle ...> took N seconds` with the callback identity. `slow_callback_duration` is consulted **only** in debug mode, and debug mode adds per-step overhead — gate it behind a flag instead of leaving it on.

### Fan out the I/O, keep the assembly ordered

Independent reads awaited one at a time cost their sum. Launch them together and consume them by name, so downstream code that reads earlier results while building later ones is untouched — only the I/O moves:

```python
gate = asyncio.Semaphore(4)      # bound it: concurrency is load on the backend
reads = {name: asyncio.ensure_future(fetch(name, gate)) for name in NAMES}
...
first = await reads["first"]      # assembly order unchanged
second = await reads["second"]
```

Three things to get right:

- **Bound the concurrency,** and put the bound in an env var — how much load a backend tolerates is a capacity decision, not a code decision. Keep the code default the safe one.
- **Release what nobody awaits.** A conditional branch may never consume a task, so cancel leftovers in a `finally` *and log which ones* — otherwise a thin case quietly pays for reads it discards.
- **If the output is validated or hashed, check the validator tolerates partial input** before streaming results as they land — and test it, per prefix, rather than reasoning about it: [Painting Partial Results](#painting-partial-results). Ours only compared items sharing a source, so any subset was valid; a validator with cross-source invariants would reject every intermediate state.

### The user moved on

Long async work outlives the click that started it, so *every* write back to the UI needs an identity check — otherwise a slow result paints over what the user is looking at now:

```python
result = await slow_work(item_id)
if self.selected == item_id:      # guard the PAINT, not necessarily the work
    self.pane.object = result
```

Whether to cancel the *work* is a separate decision from whether to paint it. `asyncio.shield` lets it finish — right when the result gets cached or persisted, since the next visit is then instant. The case worth special handling is work that is merely **queued**: if a semaphore is holding it back it has spent nothing yet, so dropping it frees the slot for what the user is actually waiting on. Left in place, the page the user is on queues behind the pages they abandoned.

`.cancel()` only *requests* cancellation — the task settles on the next turn of the loop, so a test must `await asyncio.sleep(0)` before asserting `.cancelled()`. And when awaiting through `asyncio.shield`, catch `CancelledError` and check `task.cancelled()` to tell the two cases apart: the inner work being dropped is a normal outcome, while this coroutine being cancelled belongs to the caller and must propagate.

### Testing async callbacks

`pn.state.execute` really does run the scheduled coroutine outside a served session, so a unit test that just assigns a param can kick off the app's entire background pipeline — real API calls included. Stub it when you only mean to test the synchronous half:

```python
monkeypatch.setattr(pn.state, "execute", lambda *a, **kw: None)
```

## Profiling

Profile a callback with `@pn.io.profile("name", engine=...)` (engines: `pyinstrument`, `snakeviz`, `memray`); results appear in the `/admin` dashboard (`panel serve --admin`). **The function is `pn.io.profile`, not `pn.io.profiler`** — a common hallucination.

## Batching, Loading, and Memory

- **Batch updates:** wrap multiple component assignments in `pn.io.hold()` so they trigger a single redraw instead of one per assignment — see [panel/SKILL.md](SKILL.md#performance).

- **Defer heavy components:** `pn.extension(defer_load=True, loading_indicator=True)` renders the page first and loads slow panes afterward with a spinner.
- **Loading spinner:** wrap a slow update in the component's `loading` flag — `with self._main.param.update(loading=True): ...` sets it on enter and reverts on exit. **Caveat:** a synchronous callback won't flush the spinner until it returns; make the slow work `async` if you need it visible *during* the load.
- **Memory:** cap streaming history, call `pn.state.clear_caches()` when appropriate, and schedule periodic restarts for long-running deployments.
