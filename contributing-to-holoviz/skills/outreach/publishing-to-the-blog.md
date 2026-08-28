# Publishing to the Blog

Getting a post onto [blog.holoviz.org](https://blog.holoviz.org). The site is
[Quarto](https://quarto.org/), sourced from
[`holoviz-dev/blog`](https://github.com/holoviz-dev/blog).

## Contents

- [Setup](#setup)
- [Start from the template](#start-from-the-template)
- [The header](#the-header)
- [How interactivity survives](#how-interactivity-survives)
- [Review and publish](#review-and-publish)
- [Gotchas](#gotchas)

## Setup

```bash
conda create -n holoviz-blog -c conda-forge r-quarto perl jupyter
conda activate holoviz-blog
```

`perl` is not optional — Quarto's toolchain wants it. `jupyter` is only needed
if you author in `.qmd`, since that is what executes the `{python}` chunks; add
it anyway, it costs nothing and its absence is confusing when you hit it.

Preview from the repo root, which builds the site and live-reloads on save:

```bash
quarto preview
```

## Start from the template

Copy `posts/template` and rename it. Do not hand-create a post directory; the
template carries the header format and the folder layout the site expects.

```
posts/your-post-name/
  index.ipynb     # or index.md — the post itself
  images/         # assets, linked as ./images/example.png
  repro/          # lock files and anything needed to rebuild the post later
```

`_quarto.yml` excludes `posts/template` from rendering (`"!posts/template"`), so
the template never appears on the site.

The `repro/` folder is a real convention, not decoration — existing posts ship a
`requirements.txt` there so the post can be reproduced years later against the
versions that produced it.

## The header

A YAML block in the **first cell** (markdown, or a raw cell):

```yaml
---
title: "Plotting made easy with hvPlot: 0.11 release"
date: "2024-09-27"
description: "Release announcement for hvPlot 0.11, including: DuckDB integration…"
author: "Maxime Liquet"
categories: [release, hvplot]
image: "images/thumbnail.png"
---
```

What each field actually drives:

| Field | Drives |
|---|---|
| `title`, `date` | listing entry and sort order |
| `description` | listing blurb, RSS, and the og/twitter card |
| `author` | byline; a YAML list for several authors |
| `categories` | the listing's category filter — reuse existing tags |
| `image` | listing thumbnail **and** the social card preview |

Set `image` even for a text-heavy post. Without it the post looks broken when
shared.

## How interactivity survives

**Interactive plots in a post come from committed notebook outputs, not from a
running server.** An `.ipynb` with executed HoloViews cells stores
`application/vnd.holoviews_exec.v0+json` and `holoviews_load` bundles alongside
the HTML, and Quarto passes them straight through.

This is why the repo insists notebooks are **committed in their evaluated
state**. An unevaluated notebook produces a post with no plots.

What that buys, and what it does not:

- **Works for a reader:** pan, zoom, hover, linked selection, anything Bokeh's
  JavaScript does on its own.
- **Does not work:** anything needing Python at read time. A Panel widget driving
  a callback is dead on the page — unless you pre-compute its states with
  `.embed()` or compile the link to JS with `.jslink()`. See
  [HoloViz in Quarto](holoviz-in-quarto.md#what-survives-into-the-page).

If the piece genuinely needs live Python, that is a `panel convert` artifact
embedded or linked from the post — and it is not offline. See the
[main skill](SKILL.md#present-from-one-thing-ship-another).

**Authoring in `.qmd` instead.** `_quarto.yml` renders `*.qmd` too, and a `.qmd`
with `{python}` chunks lets Quarto execute at render time rather than requiring
you to commit an evaluated notebook — so the diff stays readable and the plots
cannot go stale against the prose. Both routes produce the same interactivity;
`.ipynb` matches what every existing post does, and no post in the repo is a
`.qmd` yet (`index.qmd` is the listing page). If you take the `.qmd` route,
you are the first — build the dev site early.

The `{python}` chunk has its own rules, chiefly that a missing `.extension()`
call produces a blank plot with no error. See
[HoloViz in Quarto](holoviz-in-quarto.md).

## Review and publish

Open a PR. Every push to it rebuilds
[the dev site](https://holoviz-dev.github.io/blog-dev/) — check the post there
rather than trusting local preview. Merging to `main` publishes to the live site.

## Gotchas

- **Indented raw HTML is not rendered.** Quarto wraps it in a `<code>` element
  instead. Un-indent embedded HTML blocks, or fence them:

  ```
  :::{=html}
  <div>…</div>
  :::
  ```

- **Changing a post's path breaks inbound links.** Set `aliases` in the header to
  preserve old URLs. This is enforced — `_verify_redirects.py` runs in CI.
- **`fig-cap` on a HoloViews cell produces subfigures and often an empty plot.**
  Use a markdown caption instead; see
  [Distilling Explanatory Plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md#embedding-fig-cap-makes-subfigures).
- **Charts will not inherit the site's fonts.** Bokeh draws to canvas. Same
  reference, [Fonts](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md#fonts-bokeh-inherits-nothing).
- **Posts carrying a lot of custom HTML and JavaScript are the known rough edge**
  of this setup. Preview on the dev site before assuming it works.
