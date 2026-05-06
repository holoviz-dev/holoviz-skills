# HoloViz Skills Evaluation

Automated system to measure whether SKILL.md files improve Copilot's responses to HoloViz tasks. Runs queries with and without skills enabled, executes the generated code, and produces a comparison report.

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
```

## `eval.py` Reference

All steps are combined in a single script. Each step can be skipped independently.

```
python scripts/eval.py [options]

Options:
  --queries ID [ID ...]     Run specific query IDs only (default: all)
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
```

## Other Scripts

These scripts are still independently runnable in addition to being called by `eval.py`:

| Script | Purpose |
|---|---|
| `execute_generated.py` | Execute saved `generated_code.py` files and capture outputs |
| `aggregate_metrics.py` | Read `metadata.json` files and produce the comparison report |
| `toggle_skills.py` | Enable or disable skill files (rename AGENTS.md / SKILL.md) |
| `test_setup.py` | Pre-flight environment check before running evaluations |

## Output Structure

```
eval_results/
├── with_skills/
│   └── [query_id]/
│       ├── response.txt        # Raw Copilot output
│       ├── metadata.json       # Tokens, timing, execution result
│       ├── generated_code.py   # Extracted code block
│       ├── execution.log       # stdout/stderr from code run
│       ├── plot_output.html    # Saved plot (if generated)
│       └── screenshot.png      # Visual screenshot (if captured)
├── without_skills/
│   └── (same structure)
├── evaluation_results.json     # Full metrics comparison (machine-readable)
└── evaluation_summary.md       # Human-readable summary table
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

**`copilot: command not found`**
Install GitHub Copilot CLI: https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli

**Code execution fails**
Check `execution.log` in the query result directory for the full traceback.

**Warning in execution.log**
If a `DeprecationWarning` or similar appears, the relevant SKILL.md section needs a stronger anti-pattern example. Add a `# WRONG` / `# CORRECT` code pair to the relevant skill file.
