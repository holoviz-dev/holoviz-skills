# Writing a Blog Post

What to write and how to write it, for posts on blog.holoviz.org or a company
blog. Mechanics like Quarto, the post template and headers aren't covered here;
follow the blog repo's own template. Read the [deslop skill](../deslop/SKILL.md)
before drafting: its Before drafting section has the voice this builds on, and
its patterns cover headers over short sections, a bold label on every item, and
endings that restate the post.

## Decide the reader and the point

Write down who reads it and what they should do afterward before writing
anything else. "HoloViz contributors writing PR descriptions" and "enterprise
teams choosing an agent policy" need different examples, different links, and
sometimes a different title, and a draft aimed at both reads as aimed at
neither.

The title and the one-line description are what show up in the blog index and
social previews, so make them say what the reader gets rather than what the
post is about.

If the post is one of a series, say so in the first lines and link the other
parts, and make each part stand on its own for a reader who skipped the rest.

## Structure

- Numbered lists are fine for real sequences or a set of parallel items.
- Bold a key phrase **mid-sentence**, roughly one per paragraph, so a skimmer
  still gets the point. Never bold whole sentences or openers.
- Skip a "What's in this post" list when the headers already say it.
- A closing line can point somewhere, such as a repo or an invitation to reply.

## Voice

Report back from doing the work, in the HoloViz voice from deslop's Before
drafting section, and match the author's existing posts if there are any: ask
for one and treat it as the voice reference. Asides in parentheses and the
occasional emoji are fine if the author uses them.

## Code

Snippets should run as pasted, so include the imports, keep them minimal, and
state the versions they were run against near the first one. The
[minimal-example skill](../minimal-example/SKILL.md) covers what that looks
like.

## Figures

Each figure makes one point and is referenced in the text next to it. Good
candidates are a marked-up before/after, a small diagram of a loop or pipeline,
or a chart of real results. Keep colors consistent across figures (one color
means one thing everywhere), use the brand palette and fonts where there is
one, and give every figure a caption that says what to look at and alt text that
describes it for someone who can't see it. The blog renders in light and dark
themes, so check each figure in both, especially transparent PNGs and SVGs
with dark text.

Keep figure sources (HTML/SVG or plotting scripts) and any build script in the
post folder, and put the scripts or data behind any results the post claims in
a `repro/` folder beside them, so another session or contributor can edit a
figure or rerun a result instead of starting over.

## People and sources

- Don't name colleagues or quote internal chat (Slack, Discord, internal
  issues) in a public post without their permission. Generalize to the point
  ("one view is…", "a team found…").
- Link public sources directly and paraphrase them; don't reproduce long
  passages.
- If AI helped draft the post, it's fine, and often more convincing, to say so.

## Review loop

1. Work through the [deslop](../deslop/SKILL.md) workflow, alternating scan and
   reread until a pass finds nothing new.
2. Have a person read it.
3. Before publishing, check that links resolve, that version numbers and
   "currently" claims are still true, and that anyone named has agreed to it.
