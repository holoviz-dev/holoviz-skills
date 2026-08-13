---
name: creating-custom-holoviz-skills
description: Create new agent skills for the HoloViz ecosystem. Use when adding a skill to this repository — covers repo conventions, directory layout, routing skills, the docs pipeline, and the eval system.
metadata:
  version: "2026.08.13"
  author: holoviz
---

# Creating Custom Skills

Guide for adding a new skill to the holoviz-skills repository. This covers
what's specific to *this repo* — for general skill-authoring advice (drafting,
testing, iterating, description optimization), see the [`skill-creator` skill](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md).

## Contents

- [Deciding to add a skill](#deciding-to-add-a-skill)
- [Repo layout](#repo-layout)
- [Adding a sub-skill](#adding-a-sub-skill)
- [SKILL.md structure](#skillmd-structure)
  - [Versioning](#versioning)
- [Resource files](#resource-files)
  - [Splitting references](#splitting-references)
  - [Naming references](#naming-references)
  - [Nesting in docs](#nesting-in-docs)
- [Routing skills](#routing-skills)
- [Docs pipeline](#docs-pipeline)
- [Evaluation](#evaluation)
- [Resources](#resources)

## Deciding to add a skill

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
3. Optionally add sibling `*.md` reference files for detailed lookup material.
4. Add an entry to the parent routing skill's Loading Table and Skill Map so
   agents know when to load your skill. If you added reference files, make each
   one reachable from a Loading Table user-need row that pairs it with the
   sub-skill (e.g. "Filterable data table → `panel/SKILL.md` + `using-tabulator.md`").
   The full per-reference index belongs in the sub-skill's own References
   section — don't duplicate it as a sub-table in the routing skill, which loads
   on *every* task in the category and would carry that cost regardless of
   relevance. A reference reachable from neither a Loading Table row nor the
   sub-skill's References section still ships in the docs, but agents won't know
   to load it.
5. Run `python scripts/build_stubs.py` — this regenerates all docs pages and
   updates `zensical.toml` automatically. **Do not edit `zensical.toml` by
   hand** — the script manages the nav, including nested sections for skills
   with reference files.
6. Preview with `pixi run docs` (runs `zensical serve`).
7. Submit a pull request.

## SKILL.md structure

```yaml
---
name: your-skill-name        # lowercase + hyphens, ≤64 chars, must match directory name
description: >-              # ≤1024 chars, third person, WHAT + WHEN
  Do X for Y. Use when the user asks about Z.
# Optional fields:
license: BSD-3-Clause
compatibility: Requires panel>=1.5
user-invocable: true         # false hides from the /slash-command menu; see Routing skills
disable-model-invocation: false  # true = manual invocation only (use for skills with side effects)
argument-hint: "[component] [description]"  # shown in slash-command input
allowed-tools: Read Grep Glob Bash(python:*)  # experimental: pre-approve tools
metadata:
  version: "0.1.0"           # see Versioning below
  author: holoviz
---
```

### Versioning

`metadata.version` is per-skill and independent of the package version and of
the other skills — `build_stubs.py` renders it into each docs page as *Skill
version X.Y.Z*, so it describes that skill's content, not the release it shipped
in. New skills start at `0.1.0`.

**Patch bumps are automatic.** The `bump skill version on edit` pre-commit hook
(`scripts/bump_skill_version.py`) maps each staged file to its owning skill —
the nearest ancestor directory with a SKILL.md, so editing a reference file
bumps its sub-skill — and patch-bumps that skill once per branch, comparing
against the merge-base with `main` rather than the previous commit. The hook
exits non-zero after writing, so the commit needs re-running; that's expected,
not a failure. Don't hand-bump a patch to save it the trouble.

**Bump the minor component yourself** when the change is more than a fix —
a new section or reference file, or changed guidance an agent would act on
differently (a new recommended API, a reversed recommendation, a new gotcha).
The hook respects any version you set: it only acts when the staged value still
matches the merge-base, so a manual bump makes it a no-op for that skill.

Leave the *other* skills' versions alone. They diverged once before and were
reset to a uniform baseline, which only stays meaningful if each bump tracks a
real change to that skill.

After the frontmatter, write Markdown. Key principles:

- **Start with a Contents section.** Agents may only read the first ~100
  lines. A table of contents at the top lets them see every section and
  decide what to load. List References first if the skill has them — this
  tells the agent what deeper material is available before it reads the
  core instructions.
- **Keep it under ~500 lines.** If you're exceeding that, split detailed
  references into separate files that the agent loads on demand (see
  Resource files below).
- **Be opinionated.** State the correct way to do things, don't enumerate
  alternatives. Agents follow confident instructions better than menus.
- **Explain why.** LLMs follow reasoning better than bare directives. Instead
  of "NEVER use X", say "Avoid X because it causes Y; use Z instead."
- **Lead with what agents get wrong.** Don't restate general knowledge or
  upstream docs. Focus on hallucination patches and knowledge gaps.
- **Use code examples.** Show the correct pattern, optionally contrast with
  the common mistake: `# WRONG: ...` / `# CORRECT: ...`

## Resource files

A skill is a directory, not just a single file. Place supporting files
alongside SKILL.md and reference them with relative paths. The agent loads
these on demand (L3) — they consume zero context tokens until actually read.

```
panel/
  SKILL.md                        # Core instructions (always loaded when skill triggers)
  iterating-on-panel-apps.md      # Reference — serve, screenshot, debug loop
  building-custom-components.md   # Reference — JSComponent, ReactComponent, CDN guide
  using-material-ui.md            # Reference — pmui.Page, layouts, gotchas, theming
  examples/
    dashboard.py                  # Runnable example — agent can read or execute
    wizard.py
  scripts/
    validate_app.py               # Agent runs this; only stdout enters context
```

Place reference `.md` files flat alongside SKILL.md — not in a subdirectory.
The agent loads these on demand; they consume zero context tokens until read.

Use resource files when:

- **Sibling `.md` files** — Detailed lookup tables, API surfaces, or extended
  docs that would bloat SKILL.md. The agent reads these only when it needs
  specifics. Good for: widget mapping tables, full parameter lists, template
  comparisons. Each reference file should have its own Contents TOC at the top.
- **examples/** — Runnable code the agent can copy, adapt, or execute. Better
  than inline code blocks for multi-file apps or examples over ~30 lines.
  Reference from SKILL.md: "See `examples/basic_app.py` for a working starter."
- **scripts/** — Executable scripts the agent runs via Bash. The script code
  itself never enters the context window — only its output does. Use for
  validation, linting, scaffolding, or any deterministic operation. Each
  non-test `.py` file also gets a docs page under a "Scripts" nav node;
  `test_*.py` and `_`-prefixed files are skipped.
- **assets/** — Templates, sample data, config files the agent fills in or
  copies. Good for: project scaffolds, CI configs, test fixtures.

The key insight: SKILL.md should contain the *judgment calls* (what to do and
why), while resource files hold the *reference material* (exact APIs, working
examples, executable tools). This keeps the core instructions lean while
giving the agent access to deep detail when it needs it.

### Splitting references

There's a real tension to balance, not a fixed rule:

- **Each reference is a separate read** — a tool call the agent must make, which
  adds latency. Lots of tiny files means lots of round-trips.
- **But an over-long file may not be read in full** — an agent often reads only
  the first ~100 lines and then decides. That's *fine* as long as the file opens
  with a complete Contents TOC, so the agent can see everything the file covers
  and jump to the relevant section even without reading linearly.

So aim for a moderate number of **focused-but-substantial** references, each
opening with a full TOC — not a swarm of stubs, and not one monolith.

Decide splits by **user story / trigger**, because the routing skill matches a
user's need to a file. Concretely:

- **Merge two references when they answer the same "I want to…".** Splitting
  layout from theming, or a build-loop from its review checklist, just creates
  two reads for one intent. (e.g. `applying-` + `branding-material-ui` →
  `using-material-ui`; `structuring-` + `scaling-panel-apps` →
  `designing-panel-architecture`.)
- **Keep them separate when the trigger differs.** "Build a new app" vs "migrate
  an existing one" vs "test it" are distinct moments — merging them forces
  irrelevant material into context and muddies routing.

When you merge, give the combined file a grouped TOC (e.g. "Building:" then
"Theming:") so the broadened scope stays scannable.

### Naming references

Use lowercase-with-hyphens for filenames (`custom-components.md`, not
`custom_components.md` or `CustomComponents.md`) — consistent with skill
directory naming and avoids mixed conventions in docs URLs.

Use action-oriented H1 titles without the parent skill's name — the context
is already clear from the directory structure. Titles appear in the docs
sidebar navigation, so keep them concise.

```
# ✅ Good — action-oriented, no redundant prefix
Building Custom Components
Using Material UI
Designing Panel Architecture
Plotting in Panel

# ❌ Bad — repeats "Panel" from the parent skill
Panel Custom Components
Using Panel Material UI effectively
Panel + HoloViews Integration
```

### Nesting in docs

When `build_stubs.py` finds sibling `.md` files alongside a SKILL.md, it
automatically creates a nested docs section: the SKILL.md becomes
`panel/index.md` and each sibling becomes a page (`panel/custom-components.md`,
etc.). Links like `[name](foo.md)` in SKILL.md resolve naturally in both the
source directory and the docs output. No manual nav configuration needed.

`.py` files in `examples/` and `scripts/` become pages too, grouped under
"Examples" and "Scripts" nav nodes. All of these flatten into the *same* docs
directory, so a reference, an example, and a script can't share a stem —
`build_stubs.py` warns when they do rather than silently overwriting a page.
Examples are served and screenshotted; scripts are published as source only.

## Routing skills

The top-level `SKILL.md` in each category is a *routing skill* — it doesn't
contain library instructions itself, but tells the agent which sub-skills to
load based on the user's request. If you add a sub-skill, you must update the
routing skill's two tables:

- **Loading Table** — maps user needs to sub-skill file paths (these are
  agent-facing paths in backtick code spans).
- **Skill Map** — maps sub-skill names to what they cover (these are
  doc-facing Markdown links).

Don't list a sub-skill's reference files exhaustively in the routing skill (no
"references sub-table"). The routing skill loads on *every* task in its category,
so a per-reference index there costs context even for unrelated work, and it
duplicates the sub-skill's own References section. Instead, give each reference a
Loading Table user-need row paired with its sub-skill, and let the sub-skill's
References section be the single full index.

### Only routing skills are real skills

The host registers one skill per *top-level* directory — the routing SKILL.md.
Sub-skills under `skills/` are not registered: to the host they're ordinary
`.md` files that the routing table tells the agent to read. So there is no
`/panel` or `/testing` slash command, and adding `user-invocable` to a
sub-skill's frontmatter does nothing. Only a top-level skill can carry
`user-invocable`, `argument-hint`, or `allowed-tools` and have them take effect.

Keep routing skills `user-invocable: true` and give them an `argument-hint`
listing the main entry points from the Loading Table. Typing
`/developing-with-holoviz dashboard` is the closest thing to invoking a
sub-skill directly: the routing table resolves the argument to the right
sub-skill files. `user-invocable: false` on a routing skill makes the whole
category unreachable by slash command, since the sub-skills can't be reached
that way either.

## Docs pipeline

The docs site at holoviz-dev.github.io/holoviz-skills is built by Zensical.
`scripts/build_stubs.py` bridges the gap between SKILL.md files (which have
agent-facing frontmatter) and the docs (which need clean Markdown):

1. Finds every SKILL.md under non-excluded top-level directories.
2. Strips YAML frontmatter and HTML comments.
3. Rewrites internal `[name](…/SKILL.md)` links to point at sibling docs pages.
4. For skills with sibling `.md` files, or an `examples/` or `scripts/`
   directory, creates a nested directory (`panel/index.md` +
   `panel/custom-components.md` + `panel/preflight.md`, etc.).
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
  expected_output: static_plot
  category: hvplot_basics
```

Run `pixi run evals` to execute the full pipeline.

Note: coverage is currently thin — only the `hvplot` skill has any eval
queries today, and the `expected_output`/`category` fields are documentation
only (not read or enforced by `eval.py`). Adding queries for your skill is a
useful, but not blocking, contribution.

## Resources

- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [How to create custom Skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
