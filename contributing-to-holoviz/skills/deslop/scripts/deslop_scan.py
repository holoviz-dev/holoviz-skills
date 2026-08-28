#!/usr/bin/env python3
"""Scan prose for LLM slop patterns.

Usage:
    deslop_scan.py FILE [FILE ...]     scan files
    deslop_scan.py -                   scan stdin

Options:
    --colon-triple   enable the colon-into-a-triple check (noisy in docs)
    --em-dash        enable em-dash density reporting
    --all            enable every optional check
    --json           emit JSON instead of a text report
    --context N      characters of match text to show (default 90)

Fenced code blocks, indented code blocks, inline code and blockquotes are
skipped. Exit status is 1 when hits were found, 0 when clean.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field

ICASE = re.IGNORECASE

# ---------------------------------------------------------------- regex rules

# Each rule: (id, description, pattern, exclusion pattern or None)
RULES: list[tuple[str, str, str, str | None]] = [
    # -- rhetorical tics -----------------------------------------------------
    (
        "no-x-no-y",
        '"No X, no Y" chain',
        r"\bno\s+[\w''\-]+(?:\s+[\w''\-]+){0,2}\s*[,;]\s*(?:and\s+|or\s+)?"
        r"no\s+[\w''\-]+(?:\s+[\w''\-]+){0,2}"
        r"(?:\s*[,;]\s*(?:and\s+|or\s+)?no\s+[\w''\-]+(?:\s+[\w''\-]+){0,2})*",
        None,
    ),
    (
        "thats-the-whole",
        '"That\'s the whole ..."',
        r"\b(?:that|this)(?:'s|\u2019s| is)\s+the\s+whole\s+[\w-]+",
        None,
    ),
    (
        "did-not-chain",
        '"Did not X, did not Y" chain',
        r"\b(?:did\s+not|didn['\u2019]t)\s+[\w''\-]+(?:\s+[\w''\-]+){0,2}\s*[,;]\s*(?:and\s+|or\s+)?"
        r"(?:did\s+not|didn['\u2019]t)\s+[\w''\-]+(?:\s+[\w''\-]+){0,2}"
        r"(?:\s*[,;]\s*(?:and\s+|or\s+)?(?:did\s+not|didn['\u2019]t)\s+[\w''\-]+(?:\s+[\w''\-]+){0,2})*",
        None,
    ),
    (
        "dont-verb-it",
        '"Don\'t VERB it ... VERB it"',
        r"\b(?:do\s+not|don['\u2019]t)\s+(\w+)\s+(?:it|this|that)\b[^.!?]{0,60}[.!?;:\u2014-]\s*"
        r"(?:\w+[\s,]+){0,3}\1\s+(?:it|this|that)\b",
        None,
    ),
    (
        "sit-with-that",
        '"Sit with that"',
        r"\bsit\s+with\s+(?:that|this|it|the\s+\w+)",
        None,
    ),
    (
        "you-already-know",
        '"You already know"',
        r"\byou\s+already\s+know\b",
        None,
    ),
    (
        "is-the-entire",
        '"is the entire ..."',
        r"\b(?:is|are|was|were)\s+the\s+entire\s+[\w-]+",
        None,
    ),
    (
        "the-entire-x-is",
        '"The entire ... is"',
        r"\bthe\s+entire\s+(?:point|game|thing|idea|pitch|trick|premise|business\s+model)\s+(?:is|was)\b",
        None,
    ),
    (
        "is-the-whole",
        '"is the whole ..."',
        r"\b(?:is|are|was|were)\s+the\s+whole\s+(?:point|trick|pitch|idea|thing|game|premise|story)\b"
        r"|\bhere(?:'s|\u2019s| is)\s+the\s+whole\s+[\w-]+",
        None,
    ),
    (
        "is-real-and",
        '"is real, and / not"',
        r"\b(?:is|are|was|were)\s+real\s*[,;]?\s+(?:and|not|but)\b"
        r"|\bis\s+the\s+real\s+[\w-]+\s+and\s+it\b",
        r"real\s+(?:estate|time|numbers?|world|name|money|terms|analysis|user)",
    ),
    (
        "punchline",
        '"The punchline is"',
        r"\bthe\s+punchline\s*(?:is\b|was\b|[:?])",
        None,
    ),
    (
        "worth-naming",
        '"Worth naming"',
        r"\b(?:is|it['\u2019]s|its)?\s*worth\s+naming\b|^\s*worth\s+naming\s*:",
        r"naming\s+names",
    ),
    (
        "thats-not-nothing",
        '"That\'s not nothing"',
        r"\b(?:that|this|it|which)(?:'s|\u2019s| is)\s+not\s+nothing\b",
        None,
    ),
    (
        "performative-honesty",
        "Performative honesty",
        r"\bI\s+(?:won['\u2019]t|will\s+not)\s+pretend\b"
        r"|\bI['\u2019]?ll\s+be\s+honest\b|\bI\s+will\s+be\s+honest\b"
        r"|\blet['\u2019]?s\s+be\s+honest\b|\bif\s+I['\u2019]?m\s+being\s+honest\b"
        r"|\bto\s+be\s+(?:clear|honest|fair)\b|\bin\s+all\s+honesty\b"
        r"|(?:^|(?<=[.!?]\s)|(?<=\n))(?:Honestly|Look|Truthfully|Frankly)\s*[,:]",
        None,
    ),
    (
        "thats-the-part",
        '"That\'s the part ..."',
        r"\b(?:that|this)(?:'s|\u2019s| is)\s+the\s+part\b"
        r"|\bmy\s+favou?rite\s+part\s+(?:of|is|about)\b"
        r"|\bthe\s+part\s+that\s+(?:makes\s+me|I\s+(?:like|trust|keep))\b",
        None,
    ),
    (
        "only-x-i-trust",
        '"The only X I trust"',
        r"\bthe\s+only\s+[\w\s''\-]{0,25}?(?:I\s+trust|that\s+(?:matters|counts)|it\s+needs|"
        r"worth\s+\w+|you\s+need)\b",
        None,
    ),
    (
        "take-my-word",
        '"Don\'t take my word for it"',
        r"\btake\s+my\s+word\s+for\b",
        None,
    ),
    (
        "turns-out",
        '"Turns out ..."',
        r"(?:^|(?<=[.!?]\s)|(?<=\n)|(?<=\u2014)|(?<=\u2013))\s*Turns\s+out\b"
        r"|\bit\s+turn(?:s|ed)\s+out\s+that\b",
        None,
    ),
    (
        "fits-in-head",
        '"Fits in your head" / dev-blog boilerplate',
        r"\b(?:hold|fit|fits|holds)\s+(?:it\s+)?in\s+your\s+head\b"
        r"|\bsmall\s+enough\s+to\s+(?:hold|fit)\b"
        r"|\bbatteries[\s-]included\b|\bit\s+just\s+works\b|\bzero[\s-]config\b"
        r"|\bsane\s+defaults\b|\bjust\s+works,?\s+out\s+of\s+the\s+box\b",
        None,
    ),
    (
        "heres-the-twist",
        '"Here\'s the twist"',
        r"\bhere(?:'s|\u2019s| is)\s+the\s+(?:twist|thing|catch|kicker|rub|trick|punchline|"
        r"first|best\s+part|problem)\b",
        None,
    ),
    (
        "x-is-dead",
        '"X is dead"',
        r"\b[\w-]+\s+(?:is|are)\s+dead\b(?!\s*(?:code|letter|end|link))" r"|\blong\s+live\s+[\w-]+",
        None,
    ),
    (
        "thats-why-mattered",
        '"That\'s why X mattered"',
        r"\b(?:that|this)(?:'s|\u2019s| is)\s+why\s+[^.!?]{3,70}\bmatter(?:ed|s)\b",
        None,
    ),
    (
        "stranded-auxiliary",
        "Stranded auxiliary contrast",
        r"\b(?:didn['\u2019]t|doesn['\u2019]t|don['\u2019]t|wasn['\u2019]t|weren['\u2019]t|isn['\u2019]t|aren['\u2019]t|hasn['\u2019]t|"
        r"haven['\u2019]t|hadn['\u2019]t|wouldn['\u2019]t|won['\u2019]t|couldn['\u2019]t|can['\u2019]t|shouldn['\u2019]t)\s*[.;]"
        r"|\b(?:did|does|was|were|is|are|has|have|had|would|will|could|can|should)\s+not\s*[.;]",
        None,
    ),
    # -- signs of AI writing -------------------------------------------------
    (
        "ai-vocab",
        "AI vocabulary word",
        r"\b(?:delve[sd]?|delving|tapestry|meticulous(?:ly)?|pivotal|intricate(?:ly)?|interplay|"
        r"underscor(?:e|es|ed|ing)|garner(?:ed|ing|s)?|bolster(?:ed|ing|s)?|vibrant|bustling|"
        r"multifaceted|seamless(?:ly)?|ever-evolving|testament|realm|myriad|plethora|"
        r"foster(?:ing|s|ed)?|harness(?:ing|es|ed)?|paramount|nuanced|holistic|"
        r"profound(?:ly)?|elevat(?:e|es|ed|ing)|unlock(?:s|ed|ing)?|showcas(?:e|es|ed|ing)|"
        r"embark(?:ed|ing|s)?|leverag(?:e|es|ed|ing)|cornerstone|crucial(?:ly)?|"
        r"transformative|unwavering|indelible|beacon)\b",
        None,
    ),
    (
        "not-just-but",
        '"Not just X, but Y"',
        r"\bnot\s+(?:just|only|merely|simply)\s+[^,;.!?]{1,50}[,;]?\s*but\s+(?:also\s+)?"
        r"|\bit(?:'s|\u2019s| is)\s+not\s+[^—–.!?]{1,45}[—–]\s*it(?:'s|\u2019s| is)\b",
        None,
    ),
    (
        "important-to-note",
        '"It\'s important to note"',
        r"\bit\s+(?:is|was)\s+important\s+to\s+note\b|\bit(?:'s|\u2019s)\s+important\s+to\s+note\b"
        r"|\b(?:it(?:'s|\u2019s)\s+|it\s+is\s+)?worth\s+(?:noting|mentioning|pausing|considering|"
        r"asking|remembering)\b|\bshould\s+be\s+noted\b|\bimportantly,",
        None,
    ),
    (
        "testament",
        '"Stands as a testament"',
        r"\b(?:stands|serves|stand|serve)\s+as\s+a\s+(?:testament|reminder|symbol|"
        r"powerful\s+\w+)\b|\bis\s+a\s+testament\s+to\b",
        None,
    ),
    (
        "crucial-role",
        '"Plays a crucial role"',
        r"\bplay(?:s|ed|ing)?\s+an?\s+(?:crucial|pivotal|vital|key|significant|important|"
        r"central|essential|major)\s+role\b",
        None,
    ),
    (
        "evolving-landscape",
        '"Ever-evolving landscape"',
        r"\bever[\s-](?:evolving|changing|shifting|expanding|growing)\b"
        r"|\b(?:evolving|changing|shifting|digital|modern|current|competitive)\s+landscape\b"
        r"|\bin\s+today(?:'s|\u2019s)\s+(?:fast[\s-]paced|digital|modern|competitive)\b"
        r"|\bin\s+an\s+era\s+(?:of|where)\b",
        None,
    ),
    (
        "experts-argue",
        '"Experts argue"',
        r"\b(?:experts|critics|observers|analysts|commentators|researchers|scholars)\s+"
        r"(?:argue|say|agree|note|noted|believe|suggest|point\s+out|contend|warn)\b"
        r"|\bsome\s+(?:critics|experts|observers)\s+have\s+\w+\b"
        r"|\bindustry\s+reports\s+indicate\b|\b(?:studies|reports|surveys)\s+(?:show|suggest|indicate)\b"
        r"|\bit\s+is\s+(?:widely|generally)\s+(?:believed|accepted|agreed)\b",
        None,
    ),
    (
        "despite-challenges",
        '"Despite these challenges"',
        r"\bdespite\s+(?:these|its|the)\s+challenges\b|\bfac(?:es|ed|ing)\s+(?:several|a\s+number\s+of|"
        r"numerous|significant)\s+challenges\b|\bchallenges\s+remain\b|\bremains\s+to\s+be\s+seen\b"
        r"|\b(?:only\s+)?time\s+will\s+tell\b|\bnot\s+without\s+its\s+challenges\b",
        None,
    ),
    (
        "participle-tail",
        "Participle sentence tail",
        r",\s*(?:highlighting|underscoring|showcasing|reflecting|emphasi[sz]ing|demonstrating|"
        r"illustrating|signal(?:l)?ing|ensuring|cementing|solidifying|marking|paving|"
        r"contributing\s+to|allowing\s+for|making\s+it\s+(?:a|an|one))\b",
        None,
    ),
    (
        "promotional",
        "Promotional boilerplate",
        r"\bnestled\s+(?:in|among|between)\b|\bin\s+the\s+heart\s+of\b"
        r"|\brich\s+(?:tapestry|heritage|history|culture)\b|\bhidden\s+gem\b"
        r"|\bboast(?:s|ed|ing)?\s+(?:a|an|its|some|impressive|over)\b|\bbreathtaking\b"
        r"|\bstunning\s+(?:views?|scenery|architecture)\b|\bmust[\s-]visit\b"
        r"|\ba\s+(?:true|real)\s+(?:testament|delight|treat)\b|\bvibrant\s+(?:culture|community|city)\b",
        None,
    ),
    (
        "chatbot-leftover",
        "Chatbot leftover",
        r"\bas\s+an\s+AI\s+(?:language\s+)?model\b|\bas\s+of\s+my\s+last\s+(?:update|training)\b"
        r"|\bknowledge\s+cut[\s-]?off\b|\bI\s+(?:cannot|can't)\s+browse\s+the\s+internet\b"
        r"|oaicite|contentReference|turn\d+(?:search|view|news)\d*|utm_source=|:contentReference",
        None,
    ),
]

OPTIONAL_RULES: dict[str, tuple[str, str, str, str | None]] = {
    "colon-triple": (
        "colon-triple",
        "Colon opening onto a triple",
        r":\s+[^,:;.!?\n]{2,40},\s+[^,:;.!?\n]{2,40},\s+(?:and\s+|or\s+)?[^,:;.!?\n]{2,40}",
        None,
    ),
    "em-dash": (
        "em-dash",
        "Em-dash",
        r"[\u2014\u2013]|(?<=\w)\s--\s(?=\w)",
        None,
    ),
}

COMPILED = {rid: re.compile(pat, ICASE) for rid, _, pat, _ in RULES}
COMPILED_EXCL = {rid: re.compile(ex, ICASE) for rid, _, _, ex in RULES if ex}
for _key, (_rid, _desc, _pat, _ex) in OPTIONAL_RULES.items():
    COMPILED[_rid] = re.compile(_pat, ICASE)
    if _ex:
        COMPILED_EXCL[_rid] = re.compile(_ex, ICASE)
DESCRIPTIONS = {rid: desc for rid, desc, _, _ in RULES}
DESCRIPTIONS.update({rid: desc for rid, desc, _, _ in OPTIONAL_RULES.values()})

# ------------------------------------------------------------- masking prose

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
LINK_TARGET_RE = re.compile(r"\]\([^)\s]+\)")
URL_RE = re.compile(r"\bhttps?://\S+")


def mask_non_prose(text: str, keep_urls: bool = False) -> str:
    """Blank out code and quotes, preserving offsets so positions stay valid."""
    lines = text.split("\n")
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        if fence is not None:
            out.append(" " * len(line))
            if line.strip().startswith(fence):
                fence = None
            continue
        m = FENCE_RE.match(line)
        if m:
            fence = m.group(2)[0] * 3
            out.append(" " * len(line))
            continue
        stripped = line.lstrip()
        is_indented_code = (
            line[:4] == "    "
            and not stripped.startswith(("-", "*", "+", ">", "|"))
            and not re.match(r"^\d+[.)]\s", stripped)
        )
        if is_indented_code or stripped.startswith(">"):
            out.append(" " * len(line))
            continue
        out.append(line)
    masked = "\n".join(out)
    masked = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), masked)
    masked = LINK_TARGET_RE.sub(lambda m: " " * len(m.group(0)), masked)
    if not keep_urls:
        masked = URL_RE.sub(lambda m: " " * len(m.group(0)), masked)
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
WORD_RE = re.compile(r"[A-Za-z][A-Za-z''\-]*")

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


STRUCTURAL_RE = re.compile(r"^(?:#{1,6}\s|\||[-*+]\s|\d+[.)]\s|!\[|\[!)")


def is_structural(text: str) -> bool:
    """Headings, table rows and list items. Parallelism there is deliberate
    formatting, not an echoing run, so they break runs instead of joining them."""
    return bool(STRUCTURAL_RE.match(text.strip()))


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
        last_word = WORD_RE.findall(s.text.lower())
        if merged and last_word:
            prev_tail = merged[-1].text.rstrip(".").split()[-1].lower().strip(".,;:")
            if prev_tail in ABBREV:
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
            hits.append(_run_hit("stacked-questions", run, len(run)))
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
            hits.append(_run_hit("repeated-openers", run, len(run)))
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
            hits.append(_run_hit("echoing-run", run, len(run)))
        current_skel = skel
        run = [s] if skel else []

    return hits


def _run_hit(rule_id: str, run: list[Sentence], count: int) -> dict:
    text = " ".join(s.text for s in run)
    return {
        "rule": rule_id,
        "start": run[0].start,
        "match": text,
        "count": count,
    }


SENTENCE_DESCRIPTIONS = {
    "stacked-questions": "Stacked rhetorical questions",
    "repeated-openers": "Repeated sentence openers",
    "echoing-run": "Echoing sentence run",
}
DESCRIPTIONS.update(SENTENCE_DESCRIPTIONS)

COUNTED_RULES = {
    "no-x-no-y": r"\bno\s+",
    "did-not-chain": r"\b(?:did\s+not|didn['\u2019]t)\b",
}

# ------------------------------------------------------------------ reporting


@dataclass
class Hit:
    rule: str
    line: int
    col: int
    match: str
    count: int = 0


@dataclass
class FileReport:
    path: str
    words: int
    hits: list[Hit] = field(default_factory=list)
    em_dashes: int = 0


def line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    return line, offset - last_nl


def scan_text(text: str, path: str, enabled_optional: set[str], context: int) -> FileReport:
    masked = mask_non_prose(text)
    masked_with_urls = mask_non_prose(text, keep_urls=True)
    report = FileReport(path=path, words=len(WORD_RE.findall(masked)))

    rule_ids = [rid for rid, _, _, _ in RULES]
    rule_ids += [OPTIONAL_RULES[k][0] for k in sorted(enabled_optional)]

    for rid in rule_ids:
        haystack = masked_with_urls if rid == "chatbot-leftover" else masked
        excl = COMPILED_EXCL.get(rid)
        for m in COMPILED[rid].finditer(haystack):
            snippet = re.sub(r"\s+", " ", m.group(0)).strip()
            window = haystack[max(0, m.start() - 20) : m.end() + 20]
            if excl and excl.search(window):
                continue
            count = 0
            if rid in COUNTED_RULES:
                count = len(re.findall(COUNTED_RULES[rid], snippet, ICASE))
            line, col = line_col(text, m.start())
            report.hits.append(Hit(rid, line, col, snippet[:context], count))

    for h in scan_sentences(masked):
        line, col = line_col(text, h["start"])
        report.hits.append(
            Hit(h["rule"], line, col, re.sub(r"\s+", " ", h["match"])[:context], h["count"])
        )

    if "em-dash" in enabled_optional:
        report.em_dashes = len([h for h in report.hits if h.rule == "em-dash"])
    report.hits.sort(key=lambda h: (h.line, h.col))
    return report


def print_report(report: FileReport, show_density: bool) -> None:
    header = f"{report.path}  ({report.words} words)"
    print(header)
    print("-" * len(header))
    if not report.hits:
        print("clean\n")
        return

    by_rule: dict[str, list[Hit]] = {}
    for h in report.hits:
        by_rule.setdefault(h.rule, []).append(h)

    for rule in sorted(by_rule, key=lambda r: (-len(by_rule[r]), r)):
        hits = by_rule[rule]
        print(f"\n[{rule}] {DESCRIPTIONS[rule]}  ({len(hits)})")
        for h in hits:
            badge = f" x{h.count}" if h.count else ""
            print(f"  {h.line}:{h.col}{badge}  {h.match}")

    total = len(report.hits)
    per_1k = total / report.words * 1000 if report.words else 0
    print(f"\n{total} hits across {len(by_rule)} patterns ({per_1k:.1f} per 1000 words)")
    if show_density and report.em_dashes and report.words:
        rate = report.em_dashes / report.words * 1000
        verdict = "high" if rate > 6.7 else "ok"
        print(
            f"em-dash density: {report.em_dashes} in {report.words} words "
            f"({rate:.1f} per 1000, {verdict})"
        )
    print()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        add_help=True, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="+", metavar="FILE")
    ap.add_argument("--colon-triple", action="store_true")
    ap.add_argument("--em-dash", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--context", type=int, default=90)
    args = ap.parse_args(argv)

    optional: set[str] = set()
    if args.colon_triple or args.all:
        optional.add("colon-triple")
    if args.em_dash or args.all:
        optional.add("em-dash")

    reports: list[FileReport] = []
    for path in args.paths:
        if path == "-":
            text, label = sys.stdin.read(), "<stdin>"
        else:
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError as exc:
                print(f"{path}: {exc}", file=sys.stderr)
                continue
            label = path
        reports.append(scan_text(text, label, optional, args.context))

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "path": r.path,
                        "words": r.words,
                        "hits": [
                            {
                                "rule": h.rule,
                                "description": DESCRIPTIONS[h.rule],
                                "line": h.line,
                                "col": h.col,
                                "match": h.match,
                                "count": h.count,
                            }
                            for h in r.hits
                        ],
                    }
                    for r in reports
                ],
                indent=2,
            )
        )
    else:
        for r in reports:
            print_report(r, show_density="em-dash" in optional)

    return 1 if any(r.hits for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
