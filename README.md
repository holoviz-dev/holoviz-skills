# HoloViz Skills

[![Docs](https://img.shields.io/github/actions/workflow/status/holoviz-dev/holoviz-skills/docs.yml?style=flat-square&branch=main&label=docs)](https://github.com/holoviz-dev/holoviz-skills/actions/workflows/docs.yml)

A curated collection of [Agent Skills](https://www.anthropic.com/news/skills) for the [HoloViz](https://holoviz.org) ecosystem — Panel, hvPlot, HoloViews, Param, and more.

Agent Skills are folders of instructions, scripts, and references that teach agents how to work effectively with a specific library or workflow. These skills help agents produce correct, idiomatic HoloViz code instead of guessing from stale training data.


## Documentation

Visit **[https://holoviz-dev.github.io/holoviz-skills/](https://holoviz-dev.github.io/holoviz-skills/)** for the full list of skills and usage instructions. There, there are Copy Markdown icons at the top of each skill page to paste a skill directly into any AI chat if you prefer that over installing.

## Installation

```bash
pip install holoviz-skills
holoviz-skills install        # auto-detects tools on your machine
holoviz-skills install --global  # install to global (~/) paths instead
```

Or target a specific tool:

```bash
holoviz-skills install --claude-code   # .claude/skills/
holoviz-skills install --agent         # .agents/skills/          (cross-tool standard, commit to git)
holoviz-skills install --codex         # .agents/skills/           (OpenAI Codex)
holoviz-skills install --copilot       # .github/skills/           (GitHub Copilot)
holoviz-skills install --cursor        # .cursor/skills/
holoviz-skills install --windsurf      # .windsurf/skills/
holoviz-skills install --cline         # .cline/skills/
holoviz-skills install --jetbrains     # .junie/skills/            (JetBrains / Junie)
holoviz-skills install --gemini-cli    # .gemini/skills/
holoviz-skills install --antigravity   # .agents/skills/           (Google Antigravity)
holoviz-skills install --kiro          # .kiro/skills/
holoviz-skills install --kilo-code     # .kilo/skills/            (Kilo Code)
holoviz-skills install --mistral-vibe  # .vibe/skills/
```
## Evaluation

The `scripts/` directory contains an automated evaluation system that measures whether the skills improve Copilot's code generation quality. See [`scripts/README.md`](scripts/README.md) for details.

CI support for evaluations is also available through the `Eval Command` GitHub Actions workflow, including a maintainer `@run-eval` pull request comment trigger. See the GitHub Actions section in [`scripts/README.md`](scripts/README.md#github-actions-eval-command).

## Contributing

Contributions are welcome. See the [documentation](https://holoviz-dev.github.io/holoviz-skills/) for details on how skills are structured and how to add a new one.

## License

BSD — see [LICENSE.txt](LICENSE.txt).
