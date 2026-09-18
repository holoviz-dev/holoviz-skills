---
name: pr-description
description: Writing a clear pull request description for HoloViz packages. Use when drafting or reviewing the description, summary, or write-up of a PR in any HoloViz repository.
metadata:
  version: "2026.09.14"
  author: holoviz
---

# PR Descriptions

Write HoloViz PR descriptions in the first person, as work you did.

Follow the repo's PR template rather than inventing sections. Every HoloViz repo inherits it from the org-wide `holoviz/.github` repo, so fetch the current, authoritative sections from the raw template and fill each one in:

https://raw.githubusercontent.com/holoviz/.github/refs/heads/main/.github/pull_request_template.md

The template carries HTML comments with instructions for each section. Read them, then delete them.

## Contents

- [Writing each part well](#writing-each-part-well)
- [Voice and style](#voice-and-style)

## Writing each part well

The template's sections are authoritative; fetch them rather than working from the bullets below, which cover how to fill a section well, not which sections exist. The title is a separate PR field, not a template section.

- **Title:** conventional-commit style (`fix:`, `feat:`, `docs:`, `chore:`) summarizing the change in one line.
- **Description:** summarize the change and its motivation in your own words, say which issue it fixes, describe the tests you ran to verify it, and include a copy-pastable minimal reproducible example. Write the example per the [`minimal-example` skill](../minimal-example/SKILL.md) so a reviewer can paste and run it unchanged. Add visuals for any observable or visual change (behavior, UI, plotting, rendered docs) as screenshots, GIFs, or video, labelled old versus new; skip them when there is nothing to compare, such as docs or refactors. Flag any breaking change, API change, new dependency, or migration step prominently so a reviewer cannot miss it.
- **`Fixes #{issue}`:** replace the placeholder with the issue number, or delete the line when the PR fixes no filed issue. Leaving `#{issue}` in place renders literally.
- **AI Disclosure:** delete the section only if AI was not used. Otherwise name the tool and model on `Tool & Model:` (for example `Claude Code + Opus 4.6`), say briefly on `Usage:` what it did, and leave both checkboxes for the author to tick, since they are statements about the author's own testing and responsibility. Non-disclosure can result in a ban.
- **Checklist:** keep the items that apply and remove the rest. "Tests added and are passing" stays unticked until the tests exist and pass, and per the [`testing` skill](../testing/SKILL.md) a new test must fail on `main` first. "Added documentation" goes when the PR adds or changes user-facing behavior.

## Voice and style

Write dense, causal prose rather than a padded list. When a PR makes several distinct changes, a short bullet list with one bullet per change works well, but two or three sentences in a paragraph are equally fine when the changes are closely related and don't need to be scanned independently. Use `-` for bullets, not `*`. Either way keep it skimmable.

- Lead with the change, then the mechanism, e.g. "This PR adds X, where ...". State what changed before how it works.
- One bullet per independent change that needs context beyond the diff. Trivial file changes (a one-line README addition, a standard config file, a pixi task update) are visible in the diff and do not need a bullet. Pack the cause and effect into each bullet rather than splitting across several, e.g. "Fixed the Viewer example, which created widgets before `super().__init__()`; values synced but notifications didn't, so callbacks never fired."
- Don't hard-wrap inside a bullet or paragraph: keep each bullet on a single line. A PR description is a GitHub comment field, where every single newline renders as a line break (unlike a committed `.md` file), so wrapping shows up as mid-sentence breaks.
- Chain cause and effect within a sentence ("captured once, meaning ...", "watches it, triggering ... so ...") instead of many short, disconnected ones.
- Explain the motivation once; don't justify every step or restate the diff. State what each part does and trust the reader and the diff for the rest. Drop implementation details (how a script parses, what regex it uses) that the diff already shows; a bullet should say what something does for the reviewer, not how it works internally.
- Keep concrete anchors (key identifiers, field names, a minimal example) even while compressing, so it stays specific.
- Reserve backticks for concrete symbols (`obs_id`, `None`, function and parameter names); let conceptual names read as plain prose.
- After drafting, run the [`deslop` skill](../deslop/SKILL.md) scanner on the description to catch LLM prose patterns (AI vocabulary, selling adverbs, em-dash overuse, negative parallelism). Fix every hit that isn't a false positive. Scan the prose only: leave the template's headings, checkboxes and `Fixes #` line intact, and don't scan the minimal example, since a reproducer's repeated imports and parallel assignments are not prose tics. A colon-into-a-triple inside an `AI Disclosure` `Usage:` field is a form field rather than a rhetorical flourish, so it stays.
- Writing the description is the moment to re-read the diff's comments against the [`cleanup` skill](../cleanup/SKILL.md). Drafting the mechanism in prose exposes comments that narrate the same mechanism at length, and a comment only needs the constraint and what must remain true; the symptom, the trace and the reproducer belong in the description, which is why the two get written together. Check too that the change hasn't left a neighbouring comment describing behavior the diff removed.

## Example

A PR that adds a routing index, a sync checker, and a build script to a docs repo.

**Before (over-detailed, no motivation):**

```
docs: add SKILL.md routing index and llms.txt

This PR adds a SKILL.md routing index, an llms.txt build script,
a sync checker, and pre-commit hooks.

- `SKILL.md` at the repo root routes agents that have the checkout on
  disk. It maps user needs to page short names, with a path pattern so
  the agent resolves any name to `docs/{category}/{page}.md`. Covers
  all six categories, the three reference files, and the demo projects.
- `scripts/build_llms.py` generates `builtdocs/llms.txt` during the
  docs build by stripping SKILL.md's YAML frontmatter and rewriting
  file paths to site URLs. Not committed; produced after the site build
  and published to Pages alongside the HTML.
- `scripts/check_sync.py` is a pre-commit hook that checks every page
  on disk is referenced in SKILL.md and every name in SKILL.md resolves
  to a real file. It parses the table headers to derive the category,
  then expands short names to full paths.
- `.pre-commit-config.yaml` wires up the sync check plus ruff
  lint/format, trailing-whitespace, end-of-file-fixer, check-yaml,
  check-merge-conflict, and check-added-large-files.
- `README.md` gets one line linking to SKILL.md.
- `pixi.toml` appends the build script to the docs-build task.
```

Problems: the opening paragraph restates the title instead of saying why the change was needed. Bullets for trivial changes (README one-liner, pixi.toml one-liner, standard pre-commit config). Implementation details the diff shows (how the sync script parses headers).

**After (motivation first, prose instead of bullets):**

```
docs: add SKILL.md routing index and llms.txt

The docs had no machine-readable index, so an LLM agent had no way to
find the right page without scanning every file. This PR adds two entry
points for agents and the tooling to keep them in sync.

`SKILL.md` at the repo root routes agents that have the checkout on
disk. It maps user needs to page short names.

`scripts/build_llms.py` generates `builtdocs/llms.txt` during the docs
build by stripping SKILL.md's frontmatter and rewriting file paths to
site URLs. Not committed; produced after the site build.

`scripts/check_sync.py` is a pre-commit hook that checks every page on
disk is referenced in SKILL.md and vice versa.
```

The opening paragraph now states the problem (no index, agents scan every file) before the solution. Three short paragraphs instead of bullets; either format works when each point is one or two sentences. README, pixi.toml, and pre-commit config are obvious from the diff. The sync script paragraph says what it checks, not how it parses.
