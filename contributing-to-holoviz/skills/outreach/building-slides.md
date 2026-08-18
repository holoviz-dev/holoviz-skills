# Building Slides

Slide-based material for talks, workshops, and interactive concept explainers.
Both Quarto `revealjs` and Panel's `SlidesTemplate` use reveal.js for
navigation — the choice is about whether slides need live Python.

Worked pieces: `examples/context_explainer.py` (Panel),
`examples/context_explainer_deck.qmd` (Quarto).

## Contents

**Choosing a format:**

- [Quarto or SlidesTemplate](#quarto-or-slidestemplate)

**Quarto decks:**

- [A minimal Quarto deck](#a-minimal-quarto-deck)
- [Charts in Quarto slides](#charts-in-quarto-slides)

**Interactive explorables (SlidesTemplate):**

- [When an explorable is worth the cost](#when-an-explorable-is-worth-the-cost)
- [Structure](#structure)
- [Write for the reader, not for yourself](#write-for-the-reader-not-for-yourself)
- [Make the interaction load-bearing](#make-the-interaction-load-bearing)
- [Fix the axes](#fix-the-axes)
- [Numbers at two scales](#numbers-at-two-scales)
- [Hover and tap as teaching moves](#hover-and-tap-as-teaching-moves)
- [Auto-start on navigation](#auto-start-on-navigation)
- [Close with a receipt](#close-with-a-receipt)

**Shared:**

- [Slide writing](#slide-writing)
- [Rendering and previewing](#rendering-and-previewing)
- [Presenting and handing out](#presenting-and-handing-out)
- [Gotchas](#gotchas)


## Quarto or SlidesTemplate

**Default to Quarto.** Contributors already have it for the blog. Authoring is
markdown, interactive Bokeh plots embed via committed cell outputs (pan, zoom,
hover survive), and fragments, speaker notes, and PDF export are first-class.

Reach for Panel's `SlidesTemplate` in **one case**: the audience needs to watch
you drive a widget and see Python recompute, or the reader needs to interact
with a control to learn something. That is real, and Quarto cannot do it.

Slides are mostly prose and a picture. `SlidesTemplate` makes you build every
text slide as `pn.pane.Markdown(...)` in Python — accept that cost only when
the interaction justifies it.


## A minimal Quarto deck

```yaml
---
title: "What Param actually does"
author: "Your Name"
format:
  revealjs:
    theme: [default, brand.scss]
    logo: assets/symbol.svg
    slide-number: c/t
    embed-resources: true
    width: 1050
    height: 740
    center: false
    echo: false
---
```

`width`/`height` set the stage reveal.js scales to the viewport. The 960×700
default letterboxes Bokeh plots into a narrow column — widen it.

Theme with a SASS file using Quarto's layer syntax, `/*-- scss:defaults --*/`
then `/*-- scss:rules --*/`. Reveal uses `$presentation-*` variables, not
Bootstrap's:

```scss
/*-- scss:defaults --*/
$presentation-heading-font: Verdana, sans-serif;   // match your project's typeface
$presentation-font-size-root: 30px;
$body-color: #383838;

/*-- scss:rules --*/
.reveal h1, .reveal h2 { text-transform: none; }  // reveal uppercases by default
```


## Charts in Quarto slides

Charts follow
[Distilling Explanatory Plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md) — the font
hook, the `invert_axes` traps, and no `fig-cap` on a HoloViews cell. Two
deck-specific points:

- **Size the chart to the stage, not the screen.** A plot wider than the
  `width:` you set gets scaled down along with everything else, so its type ends
  up smaller than the slide's. Keep chart width under the stage width and let
  reveal do the scaling once.
- **Put the model in a module** and import it from both the deck and the post, so
  a changed constant updates both rather than drifting apart.


## When an explorable is worth the cost

Explorables are expensive. Reach for one only when the idea has a **hidden
mechanism with a dial on it** — something that changes as a parameter moves,
where the reader's intuition is probably wrong. Chunk size and read
amplification. Sampling rate and aliasing. Reactive dependency graphs.

If the idea is a sequence of facts, write prose. If it is a finding in real
data, write a [data story](../../../developing-with-holoviz/skills/panel/data-storytelling.md).
If the reader's intuition is already correct, you are decorating, not teaching.

```python
from panel.template import SlidesTemplate

SlidesTemplate(
    title="Reactivity, live",
    main=[intro_slide, ReactivityDemo()],
    reveal_config={"width": 1100, "height": 720, "hash": True, "center": True},
).servable()
```

Each object in `main` becomes one slide. `reveal_config` passes through to
reveal.js. Accept the costs before choosing it:

- It is a Vanilla template, so it will **not** theme with `panel-material-ui`.
  This is a deliberate exception to the repo's usual prefer-pmui guidance —
  rebuilding reveal.js navigation in pmui costs far more than the styling gains.
- `show_header` defaults to `False`; setting `title` alone shows nothing.
- You need a server, or a `panel convert` build that is **not offline**.


## Structure

Work in short parts, each with one idea. The reliable arc:

1. **The problem, made visceral.** Something concrete and painful *before* any
   terminology. The Zarr guide opens with a fake 8.3 TB download whose progress
   bar is exaggerated 400× and still does not visibly move.
2. **The idea**, introduced only once the reader wants it.
3. **The mechanics** — how it actually works, now that they care.
4. **Why it matters** — where it applies, what it costs, what it is not.
5. **Try it** — an open playground with the constraints removed.
6. **A receipt** — what the reader's own choices cost.

Never define a term before the reader has felt the pain it solves. That
ordering is the whole craft; everything else is presentation.


## Write for the reader, not for yourself

An explorable aimed at practitioners can say "tokens" and "context window". One
aimed at a broader audience cannot — the reader leaves before they learn the
mechanism. Translate the jargon into what it *does*:

| Technical term | Plain-language replacement |
|---|---|
| tokens | words |
| tokens processed / input context | the AI's workload |
| stateless request with full context replay | goes back and re-reads everything |
| quadratic growth / N² | the conversation grows faster than you'd expect |
| system prompt | setup instructions |
| cache hit / miss | (omit — fold the consequence into a one-liner if needed) |

The test: **read the sentence to someone who does not write code.** If they ask
what a word means, replace it. If they nod but look bored, you kept a term
that makes you feel precise and makes them feel excluded.

Formulas, monospaced math, and pricing-per-million-tokens tables are the same
failure mode in visual form. If the number matters, show it as a bar or a
label; if the derivation matters, let the slider derive it.


## Make the interaction load-bearing

The test: **remove the widget. Does the part still teach?** If yes, the
interaction was decoration — cut it or cut the part.

Bind one parameter to *several* views so the reader sees a single change
expressed more than one way. In `examples/context_explainer.py`, dragging
`messages` redraws the curve **and** rewrites the stat line, so the
acceleration is derived rather than asserted:

```python
class CostCurve(pn.viewable.Viewer):
    messages = param.Integer(default=20, bounds=(1, 60))

    @param.depends("messages")
    def _plot(self): ...      # the geometry

    @param.depends("messages")
    def _stats(self): ...     # the numbers, same parameter
```

Give the reader the smallest control that makes the point. A slider over one
variable beats a form with six — six inputs means nobody forms a hypothesis.


## Fix the axes

**The single most common mistake.** Autoscaled axes refit the frame on every
change, so a quantity that grows quadratically looks identically steep at 5
turns and at 60. The growth — the entire lesson — becomes invisible.

```python
# WRONG: the frame chases the data, so nothing appears to change
return curve.opts(width=520, height=330)

# CORRECT: a fixed frame the curve grows into
return curve.opts(
    width=520, height=330,
    xlim=(0, MAX_TURNS * 1.35),
    ylim=(0, total_read(MAX_TURNS) * 1.05),
)
```

Same reasoning for colour ranges (`clim`) and axis formatters: pin anything the
reader is meant to compare across states. Use
`NumeralTickFormatter(format="0.0a")` so large numbers read as `1.4m` rather
than `1.400e+6`.

Explanatory-chart practice applies throughout — `toolbar=None`, direct labels
instead of legends, one accent colour. See
[distilling-explanatory-plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md)
for the design, and [Distilling Explanatory Plots](../../../developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md)
for the mechanics that only show up once it is embedded.


## Numbers at two scales

Give every quantity a version the reader can hold and a version that is true.
The Zarr guide pairs a 192-chunk toy store with NASA's real 141,790 on the same
line, over and over. The toy makes it graspable; the real number makes it
matter. One without the other is either a cartoon or a wall.

Derive every number on every part from a few constants declared in one place,
so a reader who does not believe you can check.


## Hover and tap as teaching moves

HoloViews linked streams turn a chart into an input:

- `hv.streams.PointerXY` — "hover the map and the filename writes itself"
- `hv.streams.Tap` / `SingleTap` — "rest on a tile to lift it out"
- `hv.streams.Selection1D` — "pick these rows and watch the aggregate move"

Pair a stream with a `DynamicMap` so the explanation regenerates as the pointer
moves. Always label the affordance in prose — "hover the map" — because an
unmarked interaction is one most readers never find.


## Auto-start on navigation

When the reader lands on a new part, **fire the first action automatically** —
send the first message, start the first animation, advance the slider to its
opening position. Then let them click or drag to continue.

This matters because an unmarked blank widget looks broken, and a reader who has
to figure out that they should click before anything happens often does not.
Auto-starting one action demonstrates the affordance without a label.

Do not *block* navigation behind completing the interaction. The reader should
be able to hit Next at any point, even if they have not touched the widget.
Explorables teach by invitation, not by gate.


## Close with a receipt

End by telling the reader what *their* session cost or produced. It converts a
passive read into evidence about their own behaviour, and it is the part people
remember. Accumulate state as they interact, then spend the last part on it.


## Slide writing

These apply to both Quarto and SlidesTemplate slides:

- **One idea per slide.** If it needs two, it is two slides.
- **Headings up to about four words.** "The curve is quadratic", not "The curve
  is quadratic, not exponential" — the qualifier belongs in what you say.
- **Bold-lead bullets.** Each bullet starts with a **bold phrase** that carries
  the point on its own, followed by the detail. The audience scans the bold
  words and gets the story even if they miss everything else:
  *"**Slower responses** — the AI takes longer as the chat grows"* not
  *"As the chat grows, the AI takes longer to respond."*
- **A slide is not a document.** Bullets are prompts for the speaker, not the
  script. If a slide reads fine without you in the room, you wrote a handout.

In Quarto, reveal `. . .` splits a slide into fragments, so a point lands when
you say it rather than being readable four sentences ahead. Put the elaboration
in `::: {.notes}` — speaker notes are the right home for the caveat you want to
say aloud but not project.

```markdown
## The curve is quadratic

[653,000]{.big}

::: {.dek}
tokens read across a 40-turn thread
:::

. . .

Not exponential. Exponential would be 2^N.

::: {.notes}
Pause here — this is the load-bearing idea.
:::
```


## Rendering and previewing

**Quarto:** run `quarto render deck.qmd` to produce the HTML. Open the file
directly, or use `quarto preview deck.qmd` for live-reload while editing.
The rendered deck is a self-contained reveal.js document — it cannot be
served through Panel or iframed into a Panel app (the reveal.js runtime
conflicts with Panel's own scripts). However, `panel-live-server`'s
`evaluate` mode can still run the Python chart code from `.qmd` cells to
verify imports and inspect Bokeh models, and it can execute
`quarto render deck.qmd` via `subprocess` to produce the HTML.

**SlidesTemplate:** run `panel serve app.py`. If `panel-live-server` is
available (e.g. as an MCP tool), it can serve and screenshot the deck
directly — use it to iterate on layout and content before showing the user.

```bash
# Quarto
quarto render deck.qmd            # → deck.html
quarto preview deck.qmd           # live-reload dev server

# SlidesTemplate
panel serve app.py --show         # opens browser
panel serve app.py --port 5007    # specific port
```


## Presenting and handing out

These are usually two different artifacts:

- **Present from** whatever is richest — `panel serve` on your laptop, or the
  rendered deck locally. Never from a live network; conference wifi fails.
- **Hand out** the Quarto build with `embed-resources: true` (one file, offline,
  plots still interactive) and a PDF for people who want to skim on a phone.
  PDF: open the rendered HTML with `?print-pdf` appended and print from the
  browser.


## Gotchas

**Quarto:**

- **Reveal uppercases headings by default.** Override `text-transform` if the
  brand sets headings in sentence case.
- **`embed-resources: true` does not cover webfonts pulled from a CDN.** A theme
  that `@import`s Google Fonts still phones home. Self-host the woff2 for a
  genuinely offline deck.
- **Check the rendered deck, not the preview.** Speaker view, fragments, and PDF
  export each behave differently from the live-reload preview.

**SlidesTemplate / interactive explorables:**

- **`SlidesTemplate` content is not centred by default.** Panel columns inside
  reveal.js slides sit flush left unless you centre them yourself. Two things
  fix it: `reveal_config={"center": True}` vertically centres each slide, and
  `styles={"max-width": "700px", "margin": "0 auto"}` on each `pn.Column`
  horizontally constrains and centres the content. Without both, the deck
  looks like a dashboard, not a presentation.
- **`on_init=True` fires during `super().__init__()`.** A `@param.depends`
  watcher with `on_init=True` runs before `__init__` finishes. Any pane or
  widget that the watcher touches must be created *before* `super().__init__()`,
  not after. The Panel skill's "bare panes before super, `from_param` widgets
  after" rule applies to `from_param` widgets specifically — a plain
  `pn.widgets.Button` that the watcher sets `.name` or `.disabled` on must go
  before super too:

  ```python
  def __init__(self, **params):
      self._view = pn.pane.HTML("")          # watcher sets .object
      self._btn = pn.widgets.Button(...)     # watcher sets .name / .disabled
      super().__init__(**params)             # on_init fires _update here
      self._btn.on_click(self._advance)      # wiring is safe after super
      self._slider = pn.widgets.IntSlider.from_param(...)  # from_param after super
  ```

- **Recreating panes inside `@param.depends` flickers.** Standard Panel
  guidance, but it is worse here — a flicker on every slider tick reads as a
  bug and destroys the illusion of direct manipulation. Create panes once in
  `__init__`; see the Panel skill's Viewer Class Pattern.
- **Throttle expensive redraws only.** `pn.extension(throttled=True)` makes
  sliders fire on release rather than continuously. Use it when a redraw is
  slow — for a cheap redraw, continuous updates feel much more like direct
  manipulation, so do not apply it reflexively.
- **First load of a `panel convert` deck is slow** — Pyodide and the wheels
  download before anything appears. Put static content on the opening slide.

**Both:**

- **Direct labels tracking a moving point drift off-canvas.** When a series
  approaches an axis, anchor its label to the frame instead:
  `hv.Text(x, ylim_max * 0.045, " what you typed")`.
- **Mirrored columns look the same.** A "what you see" / "what's actually
  sent" side-by-side sounds clarifying but reads as two nearly identical
  panels. Replace with a visual that makes the *contrast* dramatic — e.g. a
  small exchange bar beside a large payload bar — so the point lands without
  reading.
- **Dense data tables overwhelm non-technical readers.** Token counts, cache
  rates, and pricing-per-million tables are information the author finds
  reassuring and the reader skips. If the number matters, make it one big
  label; if the breakdown matters, make it an interactive chart with a single
  control. If neither earns a widget, cut it.
