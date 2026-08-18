---
name: outreach
description: >-
  Prepare community and teaching material about HoloViz — conference talks,
  slide decks, presentations, tutorials, workshops, live demos, blog posts for
  blog.holoviz.org, and interactive explainers of how a HoloViz concept works.
  Use when the deliverable teaches an audience rather than shipping a feature.
metadata:
  version: "0.4.0"
  author: holoviz
---

# Outreach

Community and teaching material *about* HoloViz — talks, slide decks,
workshops, tutorials, demos, blog posts, and concept explanations. This is a
contributor activity, not an app-building one: the audience is learning
something, not operating a tool.

The distinction that decides everything downstream:

- **Data storytelling** — the data is the subject. Charts carry findings.
  "Here is what our numbers show." Covered by
  [data-storytelling](../../../developing-with-holoviz/skills/panel/data-storytelling.md).
- **Concept explanation** — an *idea* is the subject. The data is a prop, often
  synthetic. The interaction carries the argument. "Here is how a `DynamicMap`
  decides what to re-render." That is this skill.

## Contents

- [References](#references)
- [Pick the format](#pick-the-format)
- [Show the mechanism](#show-the-mechanism)
- [Present from one thing, ship another](#present-from-one-thing-ship-another)
- [Gotchas](#gotchas)

## References

- [Publishing to the Blog](publishing-to-the-blog.md) — Quarto setup, the
  `posts/template` folder, the header fields, how interactivity actually
  survives into a post, the PR preview flow.
- [Building Slides](building-slides.md) — Quarto `revealjs` decks and Panel
  `SlidesTemplate` interactive explorables. Covers the decision between them,
  slide writing, explorable structure, and worked pieces for both formats.
For chart styling mechanics (fonts on the Bokeh canvas, `invert_axes` traps,
embedding failures), see
[Distilling Explanatory Plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md)
in the hvPlot skill.

## Pick the format

| The audience will… | Build | Why |
|---|---|---|
| watch you talk, once | Quarto `revealjs` deck | markdown authoring, reveal.js navigation, PDF export |
| follow along, typing | notebook | they need to run and modify cells |
| read it alone, later | explorable explanation | nobody is there to narrate, so the interaction must |
| read findings from real data | editorial article | see `data-storytelling`; assumes no interaction |

A conference talk usually needs two: a deck to present from, and something
linkable at the end for people who want to actually understand it.

**Default to Quarto** for both posts and decks. Contributors already have it for
the blog, authoring is markdown, and interactive Bokeh plots embed the same way
in both. Reach for Panel only when you need **live Python** in front of the
audience — see [Building Slides](building-slides.md).

## Show the mechanism

**Show the mechanism; do not describe it.** The reason to build teaching
material with these tools rather than write prose is that a reader can change an
input and watch the output move. If a slide would survive being replaced by a
sentence, replace it by a sentence and save the effort.

This matters most when demoing HoloViz itself. "`DynamicMap` re-renders on zoom"
is a claim. A `DynamicMap` beside a static `Image`, both wired to a counter that
ticks on every render, is a demonstration — and nobody has to take your word.

## Present from one thing, ship another

The artifact you present from and the artifact people take away are usually
**different files**, and conflating them is the most common planning mistake.

| Path | Artifact | Opens offline | Interactivity that survives |
|---|---|---|---|
| Quarto + `embed-resources: true` | one `.html` | yes | pan, zoom, hover, linked selection |
| Quarto to PDF (`?print-pdf`) | one `.pdf` | yes | none — static images |
| `.save(embed=True, resources=INLINE)` | one `.html` | yes | precomputed widget states only |
| `panel convert --to pyodide-worker` | `.html` + CDN | **no** | full Python |
| `panel serve` | nothing | no | full Python |

Two things people get wrong here:

- **`panel convert` output is not offline.** It hard-codes CDN URLs for the
  Pyodide runtime and the Panel/Bokeh wheels, and there is no inline flag. It
  needs a network every time it opens. Say so when you hand it out; do not
  describe it as "a single file you can email."
- **`.save(embed=True)` defaults to `max_opts=3`** — three values per widget.
  You can raise it (`max_opts=60`), but each combination of widget states is
  pre-computed and stored, so file size grows fast with multiple controls.
  Workable for a single slider; combinatorial for two or more.

So: present from `panel serve` or a local deck, and publish the Quarto version
as the takeaway.

## Gotchas

- **Webfonts you name are not webfonts you have.** Naming a family selects it;
  it does not deliver it. CSS fallback is silent and looks deliberate. This bites
  hardest on charts, because Bokeh draws text to a canvas outside the CSS
  cascade — see [Distilling Explanatory Plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md).
- **Google Fonts is a network dependency.** A brand theme that `@import`s from
  `fonts.googleapis.com` makes even an `embed-resources` file phone home. Self-host
  the woff2 if the artifact is meant to be handed out.
- **Verify the artifact you ship, not the one you built.** `panel serve`,
  `panel convert`, and `quarto render` are three different runtimes. Open the
  actual output before you send it anywhere.
- **Do not demo from a live network.** Conference wifi fails. Cache the data
  next to the notebook, or generate it — a concept demo's numbers should usually
  be synthetic anyway, since the concept is the subject.
