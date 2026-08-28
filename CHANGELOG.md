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

- **Eval backend switched from GitHub Copilot to Kilo Code** — the evaluation pipeline
  (`.github/workflows/eval.yml` and `scripts/`) now drives the Kilo Code CLI
  (`@kilocode/cli`) on the free `kilo/kilo-auto/free` tier instead of the Copilot CLI.
  CI reads a `KILO_API_KEY` repository secret, referenced via `{env:KILO_API_KEY}` in the
  generated Kilo config so it is never written to disk; without the secret the run falls
  back to anonymous free-model access, which is rate-limited (200 requests/h per IP).
  Token and cost usage are now parsed from the Kilo CLI's JSON event stream rather than a
  text footer, and each `metadata.json` additionally records `cost` and the resolved
  underlying model. `eval-multi` now compares the paid `kilo/kilo-auto/frontier` tier
  against the free tier so per-run cost can be compared.

## Version 2026.08.13

### Added

- **Wrapping React Apps** reference (`panel/wrapping-react-apps.md`) — serving an existing
  React/JSX UI as the whole Panel app rather than rebuilding it in pmui: the shell/app class
  split, `model.useState` as the only transport, `Child` + `model.get_child` for embedding Panel
  components in JSX, request/response param pairs, the shadow-DOM CSS rules that follow from
  `use_shadow_dom=True`, the `_importmap` query-string trap that silently pulls in a second React,
  and the `--dev`-vs-production bundle asymmetry that makes a stale `_bundle` ship unnoticed.
  Cross-linked from `building-custom-components.md` and `converting-designs-to-material-ui.md`,
  which now states up front that it assumes a rebuild.
- **Scripts are published in the docs** — `build_stubs.py` now discovers `.py` files in a skill's
  `scripts/` directory the same way it already discovered `examples/`, grouping them under a
  "Scripts" nav node. `test_*.py` and `_`-prefixed files are skipped, and scripts get no
  screenshot pass since they're CLI tools rather than apps.
- **`preflight.py` and `layout_lint.py` are named in `panel/SKILL.md`** — previously they appeared
  only in `iterating-on-panel-apps.md`, which loads on demand, so the common "build me an app"
  path never learned the cheapest quality gate existed. Serving Workflow now gives both commands,
  the exit-code contract, and the skill-relative path-resolution caveat.
- **Docs-integrity warnings in `build_stubs.py`** — four checks that report `file:line` against
  the source, not the generated page: brackets Markdown would read as an unresolved shortcut
  reference (`are: [...]`, `objects[0]` outside a code span); relative `.md` link targets that
  don't exist, which `rewrite_internal_links` otherwise passes through silently; `.md` filenames
  cited from `scripts/` and `examples/` Python that no longer resolve — the class a rename misses,
  because the pointer lives in a docstring or in a printed violation message rather than in link
  syntax; and colliding page names, since references, examples and scripts all flatten into one
  docs directory. Anchors are deliberately not validated: a slug algorithm out of step with the
  renderer reports every heading containing an identifier (`from_param`, `_rename`) as broken, and
  a noisy check gets ignored.

### Changed

- **`panel/troubleshooting.md` → `panel/troubleshooting-panel-apps.md`** — the only reference in
  the skill with a bare-noun filename, while its H1 and every inbound link label already said
  "Troubleshooting Panel Apps". Now pairs visibly with its sibling `reviewing-panel-apps.md`. All
  17 inbound references updated across five references, both index files, and the doc anchors
  emitted in `scripts/preflight.py` violation messages. Docs URL changes accordingly.
- **Changelog section headings are `## Version X.Y.Z`** — matching the form this file's own
  comment documents and `build.yml` greps for. They had drifted to `## vX.Y.Z`, which matched
  neither, so release-note extraction produced an empty `RELEASE_BODY.md` and every draft release
  was published with no notes.

### Fixed

- **`twine check` rejected a valid wheel** — Hatchling emits core metadata 2.5 by default and
  twine only learned to validate it in 7.0.0, so an older twine failed with
  `InvalidDistribution: '2.5' is not a valid metadata version` on a wheel that was fine. There were
  two stale copies of twine: the `pypa/gh-action-pypi-publish` pin, which bundles its own twine in
  a container image and was on v1.14.0 (twine 6), now bumped to v1.14.2 (the first release carrying
  twine 7); and the build environment, which had no twine at all, now pinning `twine >=7` behind a
  `check-pip` task. `build.yml` runs that task right after `build-pip`, so metadata problems
  surface in the build job on every push rather than in `pip_publish`, which only runs on a tag and
  after the waiting room. Pinning the floor rather than capping hatchling, since capping only
  defers the same break — it already happened at metadata 2.3 and 2.4.
- **Unresolved link reference in `holoviews/SKILL.md`** — a `[...]` inside a plain-quoted error
  message parsed as a shortcut reference link and warned on every docs build. The quoted
  `.opts()` error strings are now code spans, consistent with the `ValueError` on the same line.
- **Category-index links for a skill with examples but no references** — `generate_index_md`
  gated on `child.references` alone while the nav and page writer gated on
  `references or examples`, so such a skill would have been linked at `{slug}.md` while its page
  was written to `{slug}/index.md`. All three conditions now agree.
- **`layout_lint.py` cited a reference that was never written** — its docstring handed the
  taste-level half of visual review off to `designing-visual-quality.md`, which exists nowhere in
  the repo. The boundary it draws is real — the tool checks thresholds, not hierarchy or
  whitespace rhythm — so the clause now points at the screenshot step in
  `iterating-on-panel-apps.md`, reinforcing the preflight → logs → layout lint → screenshot ladder
  instead of at a missing file.

## Version 2026.08.06

### Added

- **`TypeError: unexpected keyword argument` (pmui params aren't universal)** — new
  `panel/troubleshooting.md` entry, keyed on the traceback text because `param` raises from
  `_setup_params` and every frame is `parameterized.py`, naming no pmui code. Tables the params
  that actually trip this — `RadioButtonGroup`/`CheckButtonGroup` `variant`, `CheckBoxGroup`
  `orientation`/`size`, `Container`/`Switch`/`FloatSlider` `variant`, `Tabs(variant=…)` (it is on
  `TabMenu`), `Paper(color=…)`, `Column(spacing=…)`, `Grid(ncols=…)` — plus the note that a wrong
  *value* raises `ValueError` from the `Selector` instead. Every row verified against pmui 0.12.0.
- **Verifying with panel-live-server** section in `iterating-on-panel-apps.md` — the `evaluate` /
  `screenshot` / `show` MCP tools, and which job each is for: `evaluate` for facts about objects,
  `screenshot(code=…)` for private self-checks while iterating, `show` as the one-time handoff to
  the user. Scoped explicitly to **snippets, not files** — all three take a `code` string with no
  path parameter, so they do not replace `panel serve` for an app being edited on disk.

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

- **`RadioButtonGroup`/`CheckButtonGroup` no longer documented with `variant="outlined"`.** They
  are MUI `ToggleButtonGroup`s and have no `variant` param at all, so the sidebar-styling
  recommendation in `using-material-ui.md` raised `TypeError` as written. Replaced with `color` /
  `size` / `orientation` and an `sx` rule for borders. The `button_style` fallback is worse, not
  better: these two are the only pmui components carrying that legacy alias with no real `variant`
  behind it, so the value is accepted and then dropped before reaching the browser — no error, no
  effect. `migrating-to-material-ui.md` also now warns that its `button_style=` → `variant=` rename
  row is not mechanical.
- **Deduplicated the layout guidance in `using-material-ui.md`**, which had two sections both
  titled "Layouts" — an ambiguous `#layouts` anchor, and the structural reason `Grid`/`Column`
  advice was written twice. Merged into one, and the `ncols`/`spacing`/`xs` negations now live only
  in the troubleshooting table, with the positive form (`size=` breakpoints, gaps via `sx`) in the
  reference.
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
- The Panel development loop now runs preflight before the first serve and layout lint once the
  logs are clean, with screenshots reserved for what neither can reveal — hierarchy, whitespace
  rhythm, and whether the page reads as an untouched template.

### Fixed

- **`Select` is not an empty-state fix for the first-option bug — it has the same defect.**
  `troubleshooting.md` previously advised "use `Select` for an empty state" while
  `using-material-ui.md` documented `Select` coercing `value=None` to the first option. The latter
  is correct: `Select`, `RadioButtonGroup` and `RadioBoxGroup` all coerce a `default=None`
  `Selector` to its first option and display it as chosen, so the widget shows a selection the user
  never made and clicking it fires no event. The two entries are now one, renamed to cover every
  affected widget, with `pmui.AutocompleteInput` given as the only single-select that stays `None`
  and multi-selects noted as unaffected (they start `[]`). Inbound links updated in
  `reviewing-panel-apps.md` and in the user-facing URL emitted by `scripts/preflight.py`.

## Version 0.1.0

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
