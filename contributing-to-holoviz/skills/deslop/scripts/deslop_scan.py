#!/usr/bin/env python3
"""Scan prose for LLM slop patterns.

Usage:
    deslop_scan.py FILE [FILE ...]     scan files (directories are walked)
    deslop_scan.py -                   scan stdin

Options:
    --colon-triple   enable the colon-into-a-triple check (noisy in docs)
    --em-dash        enable em-dash density reporting
    --all            enable every optional check
    --only IDS       scan with only these rules (comma separated)
    --skip IDS       scan with every rule except these
    --all-hits       report hits below a rule's noise threshold too
    --list-rules     print the rule table and exit
    --summary        add a corpus-wide total when scanning several files
    --quiet          omit files with no hits
    --json           emit JSON instead of a text report
    --context N      characters of match text to show (default 90)

Fenced code blocks, indented code blocks, inline code, blockquotes, RST
directives and section underlines are skipped.

Some rules only fire above a count, because one instance is a style choice and
several are a tic. `--all-hits` shows those, and the report footer counts them.

Exit status: 0 clean, 1 hits found, 2 no file could be read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

I = re.IGNORECASE  # noqa: E741

TEXT_SUFFIXES = {".md", ".markdown", ".rst", ".txt"}


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    pattern: str
    exclude: str | None = None
    optional: bool = False
    min_count: int = 1
    min_per_1k: float = 0.0
    density_only: bool = False
    count_pattern: str | None = None

    @property
    def note(self) -> str:
        bits = []
        if self.optional:
            bits.append("off by default")
        if self.min_count > 1:
            bits.append(f"needs {self.min_count}+")
        if self.min_per_1k:
            bits.append(f"and {self.min_per_1k}+ per 1000 words")
        if self.density_only:
            bits.append("density only")
        return ", ".join(bits)


# ---------------------------------------------------------------- regex rules

RULES: list[Rule] = [
    # -- rhetorical tics -----------------------------------------------------
    Rule(
        "no-x-no-y",
        '"No X, no Y" chain',
        r"\bno\s+[\w'’-]+(?:\s+[\w'’-]+){0,2}\s*[,;]\s*(?:and\s+|or\s+)?"
        r"no\s+[\w'’-]+(?:\s+[\w'’-]+){0,2}"
        r"(?:\s*[,;]\s*(?:and\s+|or\s+)?no\s+[\w'’-]+(?:\s+[\w'’-]+){0,2})*",
        count_pattern=r"\bno\s+",
    ),
    Rule(
        "thats-the-whole",
        '"That\'s the whole ..."',
        r"\b(?:that|this)(?:'s|’s| is)\s+the\s+whole\s+[\w-]+",
        # "the whole file" names a thing; "the whole point" inflates one
        exclude=r"whole\s+(?:file|directory|folder|list|output|archive|dataset|"
        r"repo(?:sitory)?|document|module|package|page|suite|log|table|history)",
    ),
    Rule(
        "did-not-chain",
        '"Did not X, did not Y" chain',
        r"\b(?:did\s+not|didn['’]t)\s+[\w'’-]+(?:\s+[\w'’-]+){0,2}\s*[,;]\s*(?:and\s+|or\s+)?"
        r"(?:did\s+not|didn['’]t)\s+[\w'’-]+(?:\s+[\w'’-]+){0,2}"
        r"(?:\s*[,;]\s*(?:and\s+|or\s+)?(?:did\s+not|didn['’]t)\s+[\w'’-]+(?:\s+[\w'’-]+){0,2})*",
        count_pattern=r"\b(?:did\s+not|didn['’]t)\b",
    ),
    Rule(
        "dont-verb-it",
        '"Don\'t VERB it ... VERB it"',
        r"\b(?:do\s+not|don['’]t)\s+(\w+)(?:\s+(?:of|about|at|as|to))?\s+(?:it|this|that)\b"
        r"[^.!?]{0,60}[.!?;:—-]\s*"
        r"(?:\w+[\s,]+){0,3}\1(?:\s+(?:of|about|at|as|to))?\s+(?:it|this|that)\b",
    ),
    Rule(
        "sit-with-that",
        '"Sit with that"',
        r"\bsit\s+with\s+(?:that|this|it|the\s+\w+)",
    ),
    Rule(
        "you-already-know",
        '"You already know"',
        r"\byou\s+already\s+know\b",
    ),
    Rule(
        "is-the-entire",
        '"is the entire ..."',
        r"\b(?:is|are|was|were)\s+the\s+entire\s+(?:point|game|thing|idea|pitch|trick|"
        r"premise|story|argument|appeal|value\s+proposition|business\s+model)\b",
    ),
    Rule(
        "the-entire-x-is",
        '"The entire ... is"',
        r"\bthe\s+entire\s+(?:point|game|thing|idea|pitch|trick|premise|business\s+model)\s+(?:is|was)\b",
    ),
    Rule(
        "is-the-whole",
        '"is the whole ..."',
        r"\b(?:is|are|was|were)\s+the\s+whole\s+(?:point|trick|pitch|idea|thing|game|premise|story)\b"
        r"|\bhere(?:'s|’s| is)\s+the\s+whole\s+[\w-]+",
    ),
    Rule(
        "is-real-and",
        '"is real, and / not"',
        r"\b(?:is|are|was|were)\s+real\s*[,;]?\s+(?:and|not|but)\b"
        r"|\bis\s+the\s+real\s+[\w-]+\s+and\s+it\b",
        exclude=r"real\s+(?:estate|time|numbers?|world|name|money|terms|analysis|user)",
    ),
    Rule(
        "punchline",
        '"The punchline is"',
        r"\bthe\s+punchline\s*(?:is\b|was\b|[:?])",
    ),
    Rule(
        "worth-naming",
        '"Worth naming"',
        r"\b(?:is|it['’]s|its)\s+worth\s+(?:naming|stating|pausing\s+on)\b"
        r"|^\s*worth\s+naming\s*:",
        exclude=r"naming\s+names",
    ),
    Rule(
        "thats-not-nothing",
        '"That\'s not nothing"',
        r"\b(?:that|this|it|which)(?:'s|’s| is)\s+not\s+nothing\b",
    ),
    Rule(
        "performative-honesty",
        "Performative honesty",
        r"\bI\s+(?:won['’]t|will\s+not)\s+pretend\b"
        r"|\bI['’]?ll\s+be\s+honest\b|\bI\s+will\s+be\s+honest\b"
        r"|\blet['’]?s\s+be\s+honest\b|\bif\s+I['’]?m\s+being\s+honest\b"
        r"|\bto\s+be\s+(?:clear|honest|fair)\b|\bin\s+all\s+honesty\b"
        r"|(?:^|(?<=[.!?]\s)|(?<=\n))(?:Honestly|Look|Truthfully|Frankly)\s*[,:]",
    ),
    Rule(
        "thats-the-part",
        '"That\'s the part ..."',
        r"\b(?:that|this)(?:'s|’s| is)\s+the\s+part\b"
        r"|\bmy\s+favou?rite\s+part\s+(?:of|is|about)\b"
        r"|\bthe\s+part\s+that\s+(?:makes\s+me|I\s+(?:like|trust|keep))\b",
    ),
    Rule(
        "only-x-i-trust",
        '"The only X I trust"',
        r"\bthe\s+only\s+[\w\s'’-]{0,25}?(?:I\s+trust|that\s+(?:matters|counts)|it\s+needs|"
        r"worth\s+\w+|you\s+need)\b",
    ),
    Rule(
        "take-my-word",
        '"Don\'t take my word for it"',
        r"\btake\s+my\s+word\s+for\b",
    ),
    Rule(
        "turns-out",
        '"Turns out ..."',
        r"(?:^|(?<=[.!?]\s)|(?<=\n)|(?<=—)|(?<=–))\s*Turns\s+out\b"
        r"|\bit\s+turn(?:s|ed)\s+out\s+that\b",
    ),
    Rule(
        "fits-in-head",
        '"Fits in your head" / dev-blog boilerplate',
        r"\b(?:hold|fit|fits|holds)\s+(?:it\s+)?in\s+your\s+head\b"
        r"|\bsmall\s+enough\s+to\s+(?:hold|fit)\b"
        r"|\bbatteries[\s-]included\b|\bit\s+just\s+works\b|\bzero[\s-]config\b"
        r"|\bsane\s+defaults\b|\bjust\s+works,?\s+out\s+of\s+the\s+box\b",
    ),
    Rule(
        "heres-the-twist",
        '"Here\'s the twist"',
        r"\bhere(?:'s|’s| is)\s+the\s+(?:twist|thing|catch|kicker|rub|trick|punchline|"
        r"first|best\s+part|problem)\b",
    ),
    Rule(
        "x-is-dead",
        '"X is dead"',
        r"\b[\w-]+\s+(?:is|are)\s+dead\b(?!\s*(?:code|letter|end|link))" r"|\blong\s+live\s+[\w-]+",
        # a dead process, socket or kernel is a fact about software, not a headline
        exclude=r"\b(?:process(?:es)?|thread|socket|connection|session|kernel|server|worker|"
        r"client|channel|node|pixel|battery|link|branch|task|job)\s+(?:is|are)\s+dead",
    ),
    Rule(
        "thats-why-mattered",
        '"That\'s why X mattered"',
        r"\b(?:that|this)(?:'s|’s| is)\s+why\s+[^.!?]{3,70}\bmatter(?:ed|s)\b",
    ),
    Rule(
        "stranded-auxiliary",
        "Stranded auxiliary contrast",
        r"\b(?:didn['’]t|doesn['’]t|don['’]t|wasn['’]t|weren['’]t|isn['’]t|aren['’]t|hasn['’]t|"
        r"haven['’]t|hadn['’]t|wouldn['’]t|won['’]t|couldn['’]t|can['’]t|shouldn['’]t)\s*[.;]"
        r"|\b(?:did|does|was|were|is|are|has|have|had|would|will|could|can|should)\s+not\s*[.;]",
        min_count=3,
    ),
    Rule(
        "end-of-day",
        '"At the end of the day"',
        # the figurative use opens a clause; "runs at the end of the day" is a time
        r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*At\s+the\s+end\s+of\s+the\s+day\b"
        r"|\bat\s+the\s+end\s+of\s+the\s+day\s*,"
        r"|\bwhen\s+all\s+is\s+said\s+and\s+done\b",
    ),
    Rule(
        "in-conclusion",
        '"In conclusion"',
        r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*(?:In\s+conclusion|In\s+summary|To\s+summari[sz]e|"
        r"To\s+sum\s+up|All\s+in\s+all|In\s+closing)\b",
    ),
    Rule(
        "dive-in",
        '"Let\'s dive in"',
        r"\b(?:dive[sd]?|diving)\s+(?:deep\s+)?into\b|\bdeep[\s-]dive\b"
        r"|\blet['’]s\s+(?:dive|get\s+started|take\s+a\s+look|explore|jump\s+in|unpack)\b"
        r"|\bbuckle\s+up\b|\bread\s+on\b|\bstay\s+tuned\b",
    ),
    Rule(
        "when-it-comes-to",
        '"When it comes to"',
        r"\bwhen\s+it\s+comes\s+to\b",
    ),
    Rule(
        "whether-youre",
        '"Whether you\'re X or Y"',
        r"\bwhether\s+you(?:['’]re|\s+are)\b"
        r"|\bno\s+matter\s+(?:your|what\s+your|where\s+you|how\s+you)\b",
    ),
    Rule(
        "world-of",
        '"In the world of"',
        r"\bin\s+the\s+(?:world|realm)\s+of\b|\bwelcome\s+to\s+the\s+world\s+of\b",
    ),
    Rule(
        "takeaway",
        '"The key takeaway"',
        r"\bkey\s+takeaways?\b|\bthe\s+takeaway\s+(?:here\s+)?is\b"
        r"|\bthe\s+bottom\s+line\s+is\b|\bwhat\s+this\s+means\s+for\s+you\b",
    ),
    Rule(
        "think-of-it-as",
        '"Think of it as"',
        r"\bthink\s+of\s+(?:it|this|them|these)\s+as\b"
        r"|\bimagine\s+(?:a|an|you|for\s+a\s+moment)\b|\bpicture\s+this\b",
    ),
    Rule(
        "beauty-of",
        '"The beauty of X is"',
        r"\bthe\s+(?:beauty|magic|elegance|real\s+power|true\s+power)\s+(?:of\s+[^.!?]{1,40}\s+is|here\s+is)\b",
    ),
    Rule(
        "filler-opener",
        "Filler sentence opener",
        r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*(?:Simply\s+put|In\s+essence|At\s+its\s+core|"
        r"Fundamentally|Needless\s+to\s+say|It\s+goes\s+without\s+saying|Make\s+no\s+mistake)\b",
    ),
    Rule(
        "furthermore",
        "Essay connective",
        r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*(?:Moreover|Furthermore|Additionally|Notably|"
        r"Consequently|Nevertheless|Firstly|Secondly)\s*,",
        min_count=2,
    ),
    Rule(
        "antithesis",
        '"X rather than Y" frame',
        r"\brather\s+than\b|\binstead\s+of\b|\bas\s+opposed\s+to\b"
        r"|,\s*not\s+(?:a|an|the|by|as|to|because)\b",
        min_count=4,
        min_per_1k=3.5,
    ),
    Rule(
        "justification-tail",
        "Trailing justification clause",
        r",\s*(?:because|since|so\s+that|so\s+|which\s+means|which\s+is\s+why|"
        r"at\s+which\s+point)\b",
        min_count=5,
        min_per_1k=6.0,
    ),
    Rule(
        "count-preview",
        "Counted-list announcement",
        r"(?:^|(?<=\n)|(?<=[.!?]\s))\s*\*{0,2}(?:One|Two|Three|Four|Five|Six)\s+"
        r"(?:\w+\s+){0,2}(?:things?|ways?|cases?|limits?|mechanisms?|audiences?|"
        r"boundaries|reasons?|problems?|options?|caveats?|concerns?|questions?|steps?|"
        r"levels?|kinds?|shapes?|postures?|failures?|decisions?|choices?|areas?|places?|"
        r"parts?|pieces?|points?|lessons?|takeaways?|principles?|rules?|patterns?|"
        r"tradeoffs?|goals?|phases?|groups?|categories?|properties?)\b",
        min_count=3,
    ),
    Rule(
        "cleft-emphasis",
        '"X is what makes Y"',
        r"\bis\s+what\s+(?:makes|lets|allows|gives|keeps|does|matters|counts|separates)\b"
        r"|\bis\s+how\s+(?:someone|you|we|it|that|this|anyone)\b"
        r"|\bis\s+where\s+[^.!?]{0,40}?(?:comes?\s+from|lives?|happens?|begins?)\b"
        r"|\bis\s+the\s+(?:reason|thing)\s+that\b",
        min_count=2,
    ),
    Rule(
        "business-story",
        '"The X story"',
        r"\bthe\s+(?:\w+[\s-]){1,4}story\b",
        exclude=r"story\s+of|user\s+story|short\s+story|whole\s+story|story\s+points?",
    ),
    Rule(
        "figurative-inflation",
        "Inflated figure of speech",
        r"\bstops?\s+being\s+(?:hypothetical|theoretical|optional|a\s+problem)\b"
        r"|\bsurviv(?:e|ed|es|ing)\s+contact\s+with\b|\bdoes\s+the\s+heavy\s+lifting\b"
        r"|\bwhere\s+the\s+rubber\s+meets\b|\bunder\s+the\s+pressure\s+of\b"
        r"|\bthe\s+sharp\s+end\b|\bmoves?\s+the\s+needle\b",
    ),
    Rule(
        "vague-quantifier",
        "Unsourced quantifier",
        r"\balmost\s+(?:everyone|all|every|any)\b|\bthe\s+vast\s+majority\b"
        r"|\bmost\s+(?:people|users|teams|customers)\s+who\b|\ba\s+fraction\s+of\s+the\b"
        r"|\bfar\s+(?:cheaper|faster|better|more|less|easier|harder)\b"
        r"|\borders?\s+of\s+magnitude\b|\bnine\s+times\s+out\s+of\s+ten\b",
        min_count=2,
    ),
    Rule(
        "assistant-register",
        "Chat-assistant register",
        r"\bI\s+hope\s+this\s+helps\b|\bgreat\s+question\b|\byou(?:['’]re|\s+are)\s+absolutely\s+right\b"
        r"|\bhappy\s+to\s+help\b|\bfeel\s+free\s+to\s+(?:reach\s+out|ask|let\s+me\s+know)\b"
        r"|\bdon['’]t\s+hesitate\s+to\b|\blet\s+me\s+know\s+if\s+you\s+(?:have\s+any|need|would)\b"
        r"|(?:^|(?<=\n))\s*(?:Certainly|Absolutely|Of\s+course)\s*[!,]",
    ),
    # -- signs of AI writing -------------------------------------------------
    Rule(
        "ai-vocab",
        "AI vocabulary word",
        r"\b(?:delve[sd]?|delving|tapestry|interplay|garner(?:ed|ing|s)?|bolster(?:ed|ing|s)?|"
        r"vibrant|bustling|multifaceted|ever-evolving|testament|myriad|plethora|paramount|"
        r"intricate(?:ly)?|transformative|unwavering|indelible|beacon|cornerstone)\b",
    ),
    Rule(
        "ai-vocab-soft",
        "AI vocabulary word (ambiguous)",
        r"\b(?:meticulous(?:ly)?|pivotal|underscor(?:e|es|ed|ing)|seamless(?:ly)?|realm|"
        r"foster(?:ing|s|ed)?|harness(?:ing|es|ed)?|nuanced|holistic|profound(?:ly)?|"
        r"elevat(?:e|es|ed|ing)|unlock(?:s|ed|ing)?|showcas(?:e|es|ed|ing)|embark(?:ed|ing|s)?|"
        r"leverag(?:e|es|ed|ing)|crucial(?:ly)?|robust(?:ness)?|comprehensive(?:ly)?)\b",
        min_count=2,
    ),
    Rule(
        "not-just-but",
        '"Not just X, but Y"',
        r"\bnot\s+(?:just|only|merely|simply)\s+[^,;.!?]{1,50}[,;]?\s*but\s+(?:also\s+)?"
        r"|\bit(?:'s|’s| is)\s+not\s+[^—–.!?]{1,45}[—–]\s*it(?:'s|’s| is)\b"
        r"|\bit(?:'s|’s| is)\s+not\s+(?:about\s+)?[^.!?]{1,45}\.\s*It(?:'s|’s| is)\s+(?:about\s+)?",
    ),
    Rule(
        "important-to-note",
        '"It\'s important to note"',
        r"\bit\s+(?:is|was)\s+important\s+to\s+note\b|\bit(?:'s|’s)\s+important\s+to\s+note\b"
        r"|\b(?:it(?:'s|’s)\s+|it\s+is\s+)?worth\s+(?:noting|mentioning|pausing|considering|"
        r"asking|remembering)\b|\bshould\s+be\s+noted\b|\bimportantly,",
    ),
    Rule(
        "testament",
        '"Stands as a testament"',
        r"\b(?:stands|serves|stand|serve)\s+as\s+a\s+(?:testament|reminder|symbol|"
        r"powerful\s+\w+)\b|\bis\s+a\s+testament\s+to\b",
    ),
    Rule(
        "crucial-role",
        '"Plays a crucial role"',
        r"\bplay(?:s|ed|ing)?\s+an?\s+(?:crucial|pivotal|vital|key|significant|important|"
        r"central|essential|major)\s+role\b",
    ),
    Rule(
        "evolving-landscape",
        '"Ever-evolving landscape"',
        r"\bever[\s-](?:evolving|changing|shifting|expanding|growing)\b"
        r"|\b(?:evolving|changing|shifting|digital|modern|current|competitive)\s+landscape\b"
        r"|\bin\s+today(?:'s|’s)\s+(?:fast[\s-]paced|digital|modern|competitive)\b"
        r"|\bin\s+an\s+era\s+(?:of|where)\b",
    ),
    Rule(
        "experts-argue",
        '"Experts argue"',
        r"\b(?:experts|critics|observers|analysts|commentators|researchers|scholars)\s+"
        r"(?:argue|say|agree|note|noted|believe|suggest|point\s+out|contend|warn)\b"
        r"|\bsome\s+(?:critics|experts|observers)\s+have\s+\w+\b"
        r"|\bindustry\s+reports\s+indicate\b|\b(?:studies|reports|surveys)\s+(?:show|suggest|indicate)\b"
        r"|\bit\s+is\s+(?:widely|generally)\s+(?:believed|accepted|agreed)\b",
    ),
    Rule(
        "despite-challenges",
        '"Despite these challenges"',
        r"\bdespite\s+(?:these|its|the)\s+challenges\b|\bfac(?:es|ed|ing)\s+(?:several|a\s+number\s+of|"
        r"numerous|significant)\s+challenges\b|\bchallenges\s+remain\b|\bremains\s+to\s+be\s+seen\b"
        r"|\b(?:only\s+)?time\s+will\s+tell\b|\bnot\s+without\s+its\s+challenges\b",
    ),
    Rule(
        "participle-tail",
        "Participle sentence tail",
        r",\s*(?:highlighting|underscoring|showcasing|reflecting|emphasi[sz]ing|demonstrating|"
        r"illustrating|signal(?:l)?ing|ensuring|cementing|solidifying|marking|paving|"
        r"contributing\s+to|allowing\s+for|making\s+it\s+(?:a|an|one))\b",
    ),
    Rule(
        "hype",
        "Marketing hype word",
        r"\b(?:revolutioni[sz](?:e|es|ed|ing)|supercharg(?:e|es|ed|ing)|unleash(?:es|ed|ing)?|"
        r"empower(?:s|ed|ing)?|streamlin(?:e|es|ed|ing)|game[\s-]chang(?:er|ing)|"
        r"cutting[\s-]edge|state[\s-]of[\s-]the[\s-]art|best[\s-]in[\s-]class|next[\s-]level|"
        r"effortless(?:ly)?|blazing(?:ly)?[\s-]fast|lightning[\s-]fast|world[\s-]class|"
        r"industry[\s-]leading|battle[\s-]tested|future[\s-]proof(?:ed|ing)?)\b",
    ),
    Rule(
        "promotional",
        "Promotional boilerplate",
        r"\bnestled\s+(?:in|among|between)\b|\bin\s+the\s+heart\s+of\b"
        r"|\brich\s+(?:tapestry|heritage|history|culture)\b|\bhidden\s+gem\b"
        r"|\bboast(?:s|ed|ing)?\s+(?:a|an|its|some|impressive|over)\b|\bbreathtaking\b"
        r"|\bstunning\s+(?:views?|scenery|architecture)\b|\bmust[\s-]visit\b"
        r"|\ba\s+(?:true|real)\s+(?:testament|delight|treat)\b|\bvibrant\s+(?:culture|community|city)\b",
    ),
    Rule(
        "chatbot-leftover",
        "Chatbot leftover",
        r"\bas\s+an\s+AI\s+(?:language\s+)?model\b|\bas\s+of\s+my\s+last\s+(?:update|training)\b"
        r"|\bknowledge\s+cut[\s-]?off\b|\bI\s+(?:cannot|can't)\s+browse\s+the\s+internet\b"
        r"|oaicite|contentReference|turn\d+(?:search|view|news)\d*|utm_source=|:contentReference",
    ),
    # -- optional ------------------------------------------------------------
    Rule(
        "colon-triple",
        "Colon opening onto a triple",
        r":\s+[^,:;.!?\n]{2,40},\s+[^,:;.!?\n]{2,40},\s+(?:and\s+|or\s+)?[^,:;.!?\n]{2,40}",
        optional=True,
    ),
    Rule(
        "em-dash",
        "Em-dash",
        r"[—–]|(?<=\w)\s--\s(?=\w)",
        optional=True,
        density_only=True,
    ),
]

# rules found by looking at markdown structure rather than by regex over prose
STRUCTURAL_RULES: list[Rule] = [
    Rule("bold-lead-bullets", "Bold-label bullet run", "", min_count=1),
    Rule("bold-lead-paragraph", "Bold-label paragraph slot", "", min_count=3),
    Rule("emoji-decoration", "Emoji in heading or bullet", ""),
]

SENTENCE_RULES: list[Rule] = [
    Rule("stacked-questions", "Stacked rhetorical questions", ""),
    Rule("repeated-openers", "Repeated sentence openers", ""),
    Rule("echoing-run", "Echoing sentence run", ""),
    Rule("repeated-frame", "Repeated sentence frame", ""),
    Rule("fragment-run", "Run of sentence fragments", ""),
]

ALL_RULES: list[Rule] = RULES + STRUCTURAL_RULES + SENTENCE_RULES
BY_ID: dict[str, Rule] = {r.id: r for r in ALL_RULES}
DESCRIPTIONS = {r.id: r.description for r in ALL_RULES}

COMPILED = {r.id: re.compile(r.pattern, I) for r in RULES}
COMPILED_EXCL = {r.id: re.compile(r.exclude, I) for r in RULES if r.exclude}
COMPILED_COUNT = {r.id: re.compile(r.count_pattern, I) for r in RULES if r.count_pattern}

# ------------------------------------------------------------- masking prose

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
LINK_TARGET_RE = re.compile(r"\]\([^)\s]+\)")
URL_RE = re.compile(r"\bhttps?://\S+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>\n]*>")
RST_DIRECTIVE_RE = re.compile(r"^(\s*)\.\.(?:\s|$)")
RST_UNDERLINE_RE = re.compile(r"^\s*([=~^\"'`*+#_:.-])\1{2,}\s*$")
LIST_ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s")


def _blank(line: str) -> str:
    return " " * len(line)


def mask_non_prose(text: str, keep_urls: bool = False) -> str:
    """Blank out code and quotes, preserving offsets so positions stay valid.

    Indented blocks are only code when they do not hang off a list item, so
    that wrapped list continuations stay in the prose the rules see.
    """
    text = HTML_COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    out: list[str] = []
    fence: str | None = None
    directive_indent: int | None = None
    prev_blank = True
    in_code_block = False
    in_list = False
    for line in text.split("\n"):
        stripped = line.strip()
        blank = not stripped
        indent = len(line) - len(line.lstrip())

        if fence is not None:
            out.append(_blank(line))
            if stripped.startswith(fence):
                fence = None
            prev_blank = False
            continue

        if blank:
            out.append(line)
            prev_blank = True
            continue

        m = FENCE_RE.match(line)
        if m:
            fence = m.group(2)[0] * 3
            out.append(_blank(line))
            prev_blank = False
            in_code_block = False
            continue

        if directive_indent is not None:
            if indent > directive_indent:
                out.append(_blank(line))
                prev_blank = False
                continue
            directive_indent = None

        if RST_DIRECTIVE_RE.match(line):
            directive_indent = indent
            out.append(_blank(line))
            prev_blank = False
            in_code_block = False
            continue

        if RST_UNDERLINE_RE.match(line) or stripped.startswith(">"):
            out.append(_blank(line))
            prev_blank = False
            in_code_block = False
            continue

        body = line.lstrip()
        is_list = bool(LIST_ITEM_RE.match(body))
        code_indent = 8 if in_list else 4
        if indent >= code_indent and (in_code_block or prev_blank) and not is_list:
            out.append(_blank(line))
            in_code_block = True
            prev_blank = False
            continue

        if indent < code_indent:
            in_code_block = False
        if is_list:
            in_list = True
        elif indent == 0:
            in_list = False
        out.append(line)
        prev_blank = False

    masked = "\n".join(out)
    masked = HTML_TAG_RE.sub(lambda m: _blank(m.group(0)), masked)
    masked = INLINE_CODE_RE.sub(lambda m: _blank(m.group(0)), masked)
    masked = LINK_TARGET_RE.sub(lambda m: _blank(m.group(0)), masked)
    if not keep_urls:
        masked = URL_RE.sub(lambda m: _blank(m.group(0)), masked)
    return masked


# ------------------------------------------------------- sentence-level rules

SENTENCE_END_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+|\n{2,}")
ABBREV = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "cf",
    "al",
    "mr",
    "mrs",
    "ms",
    "dr",
    "st",
    "fig",
    "no",
    "approx",
    "ca",
    "ibid",
}
# digits belong to the token: L1 and L4 are different openers, not two "L"s
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’-]*")

FUNCTION_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "am",
    "in",
    "on",
    "at",
    "of",
    "to",
    "for",
    "with",
    "from",
    "by",
    "into",
    "onto",
    "and",
    "or",
    "but",
    "not",
    "no",
    "as",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "there",
    "here",
    "you",
    "your",
    "we",
    "our",
    "they",
    "their",
    "i",
    "he",
    "she",
    "them",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "can",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "must",
    "if",
    "when",
    "than",
    "then",
    "so",
    "just",
    "only",
    "all",
    "every",
    "each",
    "some",
    "more",
    "most",
    "one",
    "two",
    "three",
    "up",
    "out",
    "over",
    "about",
}

OPENER_STOPLIST = {
    "the",
    "a",
    "an",
    "it",
    "this",
    "that",
    "these",
    "those",
    "i",
    "we",
    "you",
    "they",
    "he",
    "she",
    "there",
    "and",
    "but",
    "so",
    "if",
    "in",
    "to",
    "for",
    "of",
    "on",
    "at",
    "as",
    "its",
    "his",
    "her",
    "their",
    "our",
    "my",
    "your",
}


@dataclass
class Sentence:
    text: str
    start: int


STRUCTURAL_RE = re.compile(r"^(?:#{1,6}\s|\||[-*+]\s|\d+[.)]\s|!\[|\[!|:\w+:|\.\.\s)")


def is_structural(text: str) -> bool:
    """Headings, table rows and list items. Parallelism there is deliberate
    formatting, not an echoing run, so they break runs instead of joining them."""
    return bool(STRUCTURAL_RE.match(text.strip()))


def _tail_word(text: str) -> str:
    words = WORD_RE.findall(text)
    return words[-1].lower() if words else ""


def split_sentences(masked: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    pos = 0
    for part in SENTENCE_END_RE.split(masked):
        if part is None:
            continue
        idx = masked.find(part, pos) if part else pos
        if idx < 0:
            idx = pos
        stripped = part.strip()
        if stripped:
            offset = idx + (len(part) - len(part.lstrip()))
            sentences.append(Sentence(stripped, offset))
        pos = idx + len(part)
    # rejoin fragments that were split on an abbreviation
    merged: list[Sentence] = []
    for s in sentences:
        if merged and WORD_RE.search(s.text) and _tail_word(merged[-1].text) in ABBREV:
            merged[-1] = Sentence(merged[-1].text + " " + s.text, merged[-1].start)
            continue
        merged.append(s)
    return merged


def skeleton(sentence: str) -> tuple[str, ...] | None:
    words = [w.lower() for w in WORD_RE.findall(sentence)]
    if len(words) < 5:
        return None
    skel = tuple(w if w in FUNCTION_WORDS else "*" for w in words)
    if sum(1 for t in skel if t != "*") < 3:
        return None
    return skel


def first_significant_word(sentence: str) -> str | None:
    words = WORD_RE.findall(sentence)
    return words[0].lower() if words else None


def scan_sentences(masked: str) -> list[dict]:
    hits: list[dict] = []
    sentences = split_sentences(masked)

    # stacked rhetorical questions
    run: list[Sentence] = []
    for s in sentences + [Sentence("", len(masked))]:
        if s.text.endswith("?"):
            run.append(s)
            continue
        if len(run) >= 2:
            hits.append(_run_hit("stacked-questions", run))
        run = []

    # repeated sentence openers
    run = []
    current: str | None = None
    for s in sentences + [Sentence("", len(masked))]:
        word = None if is_structural(s.text) else first_significant_word(s.text)
        if word is not None and word == current:
            run.append(s)
            continue
        if len(run) >= 3 and current not in OPENER_STOPLIST:
            hits.append(_run_hit("repeated-openers", run))
        current = word
        run = [s] if word else []

    # echoing sentence runs
    run = []
    current_skel: tuple[str, ...] | None = None
    for s in sentences + [Sentence("", len(masked))]:
        skel = None if is_structural(s.text) else skeleton(s.text)
        if skel is not None and skel == current_skel:
            run.append(s)
            continue
        if len(run) >= 2:
            hits.append(_run_hit("echoing-run", run))
        current_skel = skel
        run = [s] if skel else []

    # repeated sentence frames: consecutive sentences sharing both a content word
    # near the front and the same connective. Catches the parallelism an exact
    # skeleton match cannot, where the clauses hanging off the frame differ in
    # length. Both signals are needed: sharing only the noun is just staying on
    # topic, and sharing only the connective is just a habit.
    run = []
    shared: set[str] = set()
    shared_conn: set[str] = set()
    for s in sentences + [Sentence("", len(masked))]:
        head = None if is_structural(s.text) else frame_words(s.text)
        conn = connectives(s.text) if head else set()
        if head and conn and (not run or (shared & head and shared_conn & conn)):
            shared = (shared & head) if run else head
            shared_conn = (shared_conn & conn) if run else conn
            run.append(s)
            continue
        if len(run) >= 3:
            hits.append(_run_hit("repeated-frame", run, sorted(shared)[:1]))
        run = [s] if (head and conn) else []
        shared = head or set()
        shared_conn = conn

    # runs of verbless fragments, which is how a counted list gets padded out.
    # Short ones are bylines, dates and captions, not prose.
    run = []
    for s in sentences + [Sentence("", len(masked))]:
        if (
            s.text
            and not is_structural(s.text)
            and len(WORD_RE.findall(s.text)) >= 5
            and not has_finite_verb(s.text)
        ):
            run.append(s)
            continue
        if len(run) >= 2:
            hits.append(_run_hit("fragment-run", run))
        run = []

    return hits


def frame_words(sentence: str, depth: int = 4) -> set[str]:
    """The content words near the front of a sentence, which is the part a
    parallel run holds fixed while the rest of the sentence varies."""
    words = [w.lower() for w in WORD_RE.findall(sentence)]
    return {w for w in words[:depth] if w not in FUNCTION_WORDS and len(w) > 2}


FRAME_CONNECTIVES = (
    ", which means",
    ", which is",
    ", so that",
    ", at which point",
    ", rather than",
    ", instead of",
    ", because",
    ", since",
    ", so ",
    " means ",
)


def connectives(sentence: str) -> set[str]:
    low = sentence.lower()
    return {c for c in FRAME_CONNECTIVES if c in low}


AUXILIARIES = {
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "am",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "can",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "must",
    "shall",
    "ought",
}


def has_finite_verb(sentence: str) -> bool:
    """Cheap and deliberately generous: an auxiliary, or any inflected word.
    A sentence this says has no verb is almost always a real fragment."""
    for word in WORD_RE.findall(sentence.lower()):
        if word in AUXILIARIES:
            return True
        if len(word) > 3 and word.endswith(("s", "ed", "ing")):
            return True
    return False


def _run_hit(rule_id: str, run: list[Sentence], extra: list[str] | None = None) -> dict:
    text = " ".join(s.text for s in run)
    if extra:
        text = f'on "{extra[0]}": {text}'
    return {
        "rule": rule_id,
        "start": run[0].start,
        "match": text,
        "count": len(run),
    }


# ----------------------------------------------------------- structural rules

# pictographs and the tick/cross/warning dingbats, not arrows or symbols: "↔"
# in a title is notation, "🚀" is decoration
EMOJI_RE = re.compile("[\U0001f300-\U0001faff✅❌⚠✨⭐❗✔ℹ🌟]")
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
# unordered only: a numbered list of bolded step names is how plans are written
BOLD_LEAD_RE = re.compile(r"^\s*[-*+]\s+\*\*[^*\n]{2,60}\*\*\s*[:—–-]?\s+\S")
# a bolded phrase is a definition-list term; a bolded *sentence* is a slot label
# the model wrote to look organised ("**What it delivers.**")
BOLD_PARA_RE = re.compile(r"^\*\*[^*\n]{2,80}[^*\s.]\.\*\*")


def scan_structure(masked: str) -> list[dict]:
    """Markdown shapes LLMs reach for: every bullet a bold label, emoji in
    headings. Runs of bold-label bullets are one hit, not one per bullet."""
    hits: list[dict] = []
    offset = 0
    run: list[tuple[int, str]] = []

    def flush(run: list[tuple[int, str]]) -> None:
        if len(run) >= 3:
            hits.append(
                {
                    "rule": "bold-lead-bullets",
                    "start": run[0][0],
                    "match": run[0][1].strip(),
                    "count": len(run),
                }
            )

    for line in masked.split("\n"):
        stripped = line.strip()
        if BOLD_LEAD_RE.match(line):
            run.append((offset, line))
        elif stripped:
            flush(run)
            run = []
        if BOLD_PARA_RE.match(line):
            hits.append(
                {
                    "rule": "bold-lead-paragraph",
                    "start": offset,
                    "match": BOLD_PARA_RE.match(line).group(0),
                    "count": 0,
                }
            )
        if (HEADING_RE.match(line) or LIST_ITEM_RE.match(stripped)) and EMOJI_RE.search(line):
            hits.append(
                {
                    "rule": "emoji-decoration",
                    "start": offset,
                    "match": stripped,
                    "count": 0,
                }
            )
        offset += len(line) + 1
    flush(run)
    return hits


# ------------------------------------------------------------------ reporting


@dataclass
class Hit:
    rule: str
    line: int
    col: int
    match: str
    count: int = 0
    suppressed: bool = False


@dataclass
class FileReport:
    path: str
    words: int
    hits: list[Hit] = field(default_factory=list)
    error: str | None = None

    @property
    def listed(self) -> list[Hit]:
        return [h for h in self.hits if not h.suppressed and not BY_ID[h.rule].density_only]

    @property
    def suppressed(self) -> list[Hit]:
        return [h for h in self.hits if h.suppressed]

    def density_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for h in self.hits:
            if BY_ID[h.rule].density_only:
                counts[h.rule] = counts.get(h.rule, 0) + 1
        return counts


def line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    return line, offset - last_nl


def select_rules(only: set[str], skip: set[str], optional: set[str]) -> list[Rule]:
    chosen = []
    for rule in ALL_RULES:
        if only:
            if rule.id in only:
                chosen.append(rule)
            continue
        if rule.id in skip:
            continue
        if rule.optional and rule.id not in optional:
            continue
        chosen.append(rule)
    return chosen


def scan_text(
    text: str,
    path: str,
    rules: list[Rule],
    context: int,
    all_hits: bool = False,
) -> FileReport:
    masked = mask_non_prose(text)
    masked_with_urls = mask_non_prose(text, keep_urls=True)
    report = FileReport(path=path, words=len(WORD_RE.findall(masked)))
    active = {r.id for r in rules}

    for rule in rules:
        if rule.id not in COMPILED:
            continue
        haystack = masked_with_urls if rule.id == "chatbot-leftover" else masked
        excl = COMPILED_EXCL.get(rule.id)
        counter = COMPILED_COUNT.get(rule.id)
        for m in COMPILED[rule.id].finditer(haystack):
            snippet = re.sub(r"\s+", " ", m.group(0)).strip()
            window = haystack[max(0, m.start() - 20) : m.end() + 20]
            if excl and excl.search(window):
                continue
            line, col = line_col(text, m.start())
            count = len(counter.findall(snippet)) if counter else 0
            report.hits.append(Hit(rule.id, line, col, snippet[:context], count))

    for raw in scan_sentences(masked) + scan_structure(masked):
        if raw["rule"] not in active:
            continue
        line, col = line_col(text, raw["start"])
        match = re.sub(r"\s+", " ", raw["match"])[:context]
        report.hits.append(Hit(raw["rule"], line, col, match, raw["count"]))

    if not all_hits:
        per_rule: dict[str, int] = {}
        for h in report.hits:
            per_rule[h.rule] = per_rule.get(h.rule, 0) + 1
        for h in report.hits:
            rule = BY_ID[h.rule]
            rate = per_rule[h.rule] / report.words * 1000 if report.words else 0
            if per_rule[h.rule] < rule.min_count or rate < rule.min_per_1k:
                h.suppressed = True

    report.hits.sort(key=lambda h: (h.line, h.col))
    return report


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def print_report(report: FileReport) -> None:
    header = f"{report.path}  ({plural(report.words, 'word')})"
    print(header)
    print("-" * len(header))
    if report.error:
        print(f"error: {report.error}\n")
        return

    listed = report.listed
    by_rule: dict[str, list[Hit]] = {}
    for h in listed:
        by_rule.setdefault(h.rule, []).append(h)

    for rule in sorted(by_rule, key=lambda r: (-len(by_rule[r]), r)):
        hits = by_rule[rule]
        print(f"\n[{rule}] {DESCRIPTIONS[rule]}  ({len(hits)})")
        for h in hits:
            badge = f" x{h.count}" if h.count else ""
            print(f"  {h.line}:{h.col}{badge}  {h.match}")

    total = len(listed)
    if not total:
        print("clean")
    else:
        per_1k = total / report.words * 1000 if report.words else 0
        print(
            f"\n{plural(total, 'hit')} across {plural(len(by_rule), 'pattern')} "
            f"({per_1k:.1f} per 1000 words)"
        )

    for rule, count in sorted(report.density_counts().items()):
        rate = count / report.words * 1000 if report.words else 0
        verdict = "high" if rate > 6.7 else "ok"
        print(
            f"{DESCRIPTIONS[rule].lower()} density: {count} in "
            f"{plural(report.words, 'word')} ({rate:.1f} per 1000, {verdict})"
        )

    below: dict[str, int] = {}
    for h in report.suppressed:
        below[h.rule] = below.get(h.rule, 0) + 1
    if below:
        parts = [f"{r} x{n} (needs {BY_ID[r].min_count})" for r, n in sorted(below.items())]
        print(f"below threshold, not listed: {', '.join(parts)}")
    print()


def print_summary(reports: list[FileReport]) -> None:
    by_rule: dict[str, int] = {}
    words = 0
    for r in reports:
        words += r.words
        for h in r.listed:
            by_rule[h.rule] = by_rule.get(h.rule, 0) + 1
    total = sum(by_rule.values())
    header = f"summary: {plural(len(reports), 'file')}, {plural(words, 'word')}"
    print(header)
    print("=" * len(header))
    for rule, n in sorted(by_rule.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {n:5d}  {rule}")
    per_1k = total / words * 1000 if words else 0
    print(f"  {total:5d}  total ({per_1k:.1f} per 1000 words)\n")


def print_rules(optional: set[str]) -> None:
    for group, rules in (
        ("regex", [r for r in RULES if not r.optional]),
        ("structural", STRUCTURAL_RULES),
        ("sentence", SENTENCE_RULES),
        ("optional", [r for r in RULES if r.optional]),
    ):
        print(f"\n{group}")
        for rule in rules:
            note = f"  [{rule.note}]" if rule.note else ""
            print(f"  {rule.id:22s} {rule.description}{note}")
    print()


def collect_paths(paths: list[str]) -> list[str]:
    found: list[str] = []
    for path in paths:
        if path == "-" or not os.path.isdir(path):
            found.append(path)
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules")
            for name in sorted(files):
                if os.path.splitext(name)[1].lower() in TEXT_SUFFIXES:
                    found.append(os.path.join(root, name))
    return found


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        add_help=True, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", metavar="FILE")
    ap.add_argument("--colon-triple", action="store_true")
    ap.add_argument("--em-dash", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--all-hits", action="store_true")
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--context", type=int, default=90)
    args = ap.parse_args(argv)

    optional = {r.id for r in RULES if r.optional} if args.all else set()
    if args.colon_triple:
        optional.add("colon-triple")
    if args.em_dash:
        optional.add("em-dash")

    if args.list_rules:
        print_rules(optional)
        return 0
    if not args.paths:
        ap.error("no files given")

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown = (only | skip) - set(BY_ID)
    if unknown:
        ap.error(f"unknown rule(s): {', '.join(sorted(unknown))}")
    rules = select_rules(only, skip, optional)

    reports: list[FileReport] = []
    for path in collect_paths(args.paths):
        if path == "-":
            text, label = sys.stdin.read(), "<stdin>"
        else:
            label = path
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError as exc:
                reports.append(FileReport(path=label, words=0, error=str(exc)))
                continue
        try:
            reports.append(scan_text(text, label, rules, args.context, args.all_hits))
        except Exception as exc:  # a broken rule must not lose the other files
            reports.append(FileReport(path=label, words=0, error=f"{type(exc).__name__}: {exc}"))

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "path": r.path,
                        "words": r.words,
                        "error": r.error,
                        "hits": [
                            {
                                "rule": h.rule,
                                "description": DESCRIPTIONS[h.rule],
                                "line": h.line,
                                "col": h.col,
                                "match": h.match,
                                "count": h.count,
                                "suppressed": h.suppressed,
                            }
                            for h in r.hits
                        ],
                        "totals": {
                            "listed": len(r.listed),
                            "suppressed": len(r.suppressed),
                            "density": r.density_counts(),
                        },
                    }
                    for r in reports
                ],
                indent=2,
            )
        )
    else:
        shown = [r for r in reports if r.listed or r.error or not args.quiet]
        for r in shown:
            print_report(r)
        if args.summary and len(reports) > 1:
            print_summary(reports)

    if all(r.error for r in reports):
        for r in reports:
            print(f"{r.path}: {r.error}", file=sys.stderr)
        return 2
    return 1 if any(r.listed for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
