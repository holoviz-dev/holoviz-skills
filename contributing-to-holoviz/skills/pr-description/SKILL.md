---
name: pr-description
description: Writing a clear pull request description for HoloViz packages. Use when drafting or reviewing the description, summary, or write-up of a PR in any HoloViz repository.
metadata:
  version: "0.1.2"
  author: holoviz
---

# PR Descriptions

Write HoloViz PR descriptions in the first person, as work you did, and keep the prose free of em dashes.

Follow the repo's PR template rather than inventing sections. Every HoloViz repo inherits it from the org-wide `holoviz/.github` repo, so fetch the current, authoritative sections from the raw template and fill each one in:

https://raw.githubusercontent.com/holoviz/.github/refs/heads/main/.github/pull_request_template.md

## Writing each part well

- **Title:** conventional-commit style (`fix:`, `feat:`, `docs:`, `chore:`) summarizing the change in one line.
- **Description:** 2-3 sentences in your own words on what changed and why, with the motivation and a minimal reproducible example. Write the example per the [`minimal-example` skill](../minimal-example/SKILL.md) so a reviewer can paste and run it unchanged. Flag any breaking change, API change, new dependency, or migration step prominently so a reviewer cannot miss it.
- **Before / After:** include for any observable or visual change (behavior, UI, plotting, rendered docs) with screenshots, GIFs, or video, labelled old versus new. Skip it when there is nothing to compare, such as docs or refactors.
- **AI disclosure:** if AI was used, name the tool and model (for example Claude Code + Opus) and how it was used, and never delete the section. Non-disclosure can result in a ban.

## Voice and style

Write dense, causal prose rather than a padded list. When a PR makes several distinct changes, prefer a short bullet list with one bullet per change, each a complete change-then-mechanism statement (not a fragment); a single-change PR can be one short paragraph instead. Either way keep it skimmable, and add a short "How to test" note or a minimal reproducible example.

- Lead with the change, then the mechanism, e.g. "This PR adds X, where ...". State what changed before how it works.
- One bullet per independent change. Pack the cause and effect into that bullet rather than splitting it across several, e.g. "Fixed the Viewer example, which created widgets before `super().__init__()`; values synced but notifications didn't, so callbacks never fired."
- Don't hard-wrap inside a bullet or paragraph: keep each bullet on a single line. A PR description is a GitHub comment field, where every single newline renders as a line break (unlike a committed `.md` file), so wrapping shows up as mid-sentence breaks.
- Chain cause and effect within a sentence ("captured once, meaning ...", "watches it, triggering ... so ...") instead of many short, disconnected ones.
- Explain the motivation once; don't justify every step or restate the diff. State what each part does and trust the reader and the diff for the rest.
- Keep concrete anchors (key identifiers, field names, a minimal example) even while compressing, so it stays specific.
- Stay neutral and declarative; drop selling adverbs like "cleanly", "simply", or "robustly".
- Reserve backticks for concrete symbols (`obs_id`, `None`, function and parameter names); let conceptual names read as plain prose.
