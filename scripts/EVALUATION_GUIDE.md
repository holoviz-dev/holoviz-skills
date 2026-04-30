# HoloViz Skills Evaluation System

Automated system to evaluate whether SKILL.md files improve Copilot's responses to HoloViz tasks.

## Quick Start

### 1. Install Dependencies

```bash
# Using pixi (recommended) - installs eval environment with all dependencies
pixi install -e eval

# That's it! Playwright setup happens automatically when you run evaluations
# (or you can run it manually: pixi run -e eval eval-setup)

# Or install manually if not using pixi
pip install pyyaml playwright holoviews hvplot bokeh pandas matplotlib
playwright install chromium
```

### 2. Run Full Evaluation

```bash
# Using pixi (recommended) - automatically sets up Playwright first
pixi run -e eval evals

# Run specific queries only (quick test with single query)
pixi run -e eval evals --queries hvplot_basic_line

# Run multiple specific queries
pixi run -e eval evals --queries hvplot_basic_line hvplot_interactive_scatter

# Faster evaluation without screenshots (no Playwright setup needed)
pixi run -e eval eval-no-screenshots

# Or run directly with Python
cd scripts
python run_full_evaluation.py
```

This will:
1. Run Copilot queries with and without SKILL.md files enabled
2. Execute the generated code
3. Generate comparison reports

  - Each query has: `response.txt`, `generated_code.py`, `execution.log`, `screenshot.png`
- `without_skills/` - Results without SKILL.md files
  - Same structure as above
- `evaluation_results.json` - **Single comprehensive JSON with all metrics and comparisons**SKILL.md files enabled
- `without_skills/` - Results without SKILL.md files
- `metrics_summary.json` - Detailed comparison data
- `metrics.csv` - Metrics in spreadsheet format
- `README.md` - Results overview

## Individual Scripts

### run_eval.py - Main Evaluation Runner

Runs Copilot queries and captures responses.

```bash
# Run all queries
python run_eval.py

# Run specific queries
python run_eval.py --queries hvplot_basic_line

# Run with-skills evaluation only
python run_eval.py --skip-without-skills

# Custom output directory
python run_eval.py --output ./my_results
```

### execute_generated.py - Code Execution

Executes generated code and captures results.

```bash
# Execute all generated code
python execute_generated.py

# Execute with longer timeout
python execute_generated.py --timeout 60

# Execute specific queries only
python execute_generated.py --queries hvplot_basic_line

# Skip screenshots (faster, useful for quick tests)
python execute_generated.py --skip-screenshots
```

### aggregate_metrics.py - Metrics Aggregation

Generates comparison reports and metrics.

```bash
# Aggregate all metrics
python aggregate_metrics.py

# Custom evaluation results directory
python aggregate_metrics.py --eval-results ./my_results
```

### toggle_skills.py - Skills Management

Utility to enable/disable SKILL.md files.

```bash
# Check current status
python toggle_skills.py status

# Disable all skills
python toggle_skills.py disable

# Enable all skills
python toggle_skills.py enable

# Use custom root directory
python toggle_skills.py status --root /path/to/repo
```

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

### Query Fields

- `id`: Unique identifier (lowercase, hyphens only)
- `prompt`: The question/task for Copilot
- `expected_output`: Type of output (`static_plot` or `panel_app`)
- `timeout`: Maximum execution time in seconds
- `category`: Optional grouping tag

## Advanced Usage

### Run Specific Pipeline Steps

```bash
# Only generate code (skip execution)
python run_full_evaluation.py --skip-execution

# Only evaluation and execution (skip metrics)
python run_full_evaluation.py --skip-aggregation

# Combine options
python run_full_evaluation.py --queries hvplot_basic_line --skip-execution
```

### Compare Multiple Runs

```bash
# Run evaluation with different configurations
python run_eval.py --output ./results_v1
python run_eval.py --output ./results_v2

# Compare results
python aggregate_metrics.py --eval-results ./results_v1
python aggregate_metrics.py --eval-results ./results_v2
```

### Debugging

```bash
# Test Copilot CLI directly
copilot -p "Create a line plot with hvplot"

# Check skill status
python toggle_skills.py status

# Manually execute generated code
cd eval_results/with_skills/hvplot_basic_line
python generated_code.py
```

## Output Structure

```
eval_results/
├── with_skills/
│   ├── hvplot_basic_line/
│   │   ├── execution.log         # Execution output (if run)
│   │   ├── plot_output.html      # HTML plot (if generated)
│   │   └── screenshot.png        # Visual screenshot
│   └── hvplot_interactive_scatter/
├── without_skills/
│   └── (same structure)
└── evaluation_results.json      # Single JSON with all comparisons
├── metrics_summary.json          # Detailed comparison
├── metrics.csv                   # Spreadsheet-friendly format
└── README.md                     # Results overview
```

## Metrics Collected

For each query, the system collects:

- **Token Usage**: Input, output, cached, and reasoning tokens
- **Response Time**: How long Copilot took to respond
- **Code Generation**: Whether code was generated
- **Execution Success**: Whether generated code runs without errors
- **Execution Time**: How long code took to execute

## Troubleshooting

### "copilot: command not found"

Install GitHub Copilot CLI:
```bash
# See: https://docs.github.com/en/copilot/github-copilot-in-the-cli
```

### "No such file or directory: eval_queries.yaml"

Make sure you're running from the `scripts/` directory:
```bash
cd scripts
python run_eval.py
```

### Code execution fails

- Check `execution.log` in the query directory for error details
- Try running generated code manually to diagnose issues
- Increase timeout: `--timeout 60`

### Skills not being toggled

- Verify SKILL.md files exist: `python toggle_skills.py status`
- Check file permissions
- Ensure you're running from the correct directory

## Development

### Adding New Queries

1. Edit `eval_queries.yaml`
2. Add your query following the existing format
3. Run evaluation: `python run_eval.py --queries your_query_id`

### Modifying Scripts

All scripts are standalone Python files in the `scripts/` directory:
- `run_eval.py` - Main evaluation logic
- `execute_generated.py` - Code execution
- `aggregate_metrics.py` - Metrics aggregation
- `toggle_skills.py` - Skills management utility
- `run_full_evaluation.py` - Orchestrator

### Dependencies

- Python >= 3.12
- PyYAML (for reading query definitions)
- GitHub Copilot CLI (for running queries)

- Playwright (optional, for screenshot capture)
  - Install with: `pip install playwright && playwright install chromium`
## Future Enhancements

Potential improvements to consider:

- Screenshot capture with Playwright for visual outputs
- Automated visual similarity comparison
- Support for Panel dashboard apps
- Code quality metrics (complexity, style)
- Performance benchmarking
- CI/CD integration
- Multi-model comparison

## Contributing

When adding new evaluation queries:
1. Keep prompts clear and specific
2. Test queries manually first
3. Document expected behavior
4. Consider both positive and edge cases

## License

BSD License (same as holoviz-skills repository)
