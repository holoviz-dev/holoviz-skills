# Data Storytelling

Assemble explanatory charts into a scrollable, editorial article — masthead, narrow reading
column, prose interleaved with charts, each captioned by its takeaway. The charts themselves
follow [Distilling Explanatory Plots](../hvplot/distilling-explanatory-plots.md); this is the
Panel shell around them. Complete piece: `examples/graphic_story.py`.

## Contents

- [Reading column](#reading-column)
- [Prose-then-chart rhythm](#prose-then-chart-rhythm)
- [One visual family](#one-visual-family)
- [Assume no interaction](#assume-no-interaction)
- [Gotchas](#gotchas)

## Reading column

Clamp the body to a readable width instead of letting it stretch: wrap the article in
`pmui.Container(width_option="md")` inside a `pmui.Page`. Section/masthead name goes in
`Page.title`, the story's headline in the body as `pmui.Typography(variant="h3")`, the dek as a
`subtitle1` in `text.secondary`. An editorial serif (`theme_config` `typography.fontFamily`)
sells the article feel.

## Prose-then-chart rhythm

Build one `pmui.Column` alternating a short paragraph and the chart it sets up, so the reader
meets the point before the picture. Charts go in `pn.pane.HoloViews` (no pmui equivalent) and
auto-theme under the Page.

## One visual family

Route every chart through one shared `style()` helper and one small palette — consistency is
what makes a stack of charts feel authored rather than piled up.

## Assume no interaction

A story is read, not operated: keep the explanatory rule that the static view carries the
message (`toolbar=None`, direct labels, annotations in place). No widgets, no sidebar.

## Gotchas

- Body prose goes in `pn.pane.Markdown` (renders inline `**bold**`/`` `code` ``), not
  `pmui.Typography` (plain text) — use Typography for the headline and dek.
- `Page.main` needs a list: `main=[container]`, not `main=container`. No sidebar for an article.
- The masthead AppBar defaults to blue; set `palette.primary.main` (e.g. a dark ink) so it reads
  as a masthead rather than an app header.
