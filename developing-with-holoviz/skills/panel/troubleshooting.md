# Troubleshooting Panel Apps

Symptom-indexed fixes for Panel/pmui apps that serve but misbehave *silently*. Look up what you see. For the review checklist see [Reviewing Panel Apps](reviewing-panel-apps.md); for the serve→screenshot→debug loop see [Iterating on Panel Apps](iterating-on-panel-apps.md).

## Contents

- [Widgets change but nothing updates (init ordering)](#widgets-change-but-nothing-updates-init-ordering)
- [AttributeError during init (on_init ordering)](#attributeerror-during-init-on_init-ordering)
- [First radio option can't be selected](#first-radio-option-cant-be-selected)
- [Select renders blank after setting .objects](#select-renders-blank-after-setting-objects)
- [Date filter returns nothing / type error](#date-filter-returns-nothing--type-error)
- [Markdown header flickers on hover](#markdown-header-flickers-on-hover)
- [Component rebuilds / flickers on every change](#component-rebuilds--flickers-on-every-change)
- [pmui.Page renders blank (no header/sidebar)](#pmuipage-renders-blank-no-headersidebar)
- ["responsive mode could not be enabled" / won't resize](#responsive-mode-could-not-be-enabled--wont-resize)
- [Screenshot shows a loading spinner](#screenshot-shows-a-loading-spinner)
- [Behavior or deprecation differs across versions](#behavior-or-deprecation-differs-across-versions)

## Widgets change but nothing updates (init ordering)

A `.from_param()` widget created **before** `super().__init__(**params)`: its value still syncs, but `@param.depends`/`.watch()` never fire, so dependents go stale. Not widget-specific, not a pmui write-back bug — just ordering. Fix: create `.from_param()` widgets **after** `super()`.

```python
def __init__(self, **params):
    super().__init__(**params)
    self._toggle = pmui.RadioButtonGroup.from_param(self.param.chart_type)  # ✅ after super()
```

Rule: bare panes before `super()`, `.from_param()` widgets after ([Viewer pattern](SKILL.md#viewer-class-pattern)).

## AttributeError during init (on_init ordering)

`AttributeError: '…' object has no attribute '_some_pane'` from inside `super().__init__()`: an `@param.depends(..., on_init=True)` watcher fires during `super()` and references a pane not yet created. Fix: create panes referenced by `on_init` watchers **before** `super()` (the flip side of the rule above).

## First radio option can't be selected

`RadioBoxGroup`/`RadioButtonGroup` with `default=None` highlights the first option anyway, so clicking it fires no change event and callbacks never trigger on load. Fix: set a real default (or use `Select` for an empty state).

## Select renders blank after setting .objects

Assigning a **dict** to `Selector.objects` at runtime can leave display labels unpopulated. Fix: keep the param's `objects` a plain list of values, drive the widget's `options` (a `{label: value}` dict) directly, and reassign `value` to stay within the new set (see [`from_data`](designing-panel-architecture.md#the-from_data-factory)).

## Date filter returns nothing / type error

A date widget yields `datetime.date`, which doesn't compare cleanly to a pandas datetime column. Fix: wrap in `pd.Timestamp` first.

```python
start, end = self.date_range
df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
```

## Markdown header flickers on hover

The auto-generated header anchor renders on hover. Fix: `pn.pane.Markdown(..., disable_anchors=True)`.

## Component rebuilds / flickers on every change

A `@param.depends` method (no `watch=True`) returns a *new* layout/widget each call, so the subtree is recreated. Fix: create panes once in `__init__` and update properties; use `pn.pane.Placeholder` when the content *type* varies. Full checklist: [Reviewing Panel Apps](reviewing-panel-apps.md#flickering-from-recreated-components).

## pmui.Page renders blank (no header/sidebar)

`__panel__` returns the `Page` only under `if pn.state.served:`, and that guard is `False` when `__panel__` runs — so you fall through to the bare layout. Fix: for an always-served app, build the `Page` once in `__init__` and return it unconditionally ([Page rules](using-material-ui.md#page)).

## "responsive mode could not be enabled" / won't resize

hvPlot sets `width=700` internally; `.opts(responsive=True)` doesn't remove it, and mixing responsive + non-responsive elements in an overlay conflicts. Fix: pass `responsive=True, height=N` as **hvPlot call args** (not `.opts()`), on *every* overlay element, and never set both `width` and `responsive=True`. Pure-HoloViews `.opts(responsive=True, height=N)` is fine ([Responsive Sizing](plotting-in-panel.md#responsive-sizing)).

## Screenshot shows a loading spinner

The capture beat the render — a fixed `wait_for_timeout` instead of waiting on the `.pn-loading` overlay that `defer_load`/`loading_indicator`/`loading=True` add. Fix:

```python
page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=30000)
```

Full pattern: [Iterating on Panel Apps](iterating-on-panel-apps.md#screenshot-shows-a-loading-spinner).

## Behavior or deprecation differs across versions

`panel-material-ui` moves fast — param names, defaults, and deprecations shift between releases. Diagnose the method, don't memorize versions:

- Print what's actually loaded: `print(pn.__version__, pmui.__version__)`. A long-lived server holds *old* modules until restarted — restart after upgrading.
- Run it and **read the `DeprecationWarning`** — it names the replacement. Trust the warning over any doc.

Known moving targets: `pmui.Chip(object=...)` is deprecated → use `label=` (but `pmui.Alert(object=...)` is *not* deprecated — don't "fix" it). The button-group "from_param write-back gap" was never real — it's the [init-ordering](#widgets-change-but-nothing-updates-init-ordering) issue.
