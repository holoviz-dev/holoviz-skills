# HoloViz Skills

[![Docs](https://img.shields.io/github/actions/workflow/status/holoviz-dev/holoviz-skills/docs.yml?style=flat-square&branch=main&label=docs)](https://github.com/holoviz-dev/holoviz-skills/actions/workflows/docs.yml)

A curated collection of [Agent Skills](https://www.anthropic.com/news/skills) for the [HoloViz](https://holoviz.org) ecosystem — Panel, hvPlot, HoloViews, Param, and more.

Agent Skills are folders of instructions, scripts, and references that teach agents how to work effectively with a specific library or workflow. These skills help agents produce correct, idiomatic HoloViz code instead of guessing from stale training data.

## Installation

```bash
pip install holoviz-skills
holoviz-skills install        # auto-detects tools on your machine
```

Or target a specific tool:

```bash
holoviz-skills install --claude-code   # ~/.claude/skills/       (global)
holoviz-skills install --repo          # .agents/skills/          (cross-tool, commit to git)
holoviz-skills install --copilot       # .github/skills/
holoviz-skills install --cursor        # .cursor/rules/
holoviz-skills install --windsurf      # .windsurf/skills/
holoviz-skills install --cline         # .cline/skills/
holoviz-skills install --continue      # .continue/rules/
holoviz-skills install --gemini-cli    # .gemini/skills/
```

## Documentation

Visit **[https://holoviz-dev.github.io/holoviz-skills/](https://holoviz-dev.github.io/holoviz-skills/)** for the full list of skills and usage instructions.

## Evaluation

The `scripts/` directory contains an automated evaluation system that measures whether the skills improve Copilot's code generation quality. See [`scripts/README.md`](scripts/README.md) for details.

## Contributing

Contributions are welcome. See the [documentation](https://holoviz-dev.github.io/holoviz-skills/) for details on how skills are structured and how to add a new one.

## License

BSD — see [LICENSE.txt](LICENSE.txt).
