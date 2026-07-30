<div data-all-skills-zip style="display:none"></div>

# HoloViz Skills

A curated collection of [Agent Skills](https://www.anthropic.com/news/skills) for the [HoloViz](https://holoviz.org) ecosystem — Panel, hvPlot, HoloViews, Param, and more.

## What are Agent Skills?

Agent Skills are folders of instructions, scripts, and references that teach AI agents how to work effectively with a specific library or workflow. These skills help agents produce correct, idiomatic HoloViz code instead of guessing from stale training data.

## Available Skills

- [Developing with HoloViz](developing-with-holoviz/index.md) — skills for building apps with Panel, hvPlot, HoloViews, Param, and more
- [Contributing to HoloViz](contributing-to-holoviz/index.md) — skills for maintaining and contributing to HoloViz packages
- [Creating Custom Skills](creating-custom-holoviz-skills.md) — guide for adding new skills to this repository

## Using Skills

Agent Skills are supported by a growing number of AI coding tools. The quickest way to install them is via the CLI:

```bash
pip install holoviz-skills
holoviz-skills install        # auto-detects tools on your machine
holoviz-skills install --global  # install to global (~/) paths instead
```

Or target a specific tool:

```bash
holoviz-skills install --claude-code   # .claude/skills/
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
holoviz-skills install --agent         # .agents/skills/          (cross-tool standard, commit to git)
```

Alternatively, use the **Download ZIP** icon at the top of any skill page, or grab the whole collection at once. Each category and sub-skill also has its own ZIP, published as assets on the [latest release](https://github.com/holoviz-dev/holoviz-skills/releases/latest).

See your tool's documentation for manual setup instructions:

[Claude Code / Cowork](https://code.claude.com/docs/en/skills) · [GitHub Copilot](https://code.visualstudio.com/docs/copilot/customization/agent-skills) · [OpenAI Codex](https://developers.openai.com/codex/skills) · [Cursor](https://cursor.com/docs/skills) · [Windsurf](https://docs.windsurf.com/windsurf/cascade/skills) · [Cline](https://docs.cline.bot/customization/skills) · [JetBrains AI](https://www.jetbrains.com/help/ai-assistant/settings-reference-skills.html) · [Gemini CLI](https://geminicli.com/docs/cli/skills/) · [Antigravity](https://antigravity.google/docs/skills) · [Kiro](https://kiro.dev/docs/skills) · [Kilo Code](https://kilo.ai/docs/customize/skills) · [Mistral Vibe](https://docs.mistral.ai/mistral-vibe/agents-skills)

You can also click the **Copy Markdown** icon at the top of each skill page to paste a skill directly into any AI chat. Claude Desktop / Cowork users can install a category as a pre-built plugin from the [latest release](https://github.com/holoviz-dev/holoviz-skills/releases/latest) — one `.plugin` per category, e.g. `developing-with-holoviz.plugin`, `contributing-to-holoviz.plugin`, and `creating-custom-holoviz-skills.plugin`.

## Contributing

Contributions are welcome! To add a new skill:

1. Fork the repository
2. Create a new folder under an appropriate category
3. Add a `SKILL.md` file following the template structure
4. Submit a pull request

See [Creating Custom HoloViz Skills](creating-custom-holoviz-skills.md) for guidance on authoring new skills.

## License

BSD — see [LICENSE.txt](https://github.com/holoviz-dev/holoviz-skills/blob/main/LICENSE.txt).
