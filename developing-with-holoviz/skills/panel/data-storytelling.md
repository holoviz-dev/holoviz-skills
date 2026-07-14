# Data Storytelling

Assemble explanatory charts into a scrollable, editorial article — a masthead, a
narrow reading column, prose interleaved with charts, each captioned by its
takeaway. The individual charts follow the hvplot
[Distilling Explanatory Plots](../hvplot/distilling-explanatory-plots.md) reference; this is the Panel
shell that turns them into a narrative. See `examples/graphic_story.py` for a
complete piece.

## Contents

- [Reading column](#reading-column)
- [Prose-then-chart rhythm](#prose-then-chart-rhythm)
- [One visual family](#one-visual-family)
- [Assume no interaction](#assume-no-interaction)
- [Gotchas](#gotchas)

## Reading column

Clamp the body to a readable width instead of letting it stretch across the
viewport: wrap the article in `pmui.Container(width_option="md")` inside a
`pmui.Page`. Put the section/masthead name in `Page.title` and the story's own
headline in the body as `pmui.Typography(variant="h3")`, with the dek as a
`subtitle1` in `text.secondary`. An editorial serif (`theme_config`
`typography.fontFamily`) sells the article feel.

## Prose-then-chart rhythm

Build a single `pmui.Column` that alternates a short paragraph and the chart it
sets up, so the reader always meets the point before the picture. Charts go in
`pn.pane.HoloViews` (there is no pmui equivalent) and auto-theme under the Page.

## One visual family

Route every chart through one shared `style()` helper and one small palette, so
the piece reads as a set rather than a pile of unrelated plots. Consistency is
what makes a stack of charts feel authored.

## Assume no interaction

A story is read, not operated: keep the explanatory rule that the static view
carries the message (`toolbar=None`, direct labels, annotations in place). Don't
add widgets or a sidebar — a `Page` with no controls is the right shape here.

## Gotchas

- Body prose goes in `pn.pane.Markdown` (renders inline `**bold**`/`` `code` ``),
  not `pmui.Typography` (plain text) — use Typography for the headline and dek.
- `Page.main` needs a list: `main=[container]`, not `main=container`.
- Don't give the `Page` a sidebar for an article; use only `main`.
- The masthead AppBar defaults to blue; set `palette.primary.main` (e.g. a dark
  ink) so it reads as a masthead rather than an app header.
