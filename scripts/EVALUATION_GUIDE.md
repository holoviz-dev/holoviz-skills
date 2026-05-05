# HoloViz Skills Evaluation System

Automated system to evaluate whether SKILL.md files improve Copilot's responses to HoloViz tasks.

## Quick Start

```bash
# 1. Install all dependencies
pixi run setup-dev

# 2. Check the system is ready
pixi run eval-check

# 3. Run the full evaluation
pixi run evals

# Run specific queries only
pixi run evals --queries hvplot_basic_line

# Run without screenshots (faster, no Playwright needed)
pixi run eval-no-screenshots
```

This will:
1. Run Copilot queries with and without SKILL.md files enabled
2. Execute the generated code
3. Save results to `eval_results/`

## Output Structure

```
eval_results/
├── with_skills/
│   └── [query_id]/
│       ├── response.txt           # Raw Copilot output
│       ├── metadata.json          # Metrics and metadata
│       ├── generated_code.py      # Extracted code
│       ├── execution.log          # Execution output
│       ├── plot_output.html       # HTML plot (if generated)
│       └── screenshot.png         # Visual screenshot (if captured)
├── without_skills/
│   └── (same structure)
├── evaluation_results.json        # All metrics and comparisons (JSON)
└── evaluation_summary.md          # Human-readable summary report
```

## Metrics Collected

For each query, the system collects:

- **Token Usage**: Input, output, cached, and reasoning tokens
- **Response Time**: How long Copilot took to respond
- **Code Generation**: Whether code was generated
- **Execution Success**: Whether generated code runs without errors
- **Execution Time**: How long the code took to execute

## Test Queries

Edit `scripts/eval_queries.yaml` to add or modify test queries:

```yaml
queries:
  - id: my_new_query
    prompt: |
      Your prompt here...
    expected_output: static_plot  # or panel_app
    timeout: 30
    category: hvplot_basics
```

Query fields:

- `id`: Unique identifier (lowercase, hyphens only)
- `prompt`: The question/task for Copilot
- `expected_output`: Type of output (`static_plot` or `panel_app`)
- `timeout`: Maximum execution time in seconds
- `category`: Optional grouping tag

## Advanced Usage

Run only a specific condition using the `--skills` flag:

```bash
# Only run the with-skills condition
python scripts/run_full_evaluation.py --skills with

# Only run the without-skills condition
python scripts/run_full_evaluation.py --skills without

# Run both (default)
python scripts/run_full_evaluation.py --skills both
```

The same flag is available on `run_eval.py` directly:

```bash
python scripts/run_eval.py --skills with --queries hvplot_basic_line
```

## Troubleshooting

### "copilot: command not found"

Install GitHub Copilot CLI — see https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli

### Code execution fails

Check `execution.log` in the query directory for error details.

## License

BSD License
