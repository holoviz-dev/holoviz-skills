# HoloViz Skills Evaluation

Automated system to measure whether SKILL.md files improve Kilo Code's responses to HoloViz tasks. Runs queries with and without skills enabled, executes the generated code, and produces JSON summaries plus dashboards. Supports running multiple models in a single pass to compare their outputs side by side.

## Coverage

`scripts/eval_queries.yaml` currently defines 2 queries: `hvplot_earthquake_plot`
(a static `hvplot` plot) and `panel_sunset_app` (an interactive `panel` app). They
cover the `hvplot` and `panel` skills. The runner does not enforce which skill a
query exercises; the association is by convention, via each query's `category`.

`cleanup` has its own eval, `eval_cleanup.py` (see below), because `eval.py` executes generated plots and a
code review has nothing to execute. The other skills (both routing skills,
`param`, `holoviews` and its references, `documentation`,
`minimal-example`, `outreach`, `pr-description`, `testing`,
`creating-custom-holoviz-skills`) have no eval coverage yet. Contributions adding
queries for other skills are welcome — see "Adding Queries" below.

## Cleanup Eval

`eval_cleanup.py` asks Kilo, with and without skills, to clean up a sloppy change in a
tiny package whose other modules already have the helpers the change rewrites.
`cleanup_review` is the opening snippet of "Deslop AI Slop Part 2: Code", which the
cleanup skill quotes, so treat it as a smoke test; `cleanup_holdout` plants the same six
findings in code no skill shows. Each run works in a temporary copy of the package, so
Kilo can't read this README or the eval's docstring, and the files Kilo returns are
graded with `cleanup_scan.py` plus a check for each helper the change should reuse.

```bash
pixi run eval-cleanup                                   # both fixtures, both conditions
python scripts/eval_cleanup.py --fixtures cleanup_holdout --repeat 5
python scripts/eval_cleanup.py --models kilo/kilo-auto/free --skills with
python scripts/eval_cleanup.py --fixtures cleanup_holdout \
    --grade eval_results/cleanup/cleanup_holdout/default/with_skills/run-1
```

Rerun it after a model release to check the skill still earns its place: if the
without-skills pass rate for a check catches up, the rule behind that check can go.

## Requirements

- Kilo Code CLI installed — `npm install -g @kilocode/cli` (see the [Kilo CLI docs](https://kilo.ai/docs/code-with-ai/platforms/cli))
- A Kilo account API key for authenticated runs. The free `kilo/kilo-auto/free` tier also
  runs anonymously, but anonymous access is rate-limited (200 requests/h per IP), so a key
  is recommended — and required for reliable CI runs.

## Quick Start

```bash
# 1. Set up development tooling
pixi run setup-dev

# 2. Check the eval system is ready (installs the eval environment and Playwright)
pixi run eval-check

# 3. Run the full pipeline (generate → execute → report; updates local history files)
pixi run evals

# Run without screenshots (faster, no Playwright needed)
pixi run eval-no-screenshots

# Compare the frontier (paid) and free Kilo auto tiers
pixi run eval-multi

# Merge shared eval-data history and snapshots into local eval_results/
pixi run eval-sync

# Run tests for the eval scripts
pixi run eval-test

# Open the historical trends dashboard
pixi run eval-history-dashboard

# Deploy the historical dashboard (history from eval-data; add --images DIR for plots)
pixi run eval-deploy-dashboard
```

The eval tasks are defined only in the `eval` environment, so `pixi run` selects it
automatically. Run `pixi task list` to see a list of possible tasks in the repository.

## GitHub Actions Eval Command

The repository includes an `Eval Command` workflow at `.github/workflows/eval.yml`.

- Trigger from a pull request comment: `@run-eval`
- Trigger manually from the Actions tab: `Eval Command` workflow (`workflow_dispatch`)

Security and scope:

- Comment-triggered runs are limited to trusted users (`OWNER`, `MEMBER`, `COLLABORATOR`)
- Comment-triggered runs only support same-repository pull requests (fork PRs are rejected)
- The workflow checks out the PR head SHA and runs its full pipeline, including the PR's
  own `scripts/`/`pixi.toml`

Required repository secret:

- `KILO_API_KEY`: a Kilo account API key (from your profile at app.kilo.ai). If it's not
  set the workflow runs anonymously (anonymous access is rate-limited; see Requirements).
  If the key works but is rejected with "model not found" (no free-tier access), the run is
  retried anonymously; any other failure fails the job.

Jobs:

- `eval` (`contents: read`, no push credentials): runs the queries and the generated
  code, uploads `eval_results/` as an Actions artifact, and posts the PR comment. Kilo's
  deny rules are passed via `KILO_CONFIG_CONTENT` (ranked above project config); project
  config stays enabled because `AGENTS.md` is what points the agent at the skills.
- `publish` (`contents: write`, fresh runner, never runs generated code): downloads the
  artifact, pushes the JSON history to the `eval-data` branch, and deploys the dashboard
  (bundling plot images from the artifact) when `deploy_dashboard` is set.

Each query's `metadata.json` records `instruction_reads` (the `SKILL.md` / `AGENTS.md`
files the agent read) so a regression in skill loading is visible. A query that times out
is recorded as `timed_out` and the run continues; the run only aborts if every call fails.

## `eval.py` Reference

All steps are combined in a single script. Each step can be skipped independently.

```
python scripts/eval.py [options]

Options:
  --queries ID [ID ...]     Run specific query IDs only (default: all)
  --models MODEL [MODEL ...]
                            Model(s) to evaluate in provider/model format
                            (default: Kilo's default). E.g. --models kilo/kilo-auto/free
  --skills both|with|without
                            Which condition(s) to evaluate (default: both)
  --skip-generation         Skip Kilo queries; use existing generated_code.py files
  --skip-execution          Skip code execution step
  --skip-aggregation        Skip metrics aggregation step
  --skip-screenshots        Skip Playwright screenshot capture (faster)
  --timeout SEC             Code execution timeout in seconds (default: 30)
  --run-trigger TRIGGER     manual|ci_comment|ci_dispatch|ci_schedule|ci_tag (default: manual)
  --pr-number N             PR number recorded in run metadata
  --queries-file PATH       Path to queries YAML (default: scripts/eval_queries.yaml)
  --output DIR              Output directory (default: eval_results/)
```

### Common invocations

```bash
# Full pipeline, specific queries only
python scripts/eval.py --queries hvplot_earthquake_plot

# With-skills condition only (skip Kilo without-skills run)
python scripts/eval.py --skills with

# Re-run execution + report without re-querying Kilo
python scripts/eval.py --skip-generation

# Generate responses only, no execution or report
python scripts/eval.py --skip-execution --skip-aggregation

# Full pipeline, longer timeout, no screenshots
python scripts/eval.py --timeout 60 --skip-screenshots

# Run with specific models
python scripts/eval.py --models kilo/anthropic/claude-sonnet-5

# Compare two models, with-skills only
python scripts/eval.py --models kilo/kilo-auto/frontier kilo/kilo-auto/free --skills with
```

### Available models

Models are given in `provider/model` format. Run `kilo models kilo` to list the Kilo
Gateway catalog. Auto tiers route to underlying models server-side, so the tier ID stays
stable even as the models behind it change:

- `kilo/kilo-auto/free` — best available free models, no credits required (CI default)
- `kilo/kilo-auto/efficient`, `kilo/kilo-auto/balanced`, `kilo/kilo-auto/frontier` — paid tiers
- Individual free models appear as `*:free` entries in `kilo models kilo | grep :free`,
  but that list rotates as providers change promotional periods

The `eval-multi` task compares the paid `kilo/kilo-auto/frontier` tier against the free
tier so per-run cost can be compared.

When `--models` is not specified, Kilo uses its own default model. The `model` field is recorded as `"default"` in `metadata.json`, while the CLI labels it as `Default (Kilo)`.

## Historical Dashboard

The historical dashboard is intentionally separate from the query comparison view and
focuses on trends across runs. Open it with the `eval-history-dashboard` task (Quick
Start).

It reads compact history files produced during aggregation:

- `eval_results/runs.json` (run registry + metadata)
- `eval_results/history_summary.json` (flattened trend rows, including `cost`,
  `run_trigger`, `pr_number`, `timed_out`, `anonymous`, and the `resolved_models` each call
  was routed to)

On a clean checkout, pull the shared copies first (see Shared Eval Data below).

By default the dashboard selects the 5 most recent runs that were not triggered by a PR
comment; use the "Run source" filter and the "Runs" selector to include PR runs. Timed-out
calls get their own status and are excluded from response-time statistics. Costs are summed
in the Overview, and runs recorded before cost tracking have an unknown cost that is excluded
from averages (the total is labelled "partial" when any selected cost is unknown). The
Overview shows a stacked bar of the underlying models each run's calls were routed to.

## Other Scripts

These scripts are still independently runnable in addition to being called by `eval.py`:

| Script | Purpose |
|---|---|
| `execute_generated.py` | Execute saved `generated_code.py` files and capture outputs |
| `aggregate_metrics.py` | Read `metadata.json` files and produce the comparison report |
| `compare_history.py` | Panel historical dashboard — `panel serve scripts/compare_history.py --show --args eval_results/` |
| `eval_sync.py` | Merge eval history and snapshots from the `eval-data` branch (`--upload` is CI only) |
| `eval_publish.py` | Deploy the historical dashboard: history from `eval-data`, plots from `--images DIR` |
| `toggle_skills.py` | Enable or disable skill files (rename AGENTS.md / SKILL.md) |
| `test_setup.py` | Pre-flight environment check before running evaluations |

## Output Structure

```
eval_results/
├── <model>/                         # e.g. kilo_kilo-auto_free, default
│   ├── with_skills/
│   │   └── [query_id]/
│   │       ├── response.txt        # Kilo response text
│   │       ├── events.jsonl        # Kilo's JSON event stream for the query
│   │       ├── metadata.json       # Model, tokens, timing, execution result
│   │       ├── generated_code.py   # Extracted code block
│   │       ├── execution.log       # stdout/stderr from code run
│   │       ├── plot_output.html    # Saved output: plot or Panel app (if generated)
│   │       └── screenshot.png      # Visual screenshot (if captured)
│   └── without_skills/
│       └── (same structure)
├── evaluation_results.json          # Full metrics comparison (machine-readable)
├── runs/                            # Per-run immutable snapshots
│   └── <run_id>/
│       ├── evaluation_results.json
│       └── run_metadata.json
├── runs.json                        # Compact run registry
└── history_summary.json             # Flattened historical trend rows
```

`metadata.json` always includes a `"model"` field — either the model name passed via
`--models` or `"default"` when no model flag was used.

## Shared Eval Data (`eval-data` branch)

CI publishes eval run history and snapshots to a shared `eval-data` git branch after each
run, so results aren't stuck on whichever machine produced them. The branch holds JSON
only (`runs.json`, `history_summary.json`, `runs/<run_id>/`); plot images stay in each
run's CI artifact.

Run the `eval-sync` task (Quick Start) to merge the shared history into local
`eval_results/`; local runs are kept. `eval-sync` always talks to the `origin` remote, so
it fails on a fork that doesn't have the branch. Pushing (`--upload`) is restricted to CI.

## Dashboard Deployment

Deploy the dashboard with history from `eval-data`, optionally bundling plots from a local
results directory or a downloaded run artifact:

```bash
pixi run eval-deploy-dashboard --images eval_results
# or use local history instead of the branch
python scripts/eval_publish.py --local-history eval_results --images eval_results
```

Useful environment variables:

- `OUTERBOUNDS_CONFIG_TOKEN` (optional; configures the CLI profile before deploy)

The deploy command stages `scripts/compare_history.py`, `runs.json`,
`history_summary.json`, and (with `--images`) `plot_output.html` (or `screenshot.png` if no
plot) per query for the Plot Outputs tab, and deploys that bundle to Outerbounds.

## Adding Queries

Edit `scripts/eval_queries.yaml`:

```yaml
queries:
  - id: my_new_query
    prompt: |
      Your prompt here...
    expected_output: static_plot
    timeout: 30
    category: hvplot_basics
```

Fields:
- `id` — unique slug; lowercase letters, numbers, underscores, or hyphens only
- `prompt` — the question/task sent to Kilo
- `timeout` — per-query Kilo timeout in seconds (capped at 900)
- `expected_output` — **not currently read or enforced by `eval.py`**. It records
  what the query should produce so `execute_generated.py` can be extended to check
  it. Supported values:
  - `static_plot` — HoloViews `Dimensioned`, Bokeh `Model`, or matplotlib figure;
    saved to `plot_output.html` / `plot_output.png`.
  - `panel_app` — Panel `Viewable` / `Viewer` object (e.g. what `servable()`
    returns or a `Viewer` subclass instance); rendered with `pn.io.save` to
    `plot_output.html` and screenshotted. Do not call `pn.serve(...)` in generated
    code — the executor runs the file to completion, so a blocking server call
    times out.
  This field and `category` exist for human documentation / future use.
- `category` — optional grouping tag, also **not currently read or used** by
  `eval.py`. Documentation only, for future use.

### Per-query dependencies

If a query needs a package the eval environment doesn't already have (e.g.
`astral` for `panel_sunset_app`), add it to `[feature.eval.pypi-dependencies]` in
`pixi.toml` and run `pixi lock`. It is then installed only for the `eval`
environment — never for `default`, `docs`, `lint`, or `build`, so it never becomes
a dependency of the library. Add the import to `check_dependencies()` in
`scripts/test_setup.py` so `eval-check` fails early if it is missing.

## Troubleshooting

**`Model not found: kilo/kilo-auto/free`**
Some accounts don't serve the free auto tier. The workflow retries such runs anonymously
when it sees this error; anonymous access is rate-limited (see Requirements). If that's
too slow, use a key from an account that offers the free tier.

**Tokens and execution time show 0**
Token and cost usage come from the JSON event stream `kilo run --format json` emits. It is
saved as `events.jsonl` in the query's result directory; inspect it if this happens.

**Code execution fails**
Check `execution.log` in the query result directory for the full traceback.

**`Warning: Could not detect or save plot output`**
The executor found no HoloViews, Bokeh, matplotlib, or Panel object to save. If a
`panel_app`/Panel query is expected to save output, make sure the app exposes a
Panel object (`Viewable`, or a `Viewer` whose `__panel__` returns one) rather than
only serving it.

**Panel/app query times out**
Generated code that ends with `pn.serve(...)` or `pn.serve(app, show=True)` starts
a blocking server the executor waits on until the timeout. Ask for a `servable()`
app instead, or raise `--timeout` / `timeout:` for apps that need longer to render.

**Warning in execution.log**
If a `DeprecationWarning` or similar appears, the relevant SKILL.md section needs a stronger anti-pattern example. Add a `# WRONG` / `# CORRECT` code pair to the relevant skill file.

**Dashboard shows "No evaluation results found"**
Run the `evals` task (Quick Start) first to generate `eval_results/evaluation_results.json`,
then re-launch the dashboard.
