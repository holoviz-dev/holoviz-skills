# Changelog

All notable changes to this project are documented in this file.

<!--
Release notes are extracted by .github/workflows/build.yml, which greps for a
section heading of the exact form `## Version X.Y.Z` (no brackets, matching
the git tag without its leading "v"). Add a new `## Version X.Y.Z` section at
the top for each release; keep `## Unreleased` (no "Version" prefix) for
in-progress notes so it is skipped by the extraction.
-->

## Unreleased

### Changed

- **Skill versions are now CalVer (`YYYY.MM.DD`), not semver.** `metadata.version` records the
  date a skill last changed. `scripts/bump_skill_version.py` stamps today's date instead of
  patch-bumping, so a second edit on the same day is a no-op, and the release tag format moves
  to `vYYYY.MM.DD` (`.github/workflows/build.yml` tag globs updated to match). A date cannot
  express severity, so the previous convention of a manual minor bump for a reversed
  recommendation is gone — record the *why* here instead. `scripts/migrate_to_calver.py` is a
  one-off that dates each existing skill from its last commit; delete it once it has run.
- **Prefer native `pn.Column`/`pn.Row` over the `pmui` equivalents.** They add no Material
  styling beyond `sx`, and the pmui ones are ESM/React components whose children can paint
  before the layout has sized them — which corrupts tile/geo plots irrecoverably (see the new
  `troubleshooting.md` entry). `using-material-ui.md`, `migrating-to-material-ui.md`, and the
  example apps were updated to match; keep `pmui.Column`/`Row` where `sx` styling is needed,
  and keep pmui for the layouts that carry real styling (`Grid`, `Container`, `Paper`, `Card`,
  `Tabs`, `Accordion`, `Page`).

### Added

- **Tile plot renders blank inside a pmui layout** — new `panel/troubleshooting.md` entry with a
  yes/no reproducer. The first paint lands with a zero frame dimension, Bokeh's tile aspect
  enforcement writes `±Infinity`/`NaN` into both ranges and their reset values, and no later
  layout pass or resize repairs it.

- `holoviz-skills.plugin` — an all-categories Claude Desktop / Cowork plugin, built alongside
  the per-category ones by `pixi run build-plugin`. Its version comes from the latest git tag,
  since it spans every skill and so has no single `SKILL.md` to read `metadata.version` from.
- **Preflight lint** (`panel/scripts/preflight.py`) — stdlib-only AST checks for the mechanical
  anti-patterns already documented in `reviewing-panel-apps.md` and `troubleshooting.md`:
  flicker-causing `@param.depends` returns, `watch=True` methods that return a value,
  `from_param` before `super().__init__()`, ungrouped writes that want `pn.io.hold()`, in-place
  param mutation, `Radio*Group` `None` defaults, and sliders without `throttled`. Runs before
  the first `panel serve`, so most bugs are caught without a server or a screenshot.
- **Layout lint** (`panel/scripts/layout_lint.py`) — headless-browser DOM/CSSOM checks at three
  viewport widths for horizontal overflow, sub-44px touch targets, WCAG text contrast, element
  overlap, misaligned sibling left edges, and font-size sprawl. Geometry and contrast are
  numbers rather than judgment calls, so this replaces most of what a screenshot was needed for.
- Check suites for both linters (`test_preflight.py`, `test_layout_lint.py`), built from the
  docs' own WRONG/CORRECT pairs — a rule that doesn't fire on its documented WRONG example, or
  fires on its CORRECT one, is a bug in the rule.
- **URL State Sync** section in `designing-panel-architecture.md` — `pn.state.location.sync()`,
  with the `if pn.state.location:` guard, the changed-parameters-only URL behavior, the
  JSON-encoding limit on synced values, and numeric-looking `Selector` options misresolving
  on load.
- **Notifications** section in `using-material-ui.md` — `pn.state.notifications.*`, plus the
  threading gotcha where calling it from a worker thread under `nthreads` can silently abandon
  the rest of that callback with no error surfaced.
- `MockSource` latency/failure knobs in `iterating-on-panel-apps.md`, so the loading spinner and
  the error/`Alert` path can be rehearsed from the command line without touching app code.

### Changed

- The Panel development loop now runs preflight before the first serve and layout lint once the
  logs are clean, with screenshots reserved for what neither can reveal — hierarchy, whitespace
  rhythm, and whether the page reads as an untouched template.

## v0.1.0

### Added

- **Decluttering Plots** reference (`holoviews/decluttering-plots.md`) — stripping Bokeh chart
  junk with `.opts()`: hiding the toolbar, disabling wheel-zoom via `default_tools`/`active_tools`,
  one-axis gridlines, sharing/hiding axes across stacked plots, legend placement, nested
  categorical axes, and why these opts belong on the top-level overlay/layout.
- **Composing Exploratory Plots** and **Distilling Explanatory Plots** references for hvPlot —
  layered marks and faceting for comparison; and one-message charts for an audience.
- **Data Storytelling** reference for Panel, plus a new `examples/graphic_story.py` and its
  screenshot — assembling explanatory charts into a scrollable editorial article.
- **Session Defaults** section in the HoloViews skill (`hv.opts.defaults`), and a **Defaults**
  section in the Panel skill (`pn.extension(sizing_mode=...)`, class param defaults, checking the
  library default first). Both are cross-linked, including why hvPlot's `responsive`/`height`
  can never be defaulted.
- **Lookup** sections in the param, hvPlot, HoloViews, and Panel skills, giving the docs-URL
  patterns and site-search entry points up front.
- **Skill Map** table in `contributing-to-holoviz/SKILL.md`, and **Contents** sections in both
  routing skills.
- Lint job in CI.
- Tabulator tip: carry `row_content` detail data in a `hidden_columns` column instead of a
  closure, with the serialization tradeoff spelled out.

### Changed

- Routing tables in both category skills now use paths relative to the category directory
  rather than repeating the full prefix on every row.
- Skill titles dropped the "Using " prefix (`Using Param` → `Param`), and the docs nav nests each
  skill's references beneath it.
- All skill `metadata.version` values normalized to `0.1.0`.
- Both routing skills marked `user-invocable: false`.
- Codex install path is now `.agents/skills/` (was `.codex/skills/`).
- `pn.io.hold()` guidance consolidated into the Panel skill's Performance section; the duplicate
  copy in `reviewing-panel-apps.md` was removed and the remaining references point at one place.
- Toolbar/tool-stripping guidance consolidated into the new Decluttering Plots reference; the
  hvPlot skill and `plotting-in-panel.md` now link to it instead of restating it.
- Serving guidance now prefers `panel serve app.py --dev --show` for iteration and explains that
  `python app.py` + `.show()` is a one-off preview only (it works for plain Panel too, not just
  panel-material-ui).
- Eval query ids namespaced by skill (`earthquake_plot` → `hvplot_earthquake_plot`).
- `scripts/README.md` and `eval_queries.yaml` now state plainly that `expected_output` and
  `category` are not read or enforced by `eval.py`, and that only the hvPlot skill has eval
  coverage so far.
- `build_stubs.py` and `toggle_skills.py` skip build-output and agent-config directories, with
  a comment explaining why `holoviz_skills/` in particular would otherwise duplicate a docs
  category.
- `AGENTS.md` points at `contributing-to-holoviz` for maintenance/PR/review work on this repo
  and at `creating-custom-holoviz-skills` for adding a skill.

### Fixed

Corrections found by executing every code block and prose claim against param 2.4.1,
hvPlot 0.12.2, HoloViews 1.22.1, GeoViews 1.15.1, and datashader 0.19.1:

- **param — `.param.update()` as a context manager does not batch.** It is a *scoped override*
  that restores the original values on exit (firing watchers a second time). The keyword form
  `obj.param.update(**kwargs)` is what batches, firing one watcher call with two events; the
  callback must therefore be written `def cb(*events)`. Added `pn.io.hold()` as the distinct
  Document-level layer for suppressing UI flicker.
- **param — `name`.** Param does not reject a `name` parameter; it is `constant`, so it is
  settable only in the constructor and later assignment raises
  `TypeError: Constant parameter 'name' cannot be modified`. Also documented the loss of the
  auto-generated unique instance name, and added a rule against `UPPERCASE_SNAKE_CASE` param names.
- **param — `default_factory` / `instantiate`.** `param.List` and `param.Dict` already default to
  `instantiate=True`, so `param.List(default=[])` is *not* shared between instances; the sharing
  hazard is specific to `param.Parameter(default=[])` and other `instantiate=False` types.
- **hvPlot — `tiles=` names depend on `geo=`.** `geo=False` resolves against HoloViews' 10 tile
  sources and `geo=True` against GeoViews' 32, and the sets are not nested: `"EsriStreet"` works
  only *without* `geo=True`. Documented the 9 names portable across both modes, the GeoViews-only
  additions, and how to enumerate the live set.
- **hvPlot — `coastline=True` requires geoviews**, which was previously stated only for
  `geo=True` even though `coastline` appears in three examples. `tiles=` alone does not.
- **hvPlot — `barh` without `set_index`** plots the numeric index (y-axis labelled `index`),
  rather than rendering NaN; and a list of hex colours passed via `color=` does not error — it
  silently applies only the first entry to every bar.
- **hvPlot — `active_tools=[...]`** replaced the non-existent `active_scroll=`; `show_frame` is a
  `.opts()` plot option, not a bare hvPlot kwarg; and the `index.hour` heatmap example moved to
  `index.year` × `index.month`, since daily data has a single hour value and collapsed the axis.
- **HoloViews — `link_selections` and DynamicMap.** The blanket "does NOT work" was wrong:
  there is an explicit `DynamicMap` branch that links when `dmap.type` is an `Element` subclass
  (plus `dynamic_mul` and `dynamic_operation` cases). The real hazard is that anything it cannot
  recurse into is returned *unlinked* with only a `param.warning` — no exception to catch.
- **HoloViews — `link_selections` runtime dependencies.** Removed the unfounded `pyarrow`
  requirement (the selection machinery never references it). Lasso needs `spatialpandas` **or**
  `shapely`; the lasso tool appears in the toolbar regardless, so the `ImportError` only surfaces
  when a lasso is drawn.
- **HoloViews — misplaced-option error text** corrected to
  `Unexpected option 'X' for Y type across all extensions.`, and the useful "Similar options…"
  tail it is followed by.
- **Panel — `pn.state.served` is always `False` inside `__panel__`**, because it inspects its
  immediate caller's module and Panel is the caller. The `if pn.state.served:` guard silently
  yielded the fallback layout with no header/sidebar; the `Page` is now built once in `__init__`
  and returned unconditionally, across the Panel skill, `using-material-ui.md`,
  `plotting-in-panel.md`, and the examples.
- **Panel — `super().__init__()` ordering** now also covers narrowing a `Selector`'s `.objects`
  (must come after `super()`, or the shared class parameter is mutated for every instance) and the
  collision when a `from_param` widget is also what an `on_init=True` watcher swaps in.
- Panel — inline `Markdown`/`HTML` labels beside an `HSpacer` collapse to near-zero width under
  `sizing_mode="stretch_width"`; pin them like the icon widgets.
- Stray double period in `AGENTS.md`, and a broken anchor in `using-material-ui.md`.
