---
name: deslop
description: Strip LLM slop from prose — rhetorical tics, false-profundity constructions, AI vocabulary, and boilerplate. Use when writing or reviewing any HoloViz prose (PR descriptions, docs, blog posts, READMEs, commit messages) to remove recognizable LLM patterns.
metadata:
  version: "2026.10.01"
  author: holoviz
---

# Deslop

Remove the recognisable machinery of LLM prose from a piece of writing without changing what it says.

Two failure modes to avoid, in order of severity:

1. **Changing the meaning.** The point is to delete the performance, not the content. If a slop pattern is wrapped around a real claim, keep the claim and drop the wrapper.
2. **Trading one tic for another.** A rewrite that swaps "here's the thing" for "the reality is" has done nothing. Prefer deletion over substitution.

## Before drafting

The rest of this skill cleans up a finished draft. When you're the one drafting a PR description, a docs page or a blog post, these keep most slop out of the first draft:

- Ask for a sample of the author's writing, or a piece they want to sound like, and match it. Models imitate an example far more reliably than they follow adjectives like "concise" or "natural".
- Name the reader before writing ("maintains a Panel app", "has never used HoloViews"). The reader decides what needs explaining.
- Describe the voice you want instead of listing tics to avoid. Naming a tic tends to make it show up.

The HoloViz voice, which the `pr-description`, `documentation` and `outreach` skills build on:

- Write in the first person, as the person who did the work, including what went wrong.
- Join cause and effect in one sentence with the connective that relates them (*since*, *so*, *but*) instead of a run of short beats, and vary the length. Joining can trade a `[choppy-run]` for a `[justification-tail]` once every sentence ends the same way, and a rescan catches that.
- Make each point once, and keep the concrete anchors (identifiers, numbers, a minimal example) while compressing.
- Use the word you'd say out loud to a colleague.

## Workflow

**1. Identify the target.** A file path, a range in a file, or a draft sitting in the conversation. If the user says "deslop this" with no target, use the most recent substantial prose in the conversation. If the target is ambiguous between two candidates, ask.

**2. Read it in full.** You cannot judge whether a sentence is load-bearing from a grep hit. Read the whole document before touching anything.

**3. Scan mechanically.**

```bash
python3 scripts/deslop_scan.py <file>
```

Flags: `--colon-triple` and `--em-dash` enable two patterns that are off by default because they are noisy in technical writing. `--json` for machine-readable output. A `.py` file is scanned for its comments and docstrings only, and `--comments` adds `.py` files to a directory walk (`deslop_scan.py --comments src/`), which is how you deslop the comments in a code change. Pass `-` to read stdin, which is how you scan a draft that only exists in the conversation:

```bash
python3 scripts/deslop_scan.py - <<'EOF'
<draft text>
EOF
```

The scanner is a starting point, not the specification. It has false positives (a legitimate "no X, no Y" in quoted dialogue) and it cannot see the patterns that need judgment (a paragraph that gestures at profundity without tripping any regex). Add `--explain` to print the `references/patterns.md` entries for the rules that fired, followed by the patterns no regex catches, so you read only the part of the catalogue that applies.

**4. Rewrite.** Apply `references/patterns.md` hit by hit, then reread the whole thing for the patterns the scanner missed. Use Edit for files. For a conversation draft, output the rewritten text.

**5. Verify, and repeat.** Re-run the scanner on the result and reread the whole piece again, because one pass is never enough: rewrites introduce their own tics (a merged sentence becomes a new "not X but Y", a cut announcement leaves two choppy beats behind), and the patterns no regex catches only show up on a fresh read. Cuts also break references, so reread the sentences around each deletion for a pronoun, "this" or "that" left pointing at something that's gone. Keep alternating scan and reread until a pass turns up nothing new. Every remaining hit needs a reason: quoted material, a false positive, or an intentional choice you flag to the user.

**6. Report.** Say what you cut and, briefly, what you deliberately left. Do not paste the scanner output at the user.

## Rewrite principles

**Delete first.** Most slop is additive. "It's important to note that the parser is single-threaded" becomes "The parser is single-threaded." "Turns out the cache was never invalidated" becomes "The cache was never invalidated." The sentence gets shorter and truer at once.

**Say the thing being gestured at.** Patterns like "that's the part a counter can't reach", "the punchline is", and "here's the twist" are promises of content. If the content is in the next clause, keep it and drop the announcement. If there is no content, the sentence was empty and goes entirely.

**Never invent to fill a gap.** When a vague gesture turns out to have nothing behind it, cut it or ask the user what they meant. Do not manufacture a specific claim to make the sentence work. Same for "experts argue" and friends: either the source is knowable and gets named, or the claim gets stated as the author's own, or it goes.

**Break the parallelism, don't rebalance it.** "Not just faster, but cheaper" wants to become "faster and cheaper", not "not only faster but also cheaper". Same for "no X, no Y" chains: pick the one item that matters, or make it a plain list.

**Let one sentence carry one idea.** Echoing runs, repeated openers, and stacked questions are all the same underlying problem: an idea stated three times with the nouns swapped. State it once, keep the best example, drop the rest.

**Keep the author's voice.** A writer who is genuinely wry, or who genuinely likes short punchy sentences, is not sloppy. You are removing the tics an LLM applies uniformly, not sanding the prose down to neutral. When the surrounding text has a clear register, match it.

**Leave alone:** code blocks, inline code, command output, quoted text, citations, other people's words, and anything inside a fenced block. If a pattern appears in a quote, it stays.

## Scope discipline

Deslopping is not general copyediting. Do not restructure sections, add or remove headings, reorder arguments, change technical claims, adjust tone beyond what removing a pattern requires, or fix things you merely dislike. If you notice a real problem outside scope (a wrong API name, a broken link), mention it separately rather than fixing it silently.

If a document is slop end to end and needs a rewrite rather than an edit pass, say so instead of producing a lightly de-tic'd version of a bad draft.
