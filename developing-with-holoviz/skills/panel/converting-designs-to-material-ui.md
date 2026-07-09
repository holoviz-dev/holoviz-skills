# Converting Designs to Material UI

A workflow for turning a visual design — a screenshot, a Figma mockup, or an existing app (e.g. a
React app) you are porting — into a panel-material-ui (pmui) app. This is the *process*; for
component APIs and theming see [Using Material UI](using-material-ui.md), for custom components see
[Building Custom Components](building-custom-components.md), and for the serve/screenshot mechanics
see [Iterating on Panel Apps](iterating-on-panel-apps.md).

## Contents

- [Why a Workflow](#why-a-workflow)
- [1. Capture References First](#1-capture-references-first)
- [2. Map the Design to Components](#2-map-the-design-to-components)
- [3. Build Component-First With Mock Data](#3-build-component-first-with-mock-data)
- [4. Assemble](#4-assemble)
- [5. Theme to Match, Last](#5-theme-to-match-last)
- [Pitfalls](#pitfalls)

## Why a Workflow

The failure mode is building the whole app in one pass, then discovering at the end that a row
doesn't click, the layout collapses, or the colors are off — with no way to tell which of fifty
pieces is wrong. Building **one verified component at a time against a reference image** keeps every
step cheap to check and localizes every problem.

## 1. Capture References First

If you are porting an existing app, screenshot **every state up front** and keep the images as the
comparison target for the whole build:

- The default view, plus each meaningfully different record/selection.
- Conditional states: an expanded accordion, an empty list, an error/alert variant, a hover/active
  row. These are the states you will otherwise forget to build.

See [Iterating on Panel Apps](iterating-on-panel-apps.md) for the Playwright capture how-to (run the
source app, screenshot at a fixed viewport, wait for load). Save the images somewhere stable
(`reference_screenshots/`) and refer back to them at every step below.

## 2. Map the Design to Components

Before writing UI code, inventory the design and assign each visual element a pmui component. Most
of it is native:

| In the design | pmui |
|---|---|
| Badge / tag / status chip | `Chip` |
| Card / panel with a border | `Paper` |
| Section grid, responsive columns | `Grid` (`size={"xs": 12, "md": 6}`) |
| Collapsible "show more" | `Accordion` |
| Plain selectable list | `MenuList` |
| Headings / labels / body text | `Typography` |
| Callout / warning box | `Alert` |

Then flag the **one or two** elements that native widgets can't express — typically a richly-styled
clickable element. Decide those are custom components now (see
[Building Custom Components](building-custom-components.md) — the "Choosing an Approach" ladder:
native pmui first, a JS component only when needed), so you are not surprised mid-build.

## 3. Build Component-First With Mock Data

Build in dependency order (helpers → leaf components → composite views → app shell). For **each**
component, before moving on:

1. Implement it as a pure function or `Viewer`/`JSComponent` that takes a domain dict.
2. Serve *just that component*, fed mock data, in a throwaway preview script.
3. Screenshot it and compare against the matching region of the reference image.
4. Fix until it matches, then proceed.

**Use a mock module.** Hand-write 1–2 records in the real data shape so components render without the
live backend or real data pipeline:

```python
# mock.py — covers the conditional branches the previews must exercise
MOCK_RICH  = {...}   # hits every variant: alert path, expansion list, mixed statuses
MOCK_PLAIN = {...}   # minimal: no alert, empty optional lists
```

One record should exercise every conditional branch (the alert path, a non-empty optional list, all
status colors); the other should be minimal (no alert, empty lists) so you confirm both render. This
is the same idea as the mock-source decoupling in
[Iterating on Panel Apps](iterating-on-panel-apps.md), scoped to a single component.

A preview harness is just a themed `Page` (or bare `Container`) wrapping the one component:

```python
import panel_material_ui as pmui
from components import account_row
from mock import MOCK_RICH
from theme import THEME

pmui.Page(theme_config=THEME, dark_theme=True,
          main=[account_row(MOCK_RICH)]).servable()
```

These preview scripts are scaffolding — delete them once the full app is verified.

## 4. Assemble

Only after the pieces match the references, wire them into the app: a single
`pn.viewable.Viewer` holding one source-of-truth selection parameter, panes created once in
`__init__` and updated reactively (no flicker), returned from `__panel__` inside a `pmui.Page`. See
[Using Material UI](using-material-ui.md) for `Page`/layout rules and the Panel skill for the
Viewer pattern.

## 5. Theme to Match, Last

Approximate the original palette in `theme_config` (background, paper, text, the accent as
`primary.main`) once the structure is right. Theming a moving target wastes effort; theming a
finished layout is a single focused pass. See [Using Material UI](using-material-ui.md), including
the Page header/AppBar color note.

## Pitfalls

- **Skipping the per-component screenshot.** "It'll be fine, I'll check at the end" is exactly how
  you end up with an unclickable row buried in a finished-looking app. Check each piece.
- **Forgetting conditional states.** If you only preview the happy-path record, the alert/empty/
  expanded variants ship unverified. Mock at least one record that triggers each branch.
- **Theming first.** Don't tune colors before the layout is settled — see step 5.
