# Reviewing Panel Apps

Checklist for reviewing Panel applications. Focus on anti-patterns that cause flickering, wasted redraws, or subtle bugs. For general code style (imports, naming, param ordering), see the [cleanup](../../../contributing-to-holoviz/skills/cleanup/SKILL.md) skill. For a complete example that applies all these patterns, see `examples/wizard.py`.

## Contents

- [Flickering from Recreated Components](#flickering-from-recreated-components)
- [Missing Hold on Multi-Property Updates](#missing-hold-on-multi-property-updates)
- [Watcher Dependency Gaps](#watcher-dependency-gaps)
- [Bind vs Watch for External Instances](#bind-vs-watch-for-external-instances)
- [Spacer vs Margin](#spacer-vs-margin)
- [Mutating Instead of Reassigning](#mutating-instead-of-reassigning)
- [Watch vs Depends Misuse](#watch-vs-depends-misuse)

## Flickering from Recreated Components

The most common Panel anti-pattern. A `@param.depends` method that returns a new layout or widget on every call causes the entire component to be torn down and rebuilt, producing visible flicker.

```python
# WRONG — recreates Row on every step change
@param.depends("active_step")
def _nav_buttons(self):
    return pmui.Row(self._back_btn, pn.layout.HSpacer(), self._next_btn)

# CORRECT — create once in __init__, reference in layout
def __init__(self, **params):
    self._nav_row = pmui.Row(self._back_btn, pn.layout.HSpacer(), self._next_btn)
    super().__init__(**params)
```

**What to look for**: any `@param.depends` method (without `watch=True`) that returns `pn.Column`, `pn.Row`, `pmui.Row`, `pmui.Paper`, or any layout/widget constructor. The fix is always the same — create once, update properties.

For content that genuinely varies in type (string one moment, plot the next), use `pn.pane.Placeholder`:

```python
# WRONG — recreates widget on every toggle
@param.depends("mode")
def _details(self):
    if self.mode == "A":
        return pmui.FloatInput.from_param(self.param.amount)
    return pmui.Typography("No input needed")

# CORRECT — create both once, swap via Placeholder
def __init__(self, **params):
    self._amount_input = pmui.FloatInput.from_param(self.param.amount)
    self._no_input_msg = pmui.Typography("No input needed")
    self._details = pn.pane.Placeholder()
    super().__init__(**params)

@param.depends("mode", watch=True, on_init=True)
def _update_details(self):
    if self.mode == "A":
        self._details.update(self._amount_input)
    else:
        self._details.update(self._no_input_msg)
```

## Missing Hold on Multi-Property Updates

When a watcher updates multiple widget properties, each assignment triggers a separate redraw. Wrap in `pn.io.hold()` to batch them into one.

```python
# WRONG — 6 separate redraws
@param.depends("active_step", watch=True, on_init=True)
def _update_view(self):
    self._breadcrumbs.active = self.active_step
    self._back_btn.visible = self.active_step > 0
    self._next_btn.label = "Submit" if is_last else "Continue"
    self._next_btn.disabled = not current_step.complete
    self._content.update(current_step)
    self._progress_bar.value = progress

# CORRECT — one redraw
@param.depends("active_step", watch=True, on_init=True)
def _update_view(self):
    with pn.io.hold():
        self._breadcrumbs.active = self.active_step
        self._back_btn.visible = self.active_step > 0
        self._next_btn.label = "Submit" if is_last else "Continue"
        self._next_btn.disabled = not current_step.complete
        self._content.update(current_step)
        self._progress_bar.value = progress
```

**What to look for**: any watcher that assigns to 3+ widget properties without `pn.io.hold()`. Two assignments are borderline; three or more should always be held.

## Watcher Dependency Gaps

A watcher that lists only some of the parameters it logically depends on. The method runs when one parameter changes but not the other, leaving the UI out of sync.

```python
# WRONG — interest changes don't update complete status
@param.depends("wages", watch=True)
def _on_income_change(self):
    self.complete = self.wages > 0

# CORRECT — watch all inputs that affect the result
@param.depends("wages", "interest", watch=True)
def _on_income_change(self):
    self.complete = (self.wages + self.interest) > 0
```

**What to look for**: read every `self.param_name` inside the method body and verify it appears in the `@param.depends` decorator. Missing dependencies are silent — no error, just stale state.

## Bind vs Watch for External Instances

`pn.bind(fn, widget.param.value, watch=True)` works but creates an anonymous binding that's harder to debug and doesn't follow the Param convention. Use `.param.watch()` when reacting to parameters on an external instance.

```python
# WRONG — anonymous binding, fn receives value not event
pn.bind(self._on_menu_select, self._nav_menu.param.active, watch=True)

def _on_menu_select(self, active):
    if active and active[0] != self.active_step:
        self.active_step = active[0]

# CORRECT — explicit watch, fn receives event with .old/.new
self._nav_menu.param.watch(self._on_menu_select, "active")

def _on_menu_select(self, event):
    active = event.new
    if active and active[0] != self.active_step:
        self.active_step = active[0]
```

For the object's own parameters, prefer `@param.depends("param_name", watch=True)` — it's declarative and doesn't need event unpacking.

## Spacer vs Margin

`pn.Spacer(height=N)` creates a real component in the DOM. Margin or padding on the parent achieves the same visual gap without an extra element.

```python
# WRONG — extra DOM element just for spacing
pmui.Column(
    self._content,
    pn.Spacer(height=30),
    self._nav_row,
)

# CORRECT — margin on parent
pmui.Column(
    self._content,
    self._nav_row,
    margin=(0, 0, 30, 0),
)
```

`pn.layout.HSpacer()` and `pn.layout.VSpacer()` are fine — they're flexbox spacers that push siblings apart, which margin can't replicate.

## Mutating Instead of Reassigning

In-place operations on param values (`list.append()`, `dict.update()`, `+=` on lists) don't trigger watchers because Param checks identity, not contents. Always reassign.

```python
# WRONG — watcher never fires
self.items.append(new_item)
self.data["key"] = value

# CORRECT — new object triggers watcher
self.items = self.items + [new_item]
self.data = {**self.data, "key": value}
```

## Watch vs Depends Misuse

`@param.depends("x", watch=True)` is for side effects — updating another param, syncing state, calling an API. It should not return content for display.

`@param.depends("x")` (without `watch`) is for lazy rendering — it returns content and is called only when something reads the result. It should not have side effects.

```python
# WRONG — watch=True returning content (never displayed)
@param.depends("query", watch=True)
def results_view(self):
    return pn.pane.DataFrame(self._run_query())

# WRONG — no watch, but has side effects (runs unpredictably)
@param.depends("query")
def results_view(self):
    self.status = "loading"  # side effect!
    return pn.pane.DataFrame(self._run_query())

# CORRECT — watch for side effect, depends for display
@param.depends("query", watch=True, on_init=True)
def _run_query(self):
    self.result = execute(self.query)

@param.depends("result")
def results_view(self):
    return f"**{len(self.result)} rows**"
```
