---
name: pr-description
description: Writing a clear pull request description for HoloViz packages. Use when drafting or reviewing the description, summary, or write-up of a PR in any HoloViz repository.
metadata:
  version: "2026.08.28"
  author: holoviz
---

# PR Descriptions

Write HoloViz PR descriptions in the first person, as work you did, and keep the prose free of em dashes.

Follow the repo's PR template rather than inventing sections. Every HoloViz repo inherits it from the org-wide `holoviz/.github` repo, so fetch the current, authoritative sections from the raw template and fill each one in:

https://raw.githubusercontent.com/holoviz/.github/refs/heads/main/.github/pull_request_template.md

## Contents

- [Writing each part well](#writing-each-part-well)
- [Voice and style](#voice-and-style)

## Writing each part well

- **Title:** conventional-commit style (`fix:`, `feat:`, `docs:`, `chore:`) summarizing the change in one line.
- **Description:** 2-3 sentences in your own words on what changed and why, with the motivation and a minimal reproducible example. Write the example per the [`minimal-example` skill](../minimal-example/SKILL.md) so a reviewer can paste and run it unchanged. Flag any breaking change, API change, new dependency, or migration step prominently so a reviewer cannot miss it.
- **Before / After:** include for any observable or visual change (behavior, UI, plotting, rendered docs) with screenshots, GIFs, or video, labelled old versus new. Skip it when there is nothing to compare, such as docs or refactors.
- **AI disclosure:** if AI was used, name the tool and model (for example Claude Code + Opus) and how it was used, and never delete the section. Non-disclosure can result in a ban.

## Voice and style

Write dense, causal prose rather than a padded list. When a PR makes several distinct changes, prefer a short bullet list with one bullet per change, each a complete change-then-mechanism statement (not a fragment); a single-change PR can be one short paragraph instead. Either way keep it skimmable, and add a short "How to test" note or a minimal reproducible example.

- Lead with the change, then the mechanism, e.g. "This PR adds X, where ...". State what changed before how it works.
- One bullet per independent change that needs context beyond the diff. Trivial file changes (a one-line README addition, a standard config file, a pixi task update) are visible in the diff and do not need a bullet. Pack the cause and effect into each bullet rather than splitting across several, e.g. "Fixed the Viewer example, which created widgets before `super().__init__()`; values synced but notifications didn't, so callbacks never fired."
- Don't hard-wrap inside a bullet or paragraph: keep each bullet on a single line. A PR description is a GitHub comment field, where every single newline renders as a line break (unlike a committed `.md` file), so wrapping shows up as mid-sentence breaks.
- Chain cause and effect within a sentence ("captured once, meaning ...", "watches it, triggering ... so ...") instead of many short, disconnected ones.
- Explain the motivation once; don't justify every step or restate the diff. State what each part does and trust the reader and the diff for the rest. Drop implementation details (how a script parses, what regex it uses) that the diff already shows; a bullet should say what something does for the reviewer, not how it works internally.
- Keep concrete anchors (key identifiers, field names, a minimal example) even while compressing, so it stays specific.
- Stay neutral and declarative; drop selling adverbs like "cleanly", "simply", or "robustly".
- Reserve backticks for concrete symbols (`obs_id`, `None`, function and parameter names); let conceptual names read as plain prose.
- After drafting, run the [`deslop` skill](../deslop/SKILL.md) scanner on the description to catch LLM prose patterns (AI vocabulary, selling adverbs, em-dash overuse, negative parallelism). Fix every hit that isn't a false positive.

## Example

A PR that adds a routing index, a sync checker, and a build script to a docs repo.

**Before (over-detailed):**

```
docs: add SKILL.md routing index and llms.txt

The docs had no machine-readable index, so an LLM agent had no way to
find the right page without scanning every file. This PR adds two entry
points for agents and the tooling to keep them in sync.

* `SKILL.md` at the repo root routes agents that have the checkout on
  disk. It maps user needs to page short names, with a path pattern so
  the agent resolves any name to `docs/{category}/{page}.md`. Covers
  all six categories, the three reference files, and the demo projects.
* `scripts/build_llms.py` generates `builtdocs/llms.txt` during the
  docs build by stripping SKILL.md's YAML frontmatter and rewriting
  file paths to site URLs. Not committed; produced after the site build
  and published to Pages alongside the HTML.
* `scripts/check_sync.py` is a pre-commit hook that checks every page
  on disk is referenced in SKILL.md and every name in SKILL.md resolves
  to a real file. It parses the table headers to derive the category,
  then expands short names to full paths.
* `.pre-commit-config.yaml` wires up the sync check plus ruff
  lint/format, trailing-whitespace, end-of-file-fixer, check-yaml,
  check-merge-conflict, and check-added-large-files.
* `README.md` gets one line linking to SKILL.md.
* `pixi.toml` appends the build script to the docs-build task.
```

Problems: bullets for trivial changes (README one-liner, pixi.toml one-liner, standard pre-commit config), implementation details the diff shows (how the sync script parses headers), and mechanism repeated in every bullet.

**After (compressed):**

```
docs: add SKILL.md routing index and llms.txt

The docs had no machine-readable index, so an LLM agent had no way to
find the right page without scanning every file. This PR adds two entry
points for agents and the tooling to keep them in sync.

* `SKILL.md` at the repo root routes agents that have the checkout on
  disk. It maps user needs to page short names.
* `scripts/build_llms.py` generates `builtdocs/llms.txt` during the
  docs build by stripping SKILL.md's frontmatter and rewriting file
  paths to site URLs. Not committed; produced after the site build.
* `scripts/check_sync.py` is a pre-commit hook that checks every page
  on disk is referenced in SKILL.md and vice versa.
```

Three bullets for three things that need context. README, pixi.toml, and pre-commit config are obvious from the diff. The sync script bullet says what it checks, not how it parses.
