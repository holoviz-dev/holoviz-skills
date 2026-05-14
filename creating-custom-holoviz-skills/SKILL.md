---
name: creating-custom-holoviz-skills
description: Create new agent skills for the HoloViz ecosystem. Use when adding a skill to this repository — covers repo conventions, directory layout, routing skills, the docs pipeline, and the eval system.
---

# Creating Custom HoloViz Skills

Guide for adding a new skill to the holoviz-skills repository. This covers
what's specific to *this repo* — for general skill-authoring advice (drafting,
testing, iterating, description optimization), see the `skill-creator` skill.

## When a new skill makes sense

Add a skill when agents consistently get something wrong about a HoloViz
library or workflow and the fix can be expressed as concise, opinionated
instructions. Good candidates: API gotchas, deprecated patterns, non-obvious
conventions, correct import paths, parameter names that changed between
versions. Bad candidates: restating upstream docs, general Python knowledge,
anything the model already handles well.

## Repo layout

Skills live under one of two category directories, or at the top level for
cross-cutting concerns:

```
developing-with-holoviz/          # Using HoloViz libraries in projects
  SKILL.md                        # Routing skill — dispatches to sub-skills
  skills/
    hvplot/SKILL.md
    panel/SKILL.md
    ...

contributing-to-holoviz/          # Maintaining HoloViz packages
  SKILL.md                        # Routing skill
  skills/
    cleanup/SKILL.md
    testing/SKILL.md
    ...

creating-custom-holoviz-skills/   # This skill (top-level, standalone)
  SKILL.md
```

Pick the category that fits. If your skill is about *using* a HoloViz tool,
it goes under `developing-with-holoviz/skills/`. If it's about *contributing
to* a HoloViz package (testing, docs, releases), it goes under
`contributing-to-holoviz/skills/`.

## Adding a sub-skill

1. Create a directory: `<category>/skills/<your-skill-name>/SKILL.md`
2. Write the SKILL.md (see structure below).
3. Add an entry to the parent routing skill's Loading Table and Skill Map so
   agents know when to load your skill.
4. Run `python scripts/build_stubs.py` — this regenerates the docs pages and
   updates the nav in `zensical.toml` automatically.
5. Submit a pull request.

## SKILL.md structure

```yaml
---
name: your-skill-name        # lowercase + hyphens, ≤64 chars
description: >-              # ≤1024 chars, third person, WHAT + WHEN
  Do X for Y. Use when the user asks about Z.
---
```

After the frontmatter, write Markdown. Key principles:

- **Keep it under ~500 lines.** If you're exceeding that, split detailed
  references into separate files that the agent loads on demand.
- **Be opinionated.** State the correct way to do things, don't enumerate
  alternatives. Agents follow confident instructions better than menus.
- **Explain why.** LLMs follow reasoning better than bare directives. Instead
  of "NEVER use X", say "Avoid X because it causes Y; use Z instead."
- **Lead with what agents get wrong.** Don't restate general knowledge or
  upstream docs. Focus on hallucination patches and knowledge gaps.
- **Use code examples.** Show the correct pattern, optionally contrast with
  the common mistake: `# WRONG: ...` / `# CORRECT: ...`

## Routing skills

The top-level `SKILL.md` in each category is a *routing skill* — it doesn't
contain library instructions itself, but tells the agent which sub-skills to
load based on the user's request. If you add a sub-skill, you must update the
routing skill's two tables:

- **Loading Table** — maps user needs to sub-skill file paths (these are
  agent-facing paths in backtick code spans).
- **Skill Map** — maps sub-skill names to what they cover (these are
  doc-facing Markdown links).

## Docs pipeline

The docs site at holoviz-dev.github.io/holoviz-skills is built by Zensical.
`scripts/build_stubs.py` bridges the gap between SKILL.md files (which have
agent-facing frontmatter) and the docs (which need clean Markdown):

1. Finds every SKILL.md under non-excluded top-level directories.
2. Strips YAML frontmatter and HTML comments.
3. Rewrites internal `[name](…/SKILL.md)` links to point at sibling docs pages.
4. Writes cleaned stubs to `docs/skills/<slug>.md`.
5. Updates the `nav` block in `zensical.toml` with hierarchical sections.

You don't need to edit `zensical.toml` or `docs/` by hand — the script
handles it. Just run `pixi run build-stubs` (or `python scripts/build_stubs.py`).

## Evaluation

The `scripts/` directory has an eval system that measures whether skills
improve code generation quality. See `scripts/README.md` for full details.
To add test queries for your skill, edit `scripts/eval_queries.yaml`:

```yaml
- id: my_new_query
  prompt: |
    Your prompt here...
  expected_output: static_plot   # or panel_app
  category: hvplot_basics
```

Run `pixi run evals` to execute the full pipeline.

## Resources

- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [How to create custom Skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
