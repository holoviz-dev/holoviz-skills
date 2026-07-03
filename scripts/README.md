# HoloViz Skills Evaluation

Automated system to measure whether SKILL.md files improve Copilot's responses to HoloViz tasks. Runs queries with and without skills enabled, executes the generated code, and produces JSON summaries plus dashboards. Supports running multiple models in a single pass to compare their outputs side by side.

## Requirements

- A GitHub Copilot subscription (Individual, Business, or Enterprise) or access via the GitHub Copilot API
- GitHub Copilot CLI installed and authenticated — see [installation guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)

## Quick Start

```bash
# 1. Install dependencies
pixi run setup-dev

# 2. Check the system is ready
pixi run eval-check

# 3. Run the full pipeline (generate → execute → report)
pixi run evals

# Run without screenshots (faster, no Playwright needed)
pixi run eval-no-screenshots

# Run across multiple models
pixi run eval-multi

# Run eval and merge history into eval_results/
pixi run -e eval evals

# Deploy the historical dashboard from existing eval_results/
pixi run -e eval eval-deploy-dashboard

# Open the historical trends dashboard
pixi run -e eval eval-history-dashboard
```

## GitHub Actions Eval Command

The repository includes an `Eval Command` workflow at `.github/workflows/eval.yml`.

- Trigger from a pull request comment: `@run-eval`
- Trigger manually from the Actions tab: `Eval Command` workflow (`workflow_dispatch`)

Security and scope:

- Comment-triggered runs are limited to trusted users (`OWNER`, `MEMBER`, `COLLABORATOR`)
- Comment-triggered runs only support same-repository pull requests (fork PRs are rejected)
- The workflow checks out the PR head SHA and runs the full pipeline by default

Required repository secret:

- `COPILOT_GITHUB_TOKEN`: a fine-grained PAT with `Copilot Requests` permission, tied to a user with Copilot CLI access

Workflow outputs:

- Uploads `eval_results/` as an Actions artifact
- Runs `evals`, then `eval-deploy-dashboard` when deploying the dashboard
- Posts a PR comment with run status and a short JSON summary (or a fallback message if missing)

## `eval.py` Reference

All steps are combined in a single script. Each step can be skipped independently.

```
python scripts/eval.py [options]

Options:
  --queries ID [ID ...]     Run specific query IDs only (default: all)
  --models MODEL [MODEL ...]
                            Model(s) to evaluate (default: Copilot's default).
                            E.g. --models claude-sonnet-4.6 gpt-5.4-mini
  --skills both|with|without
                            Which condition(s) to evaluate (default: both)
  --skip-generation         Skip Copilot queries; use existing generated_code.py files
  --skip-execution          Skip code execution step
  --skip-aggregation        Skip metrics aggregation step
  --skip-screenshots        Skip Playwright screenshot capture (faster)
  --timeout SEC             Code execution timeout in seconds (default: 30)
  --queries-file PATH       Path to queries YAML (default: scripts/eval_queries.yaml)
  --output DIR              Output directory (default: eval_results/)
```

### Common invocations

```bash
# Full pipeline, specific queries only
python scripts/eval.py --queries earthquake_plot

# With-skills condition only (skip Copilot without-skills run)
python scripts/eval.py --skills with

# Re-run execution + report without re-querying Copilot
python scripts/eval.py --skip-generation

# Generate responses only, no execution or report
python scripts/eval.py --skip-execution --skip-aggregation

# Full pipeline, longer timeout, no screenshots
python scripts/eval.py --timeout 60 --skip-screenshots

# Run with specific models
python scripts/eval.py --models claude-sonnet-4.6 gpt-5.4-mini

# Compare two models, with-skills only
python scripts/eval.py --models claude-sonnet-4.6 gpt-5.4-mini --skills with
```

### Available models

Run `copilot --allow-all -p "list available model IDs"` to see current models. At time of writing:

- `claude-sonnet-4.6` (default)
- `claude-sonnet-4.5`
- `claude-haiku-4.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.3-codex`
- `gpt-5-mini`
- `gemini-3.1-pro-preview`
- `gemini-3.5-flash`

When `--models` is not specified, Copilot uses its own default model. The `model` field is recorded as `"default"` in `metadata.json`, while the CLI labels it as `Default (Copilot)`.

## Historical Dashboard

The historical dashboard is intentionally separate from the query comparison view and
focuses on trends across runs.

```bash
panel serve scripts/compare_history.py --args eval_results/ --show
```

Or using pixi:

```bash
pixi run -e eval eval-history-dashboard
```

It reads compact history files produced during aggregation:

- `eval_results/runs.json` (run registry + metadata)
- `eval_results/history_summary.json` (flattened trend rows)

This keeps the repo lean while allowing persistent time-based comparisons.

## Other Scripts

These scripts are still independently runnable in addition to being called by `eval.py`:

| Script | Purpose |
|---|---|
| `execute_generated.py` | Execute saved `generated_code.py` files and capture outputs |
| `aggregate_metrics.py` | Read `metadata.json` files and produce the comparison report |
| `compare_history.py` | Panel historical dashboard — `panel serve scripts/compare_history.py --args eval_results/` |
| `eval_publish.py` | Deploy the historical dashboard from existing eval results |
| `toggle_skills.py` | Enable or disable skill files (rename AGENTS.md / SKILL.md) |
| `test_setup.py` | Pre-flight environment check before running evaluations |

## Output Structure

```
eval_results/
├── <model>/                         # e.g. claude-sonnet-4.6, gpt-5.4-mini, default
│   ├── with_skills/
│   │   └── [query_id]/
│   │       ├── response.txt        # Raw Copilot output
│   │       ├── metadata.json       # Model, tokens, timing, execution result
│   │       ├── generated_code.py   # Extracted code block
│   │       ├── execution.log       # stdout/stderr from code run
│   │       ├── plot_output.html    # Saved plot (if generated)
│   │       └── screenshot.png      # Visual screenshot (if captured)
│   └── without_skills/
│       └── (same structure)
├── evaluation_results.json          # Full metrics comparison (machine-readable)
├── runs/                            # Per-run immutable snapshots
│   └── <run_id>/
│       ├── evaluation_results.json
│       └── run_metadata.json
├── runs.json                        # Compact run registry (git-commit friendly)
└── history_summary.json             # Flattened historical trend rows
```

`metadata.json` always includes a `"model"` field — either the model name passed via
`--models` or `"default"` when no model flag was used.

## Eval And Deploy

The recommended command for local parity with CI is:

```bash
pixi run -e eval evals
pixi run -e eval eval-deploy-dashboard
```

Useful environment variables:

- `EVAL_RUN_ID` (optional explicit run ID)
- `EVAL_RUN_TRIGGER` (`manual`, `ci_comment`, `ci_dispatch`, `ci_schedule`)
- `OUTERBOUNDS_CONFIG_TOKEN` (optional; configures the CLI profile before deploy)

The deploy command stages only:

- `scripts/compare_history.py`
- `eval_results/runs.json`
- `eval_results/history_summary.json`

and deploys that bundle to Outerbounds.

To deploy the dashboard without rerunning eval:

```bash
pixi run -e eval eval-deploy-dashboard
```

## Adding Queries

Edit `scripts/eval_queries.yaml`:

```yaml
queries:
  - id: my_new_query
    prompt: |
      Your prompt here...
    expected_output: static_plot   # or panel_app
    timeout: 30
    category: hvplot_basics
```

Fields:
- `id` — unique slug (lowercase, underscores or hyphens)
- `prompt` — the question/task sent to Copilot
- `expected_output` — `static_plot` or `panel_app`
- `timeout` — per-query Copilot timeout in seconds
- `category` — optional grouping tag

## Troubleshooting

**Tokens and execution time show 0**
The Copilot CLI token format changed. The parser in `eval.py` handles the current format:
`Tokens  ↑ 13.0k (6.8k cached) • ↓ 170 (128 reasoning)`. If you see zeros, capture
a raw `response.txt` and check the `Tokens` line format matches this pattern.

**Code execution fails**
Check `execution.log` in the query result directory for the full traceback.

**Warning in execution.log**
If a `DeprecationWarning` or similar appears, the relevant SKILL.md section needs a stronger anti-pattern example. Add a `# WRONG` / `# CORRECT` code pair to the relevant skill file.

**Dashboard shows "No evaluation results found"**
Run `python scripts/eval.py` first to generate `eval_results/evaluation_results.json`,
then re-launch the dashboard.
