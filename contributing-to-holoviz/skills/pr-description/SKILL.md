---
name: pr-description
description: Writing a clear pull request description for HoloViz packages. Use when drafting or reviewing the description, summary, or write-up of a PR in any HoloViz repository.
metadata:
  version: "0.0.1"
  author: holoviz
---

# PR Descriptions

Write HoloViz PR descriptions in the first person, as work you did, and keep the prose free of em dashes.

Follow the repo's PR template rather than inventing sections. Every HoloViz repo inherits it from the org-wide `holoviz/.github` repo, so fetch the current, authoritative sections from the raw template and fill each one in:

https://raw.githubusercontent.com/holoviz/.github/refs/heads/main/.github/pull_request_template.md

## Writing each part well

- **Title:** conventional-commit style (`fix:`, `feat:`, `docs:`, `chore:`) summarizing the change in one line.
- **Description:** 2-3 sentences in your own words on what changed and why, with the motivation and a minimal reproducible example. Flag any breaking change, API change, new dependency, or migration step prominently so a reviewer cannot miss it.
- **Before / After:** include for any observable or visual change (behavior, UI, plotting, rendered docs) with screenshots, GIFs, or video, labelled old versus new. Skip it when there is nothing to compare, such as docs or refactors.
- **AI disclosure:** if AI was used, name the tool and model (for example Claude Code + Opus) and how it was used, and never delete the section. Non-disclosure can result in a ban.

## Guidelines

- Keep the description tight. The diff shows *how*; explain *why*.
- Don't restate the diff line by line.
- For a large PR, add a short bullet list of the key changes and a "How to test" note.
