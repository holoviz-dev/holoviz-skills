# HoloViz Skills

[![Docs](https://img.shields.io/github/actions/workflow/status/holoviz-dev/holoviz-skills/docs.yml?style=flat-square&branch=main&label=docs)](https://github.com/holoviz-dev/holoviz-skills/actions/workflows/docs.yml)

A curated collection of [Agent Skills](https://www.anthropic.com/news/skills) for the [HoloViz](https://holoviz.org) ecosystem — Panel, hvPlot, HoloViews, Param, and more.

Agent Skills are folders of instructions, scripts, and references that teach agents how to work effectively with a specific library or workflow. These skills help agents produce correct, idiomatic HoloViz code instead of guessing from stale training data.


## Documentation

Visit **[https://holoviz-dev.github.io/holoviz-skills/](https://holoviz-dev.github.io/holoviz-skills/)** for the full list of skills and usage instructions. There, there are Copy Markdown icons at the top of each skill page to paste a skill directly into any AI chat if you prefer that over installing. Each category page also has a Context cost table showing how much an agent reads for each kind of task.

## Installation

**With uv**, nothing to install first:

```bash
uvx holoviz-skills install developing     # Panel, hvPlot, HoloViews, Param; auto-detects your tools
uvx holoviz-skills install contributing   # for HoloViz maintainers
uvx holoviz-skills install developing --global --claude-code   # ~/.claude/skills, every project
```

`pip install holoviz-skills` gives you the same `holoviz-skills` command.

**As a Claude Code plugin:**

```text
/plugin marketplace add holoviz-dev/holoviz-skills
/plugin install holoviz@holoviz-skills
/plugin install panel-live-server@holoviz-skills   # optional: lets the agent render and screenshot Panel apps
```

The `holoviz` plugin brings all three skills; to install just one, use uvx or npx. `panel-live-server` runs Python on your machine to render what the agent builds, which is why it's a separate plugin you opt into.

**With the skills.sh CLI:**

```bash
npx skills add holoviz-dev/holoviz-skills --skill developing-with-holoviz
```

`npx skills update` follows the GitHub `main` branch, while `uvx holoviz-skills@latest update` follows PyPI releases, so two machines can differ by whatever has merged since the last release.

### Keeping skills current

```bash
uvx holoviz-skills@latest update   # re-install what you have, listing which skills changed
uvx holoviz-skills doctor          # stale copies, your HoloViz library versions, compatibility
```

### AGENTS.md

Don't paste the skills into `AGENTS.md`: that file loads on every task, while installed skills load only when one is needed.

### All tool flags

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
