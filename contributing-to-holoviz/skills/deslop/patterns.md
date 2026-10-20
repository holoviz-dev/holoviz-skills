# Pattern catalogue

Each entry: what the pattern is, why it reads as machine-written, and how to fix it. The scanner ID in brackets matches `deslop_scan.py` output.

Two families. **Rhetorical tics** are constructions LLMs use to manufacture the feeling of insight: setup, pause, reveal, with nothing revealed. **Signs of AI writing** are the vocabulary and boilerplate tells catalogued by Wikipedia editors: less about false profundity, more about filler that survived from the training distribution.

---

## Rhetorical tics

### "No X, no Y" chains `[no-x-no-y]`

Two or more "no ..." items in a row. *No fluff, no filler, no jargon.*

Negative lists describe a product by what it isn't, which is unfalsifiable and usually padding. Keep the one absence that actually matters and state it positively, or cut the whole run.

> No config, no daemon, no state on disk. → Runs as a single process with no config file.

### "That's the whole ..." `[thats-the-whole]`

*That's the whole point. This is the whole game. That's the whole thing.*

A claim that the preceding sentence was more significant than it looked. It never adds information. Delete the sentence.

> The cache key is the file hash. That's the whole trick. → The cache key is the file hash.

### "Did not X, did not Y" chains `[did-not-chain]`

*It didn't crash, didn't warn, didn't log anything.*

Same machinery as "no X, no Y", conjugated. Collapse to the one meaningful negative, or state what it did instead.

> It didn't retry, didn't back off, didn't surface the error. → It dropped the error and returned an empty result.

### "Don't VERB it ... VERB it" `[dont-verb-it]`

*Don't call it a framework. Call it a toolkit.* The negated verb, then the same verb affirmed.

A definition performed as a correction of an objection nobody raised. Just give the definition.

> Don't think of it as a cache. Think of it as an index. → It's an index, not a cache.

### "Sit with that" `[sit-with-that]`

*Sit with that for a moment. Sit with the discomfort.*

Instructs the reader to feel something instead of giving them a reason to. Always deletable.

### "You already know" `[you-already-know]`

*You already know what to do. You already know the answer.*

Flattery that substitutes for the answer. If the reader knows, don't say it; if they don't, tell them.

### "Is the entire ..." `[is-the-entire]` and "The entire ... is" `[the-entire-x-is]`

*Latency is the entire business model. The entire point is that it fails loudly.*

Same inflation as "the whole point", with a bigger word. Strip the frame: *It fails loudly, on purpose.*

### "Is the whole ..." `[is-the-whole]`

*Reproducibility is the whole pitch. Here's the whole idea.* The general form of "That's the whole ...", with any subject.

State the pitch; do not announce that you are about to.

### "Is real ... and / not" `[is-real-and]`

*The performance cost is real, and it compounds. The risk is real, not theoretical.*

"X is real" concedes an objection in order to look even-handed, then continues unchanged. Assert the thing directly: *The performance cost compounds.*

("Real estate", "real time", "real numbers" and similar are excluded by the scanner.)

### "The punchline is" `[punchline]`

*The punchline is that it was a typo. The punchline? Nobody noticed.*

Framing a finding as a joke's payoff. Keep the finding, drop the frame.

### "Worth naming" `[worth-naming]`

*That loss is real and it's worth naming. Worth naming: the migration took four months.*

Therapist register. If it's worth naming, it's worth stating as a fact: *The migration took four months.*

### "That's not nothing" `[thats-not-nothing]`

*A 4% improvement. That's not nothing.*

Litotes standing in for an evaluation. Say what the number is worth, or let it stand alone.

### Echoing sentence runs `[echoing-run]`

Consecutive sentences on the same skeleton with the nouns swapped:

> A shopping cart is an object in the system. A chat room is an object in the system. A user session is an object in the system.

The anaphora reads as building, but each sentence carries one word of new information. Collapse to one sentence with a list, or keep the single best example.

> Carts, chat rooms, and sessions are all objects in the system.

### Performative honesty `[performative-honesty]`

*I won't pretend this is elegant. I'll be honest. Let's be honest. To be clear. Honestly, ... Look, ...*

Announcing sincerity rather than demonstrating it, and implying the surrounding text wasn't. Delete the announcement; the sentence after it is usually fine on its own.

> Honestly, the migration was a mess. → The migration was a mess.

Exception: "to be clear" doing real disambiguation work after a genuinely ambiguous statement can stay.

### "That's the part ..." `[thats-the-part]`

*That's the part a benchmark can't reach. My favourite part of the design is ...*

Points at a detail with an approving label instead of explaining why it matters. Explain why it matters, in the same number of words.

### "The only X I trust" `[only-x-i-trust]`

*The only marketing I trust is a changelog. The only thing that matters is p99.*

A narrowing superlative that sounds discriminating and is nearly always overstated. Drop "only" and the claim usually survives intact: *A changelog tells you more than the marketing does.*

### "Don't take my word for it" `[take-my-word]`

*You don't have to take my word for it. Don't take my word for any of this.*

If evidence follows, present the evidence. The invitation is a wasted sentence.

### "Turns out ..." `[turns-out]`

*Turns out the index was never used. It turns out that the fix was one line.*

Bolts a tidy conclusion onto a story that didn't earn it, and implies a discovery process the text didn't show. Cut the opener and keep the fact.

### "Fits in your head" `[fits-in-head]`

*Small enough to hold in your head. Batteries included. It just works. Zero config. Sane defaults.*

Dev-blog boilerplate that asserts simplicity instead of showing it. Replace with the concrete fact: *One 400-line module, no plugins.* If you have no such fact, cut it.

### Stacked rhetorical questions `[stacked-questions]`

Two or more questions in a row, the later ones usually fragments:

> Do I know how it works? Where it breaks? Which corners it cut?

Ask at most one, and only if you answer it. Otherwise rewrite as a statement: *I don't know how it works, where it breaks, or what it cut.*

### Repeated sentence openers `[repeated-openers]`

Three or more consecutive sentences starting on the same word.

> Maybe nobody needed it. Maybe it added a dependency. Maybe it was fine.

Same problem as echoing runs, at the level of the first word. Vary the openers or collapse the run. (The scanner ignores articles and pronouns, which repeat harmlessly, and does not count headings, table rows or list items — parallelism in a bulleted list is deliberate formatting. Check those by eye instead.)

### Colon into a triple `[colon-triple]` — off by default

A colon opening onto three or more comma-separated items: *separate ports, processes, and local state.*

The commonest shape LLM prose uses to sound concrete. Legitimate in technical writing, so enable with `--colon-triple` only when the corpus isn't documentation. When it is slop, the giveaway is that the three items are near-synonyms.

### "Here's the twist" `[heres-the-twist]`

*Here's the thing. Here's the twist. Here's the catch. Here's the kicker.*

Stage-managed reveal. Delete the phrase; the following sentence is the content.

### "X is dead" `[x-is-dead]`

*Peer review is dead. BOTD is dead; long live BOTD.*

Obituary headline, and its self-satisfied sequel. Say what changed: *Peer review no longer catches generated code.*

### "That's why X mattered" `[thats-why-mattered]`

*That's why being able to open the environment mattered. This is why keeping every transcript mattered.*

Retroactively assigns significance to an earlier point, in past tense, as if a lesson has landed. Either the earlier point made its own case or it didn't. Cut.

### Stranded auxiliary contrast `[stranded-auxiliary]`

A clause landing on a bare auxiliary for the reversal.

> The tool died; the data didn't. Reading mostly passed. Writing didn't. Maybe it wouldn't have.

One of these in a document is a stylistic choice. Three is a tic. Complete the verb on all but at most one: *The tool was retired; the data is still on disk.*

### Em-dash density `[em-dash]` — off by default

Not a construction, a frequency. LLM prose reaches for the em-dash for every parenthetical, aside, and dramatic pause. Enable with `--em-dash` to get a count and per-line hits; treat more than roughly one per 150 words as a signal. Convert most of them to commas, colons, parentheses, or a full stop.

### Choppy sentence runs `[choppy-run]`

Two or more short declarative sentences in a row within one paragraph, usually one idea chopped into beats. *Banning words half works. Models find substitutes.*

A single short sentence after a long one is emphasis. A run of them is a rhythm LLM prose applies everywhere to sound decisive, and readers hear it as machine-written. Join them into one sentence with the connective the beats were hiding (*since*, *so*, *but*, *and*):

> Delete first. Most slop is additive. → Delete first, since most slop is extra words.

The scanner counts sentences of six words or fewer. If the author's voice genuinely runs short, leave it, since the pattern is the run of them rather than any one short sentence.

### Tidy closer `[tidy-closer]`

A final sentence opening on *Ultimately*, *In the end*, *At the end of the day*, *In conclusion* or *All in all*.

It exists to make the paragraph feel finished, and it almost always restates the first sentence in bigger words. Cut it. If it carries a real conclusion, drop the opener and keep the claim.

> Ultimately, this change empowers developers to build faster dashboards. → (cut)

### Heading over a short section `[short-section]`

A heading over fewer than about 40 words, reported once two or more turn up. Usually paired with a bold one-line takeaway under each heading, so a two-sentence point gets a title, a summary and a body.

Headings are for navigating a long piece, and a reader doesn't need one to find two sentences. Fold short sections into one section as paragraphs, starting each with a plain sentence that names the point. (A heading followed directly by a subheading is a parent and isn't counted.)

### "At the end of the day" `[end-of-day]`

*At the end of the day ... when all is said and done ...*

A clause opener that promises a bottom line and usually restates the one already given. Cut it and keep the claim. `[tidy-closer]` catches it as a closing sentence; this catches it anywhere.

### "In conclusion" `[in-conclusion]`

*In conclusion ... In summary ... To sum up ... All in all ... In closing ...*

Essay scaffolding at the start of a sentence. A document that ends when its content ends doesn't need to announce it. Cut the opener, and if the sentence after it only restates earlier ones, cut that too.

### "Let's dive in" `[dive-in]`

*Let's dive in ... a deep dive into ... let's take a look ... let's unpack ... buckle up ... read on ... stay tuned.*

Announces content instead of giving it. Delete it and start with the first real sentence.

### "When it comes to" `[when-it-comes-to]`

*When it comes to performance, the new parser ...*

A wind-up before the subject. Start with the subject: *The new parser is faster.*

### "Whether you're X or Y" `[whether-youre]`

*Whether you're a beginner or an expert ... no matter your use case ...*

Addresses every possible reader and so none of them. Name the reader the document is for, or cut the clause.

### "In the world of" `[world-of]`

*In the world of data science ... welcome to the world of ...*

Places the subject in a "world" the reader is already in. Cut it and start with the subject.

### "The key takeaway" `[takeaway]`

*The key takeaway is ... the bottom line is ... what this means for you ...*

Labels a point as important instead of making it. Delete the label and state the point. If the point repeats an earlier sentence, cut it.

### "Think of it as" `[think-of-it-as]`

*Think of it as a ... imagine a ... picture this ...*

An analogy in place of a description. Keep it only when the comparison explains something the plain description can't; otherwise describe the thing.

### "The beauty of X is" `[beauty-of]`

*The beauty of this approach is ... the real power here is ... the magic of X is ...*

Praises a feature before saying what it does. Say what it does: *The cache survives restarts.*

### Filler sentence opener `[filler-opener]`

*Simply put ... In essence ... At its core ... Fundamentally ... Needless to say ... It goes without saying ... Make no mistake ...*

Promises a distilled version of the point, then states it at the same length. Delete the opener.

### Essay connective `[furthermore]`

*Moreover, ... Furthermore, ... Additionally, ... Notably, ... Consequently, ... Firstly, ...*

School-essay transitions, reported from two. Most can go. Where the relation matters, use the plain word (*also*, *so*, *but*) inside the sentence.

### "X rather than Y" frame `[antithesis]`

*... rather than ... instead of ... as opposed to ... , not a ...*

Defining a thing by what it isn't. One is a contrast; reported at four or more and 3.5 per 1,000 words, where every claim gets a foil. Keep the contrast when the reader would expect the other option, and otherwise state the positive half alone.

### Trailing justification clause `[justification-tail]`

*..., since ... , so ... , because ... , which means ... , which is why ...*

A reason tacked onto the end of a finished sentence. One is how people explain things. It's reported at five or more and 6 per 1,000 words, where every sentence ends in its own justification and the prose falls into one rhythm. Vary it: give a reason its own sentence, lead with it, or cut it when the reader doesn't need it. Joining a `[choppy-run]` with *since* or *so* often creates this one, so rescan after that fix.

### Counted-list announcement `[count-preview]`

*Three things matter here. ... Two reasons stand out. ...*

Announcing how many items follow, reported from three. The reader can count the list. Cut the count and start with the first item.

### "X is what makes Y" `[cleft-emphasis]`

*Caching is what makes this fast. ... That's how you ... This is where the value comes from ... is the reason that ...*

A cleft sentence that delays the point for emphasis, reported from two. Say it directly: *Caching makes this fast.*

### "The X story" `[business-story]`

*The deployment story ... our testing story is weak ...*

Business jargon for "how X works" or "the state of X". Name the thing: *Deploying takes three manual steps.* User stories, story points and "the story of" aren't counted.

### Inflated figure of speech `[figurative-inflation]`

*stops being hypothetical ... survives contact with ... does the heavy lifting ... where the rubber meets the road ... moves the needle ...*

Stock metaphors that make a plain event sound dramatic. Say the event: *The parser handles most of the work.*

### Unsourced quantifier `[vague-quantifier]`

*almost everyone ... the vast majority ... most users who ... far faster ... orders of magnitude ... nine times out of ten ...*

Sizes a claim without measuring it, reported from two. Give the number and where it came from, or drop the size.

### Chat-assistant register `[assistant-register]`

*I hope this helps ... Great question ... You're absolutely right ... Feel free to reach out ... Don't hesitate to ... Certainly!*

Chat replies pasted into a document. Always delete.

### Repeated sentence frame `[repeated-frame]`

Three or more sentences in a row that share a content word near the front and the same connective. *The cache stores results so that ... The cache expires entries so that ... The cache logs misses so that ...*

The parallelism `[echoing-run]` misses when the clauses differ in length. Merge the run into one sentence, or break the frame in all but one.

### Run of sentence fragments `[fragment-run]`

Two or more sentences in a row, each five words or longer, with no finite verb. *A faster parser. Fewer allocations on every render.*

Usually a list padded out as prose. Give the fragments a verb and join them, or make them a real list.

### Bold-label bullet run `[bold-lead-bullets]`

Three or more unordered bullets in a row that each open with a bold label. *- **Speed:** ... - **Cost:** ... - **Scale:** ...*

The labels make a list look organized while repeating what each bullet says. Drop them and let the bullet's first words do the work, or turn the run into a paragraph. Numbered lists of bold step names aren't counted.

### Bold-label paragraph `[bold-lead-paragraph]`

Paragraphs that open with a bold sentence ending in a period, reported from three. ***What it delivers.** The tool ...*

A slot label written to look organized. Use a heading if the piece is long enough to need one; otherwise drop the label. A bold term with no period, as in a definition list, isn't counted.

### Emoji in a heading or bullet `[emoji-decoration]`

*## 🚀 Getting started ... - ✅ Fast*

Decoration that adds no information. Delete it. Arrows and symbols used as notation (↔) aren't counted.

---

## Signs of AI writing

### AI vocabulary `[ai-vocab]` and `[ai-vocab-soft]`

Words LLMs use far more than people do: *delve, tapestry, meticulous, meticulously, pivotal, intricate, interplay, underscore(s), garner, bolster, vibrant, bustling, multifaceted, seamless(ly), ever-evolving, testament, realm, navigate (figurative), leverage (verb), robust, crucial, myriad, plethora, foster, harness, unlock, elevate, landscape (figurative), showcase, embark, profound, paramount, nuanced, holistic.*

A single hit is coincidence — "crucial" is a real word. Several in one document is the tell. The scanner splits the list: words with few ordinary uses (*delve, tapestry, testament, myriad*) report on one hit as `[ai-vocab]`, and words that also have plain uses (*crucial, robust, leverage, pivotal, comprehensive*) report from two as `[ai-vocab-soft]`. Replace with the plain word: *delve into* → *examine*; *underscores* → *shows*; *leverage* → *use*; *robust* → say what it survives.

### Marketing hype `[hype]`

*revolutionize, supercharge, unleash, empower, streamline, game-changer, cutting-edge, state-of-the-art, best-in-class, effortless, blazing-fast, world-class, battle-tested, future-proof.*

Product-page adjectives that claim a result without showing it. Replace each with the measurement or the mechanism: what it's fast at and by how much, or what it does that the old way didn't.

### "Not just X, but Y" `[not-just-but]`

*Not just faster, but cheaper. Not only correct but also readable. It's not a rewrite — it's a rethink.*

Negative parallelism, the single most reliable LLM signature. Nearly always improves as a plain conjunction: *faster and cheaper*. The em-dash contrast variant usually wants the second half only.

### "It's important to note" `[important-to-note]`

*It is important to note that ... It's worth noting ... It should be noted ... Worth pausing on ... It's worth asking ...*

Didactic hedging that adds a clause and no information. Delete and start at the actual statement.

### "Stands as a testament" `[testament]`

*Stands as a testament to ... serves as a reminder that ... is a testament to ...*

Inflates significance instead of reporting what happened. Report what happened.

### "Plays a crucial role" `[crucial-role]`

*Plays a crucial / pivotal / vital / key / significant role in ...*

Says something is involved without saying how. Name the mechanism: *The scheduler decides which shard the write lands on.*

### "Ever-evolving landscape" `[evolving-landscape]`

*The ever-evolving landscape of ... in today's fast-paced world ... the rapidly changing landscape ...*

Scene-setting boilerplate that could open any document on any topic. Delete the opener and start with the subject.

### "Experts argue" `[experts-argue]`

*Experts argue ... some critics have noted ... observers suggest ... industry reports indicate ... studies show ...*

Vague attribution to authorities who are never named, borrowing credibility without a citation. Name the source, or state the claim in your own voice and take responsibility for it, or cut it.

### "Despite these challenges" `[despite-challenges]`

*Despite these challenges ... faces several challenges ... challenges remain ... it remains to be seen ... only time will tell.*

The essay-outline formula: topic, benefits, challenges, hedged outlook. Cut the transition and the non-conclusion. If the outcome is genuinely unknown, say what would decide it.

### Participle sentence tails `[participle-tail]`

*..., highlighting the importance of ... , underscoring the need for ... , showcasing its versatility ... , reflecting a broader shift ...*

Superficial analysis bolted onto a sentence that had already finished. Almost always a clean cut at the comma. If the analysis is real, promote it to its own sentence with a subject.

### Promotional boilerplate `[promotional]`

*Nestled in ... in the heart of ... rich tapestry / heritage ... hidden gem ... boasts a ... breathtaking ... stunning views ... must-visit.*

Travel-brochure register. Replace with the fact underneath, or cut. *Boasts* in particular is almost always *has*.

### Chatbot leftovers `[chatbot-leftover]`

*As an AI language model ... as of my last update ... knowledge cutoff ...*, plus markup debris: `oaicite`, `contentReference`, `turn0search`, `utm_source=` tracking parameters on pasted links.

Not stylistic, just unedited paste. Always delete outright. Strip tracking parameters from URLs rather than removing the link.

---

## Patterns no regex catches

Reread for these after working through the scanner hits.

**The empty reveal paragraph.** Three sentences of setup, a short dramatic line, and no new information in any of them. Whole paragraph goes.

**Symmetry that isn't in the subject.** Two contrasted options given equal weight and equal length when one of them is obviously worse, because the shape wanted balance.

**Concrete-sounding numbers with no source.** "Roughly 40% of the time" appearing in a document that never measured anything.

**Conclusions that restate the introduction.** The final paragraph paraphrasing the first with different vocabulary.

**Sections that restate themselves.** The same thing at section scale: a section's last sentence repeats its heading or its opening line. *If a sentence promises content, delete the promise and keep the content. … If the announcement has nothing behind it, the whole sentence goes.* Check the last sentence of every section against its first, and cut it unless it adds a case the first didn't cover.

**Uniform sentence length.** Every sentence between 12 and 20 words. Human prose varies more, including sentences of three words and of fifty.

**Confidence that outruns the evidence.** Hedges deleted where they belonged, certainty added where the author had none.

**Triplets outside a colon.** Three benefits, three adjectives, three verbs, listed because three sounds complete: *reduce redundant computation, improve responsiveness, and lower server costs.* `[colon-triple]` only catches the ones after a colon. Keep the items you could back up with a number and drop the rest.

**Formal words nobody says.** Not the classic AI vocabulary, but stiff choices that read the same way: *discounting* (doubting), *register* (style), *additive* (extra), *prime* (make more likely), *constructions* (sentence patterns), *supplies* (makes up). If you wouldn't say it out loud to a colleague, use the word you would.
