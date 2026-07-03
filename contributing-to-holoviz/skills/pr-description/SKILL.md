---
name: pr-description
description: Writing a clear pull request description for HoloViz packages. Use when drafting or reviewing the description, summary, or write-up of a PR in any HoloViz repository.
metadata:
  version: "0.0.1"
  author: holoviz
---

# PR Descriptions

This skill covers what a good HoloViz pull request description contains. Write it in the first person, as work you did, and keep the prose free of em dashes.

## Structure

A good PR description has these parts, in order:

1. **Title:** conventional-commit style (`fix:`, `feat:`, `docs:`, `chore:`) summarizing the change in one line.
2. **Overview:** 2-3 sentences in your own words covering what changed and why. Link the issue it resolves (`Closes #1234`).
3. **Before / After:** include it only when the change produces an observable difference a reviewer should see, such as changed behavior, a bug fix with a visible symptom, an API change, or anything visual (UI, plotting, rendered docs). Skip it when there is nothing to compare, such as docs, refactors, config, or adding agent-facing files. When you include it, label the old versus new; visual changes need before/after screenshots, GIFs, or video.
4. **Major changes:** if there is a breaking change, API change, new dependency, or migration step, call it out under its own bold heading so a reviewer cannot miss it. Omit this section when there is none.
5. **AI disclosure:** if the work used AI assistance, always include a disclosure and never remove it. State what you planned and understood versus what AI helped scaffold.

## Guidelines

- Keep the overview short. The diff shows *how*; the description explains *why*.
- For a large PR, add a short bullet list of the key changes and a "How to test" note.
- Don't restate the diff line by line.

## Example

```markdown
<!-- WRONG: no why, no before/after, restates the diff -->
## Summary
Changed the `filter_by_range` function in transforms.py. Updated the
if statement and added a return. Also edited a test.

<!-- CORRECT: overview, before/after (observable behavior change), major change flagged -->
## Overview
`filter_by_range` dropped rows containing NaN, silently shrinking the
result. This makes NaN handling explicit so filtered output matches the
input length. Closes #1234.

## Before / After
Before: `filter_by_range(df, 'x', 0, 2)` returned 2 of 3 rows (NaN dropped).
After: returns all 3 rows; NaN is retained.
[before.png] [after.png]

## Breaking change
Callers relying on NaN being dropped must now filter explicitly.

## AI disclosure
I identified the bug and designed the fix; AI helped scaffold the
parametrized test cases.
```
