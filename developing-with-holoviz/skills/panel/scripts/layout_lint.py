#!/usr/bin/env python3
"""Live-browser layout lint: DOM-as-text findings instead of a screenshot.

Loads a running app's URL in a real (headless) browser at each of several
viewport widths and inspects the rendered DOM/CSSOM for geometry and contrast
issues that don't require a human eye — viewport overflow, touch targets
under 44px, WCAG text contrast under 4.5:1, overlapping elements, siblings
that should share a left edge but don't, and font-size sprawl. Output is a
short violation list, not an image.

Usage:
    python layout_lint.py http://localhost:5007/app_name
    python layout_lint.py http://localhost:5007/app_name --widths 1400,768,390

Exits 0 with no output if clean. Exits 1 and prints one line per violation:
    [WIDTHpx] [CHECK_ID] message

Requires: playwright (`pip install playwright && playwright install chromium`) —
already a dependency for the screenshot loop in iterating-on-panel-apps.md.
Point it at an already-running `panel serve` process; it doesn't start one.

What this does NOT do (by design, see designing-visual-quality.md for that):
hierarchy, whitespace rhythm, whether the design looks "templated" — anything
requiring taste rather than a number. This tool is the numbers-only half.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

DEFAULT_WIDTHS = (1400, 768, 390)
VIEWPORT_HEIGHT = 900
MIN_TOUCH_TARGET = 44
MIN_CONTRAST_RATIO = 4.5
MAX_DISTINCT_FONT_SIZES = 6
ALIGNMENT_EPSILON = 2.0  # px
OVERLAP_MIN_FRACTION = 0.3  # of the smaller element's area

# Extracts one flat list of visible elements with the geometry/style data every
# check below needs. Kept to a single evaluate() call per width so the
# Python/JS round trip happens once, not once per check.
DOM_EXTRACT_JS = """
() => {
  function selectorFor(el) {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? '#' + el.id : '';
    const cls = el.classList.length ? '.' + el.classList[0] : '';
    return tag + id + cls;
  }
  function effectiveBackground(el) {
    let node = el;
    while (node) {
      const bg = getComputedStyle(node).backgroundColor;
      if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
      node = node.parentElement;
    }
    return 'rgb(255, 255, 255)';
  }

  const all = Array.from(document.querySelectorAll('body *'));
  const visible = [];
  const indexOf = new Map();
  for (const el of all) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden'
        || parseFloat(style.opacity) === 0) continue;
    indexOf.set(el, visible.length);
    visible.push(el);
  }

  const elements = visible.map((el, i) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    let parentIdx = -1;
    let p = el.parentElement;
    while (p) {
      if (indexOf.has(p)) { parentIdx = indexOf.get(p); break; }
      p = p.parentElement;
    }
    const hasDirectText = Array.from(el.childNodes).some(
      n => n.nodeType === 3 && n.textContent.trim().length > 0
    );
    const isInteractive = (
      ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)
      || el.getAttribute('role') === 'button'
      || style.cursor === 'pointer'
    );
    const hasOwnBackground = (() => {
      const bg = style.backgroundColor;
      return bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent';
    })();
    return {
      idx: i,
      parentIdx: parentIdx,
      sel: selectorFor(el),
      tag: el.tagName,
      classes: Array.from(el.classList),
      left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
      width: rect.width, height: rect.height,
      position: style.position,
      color: style.color,
      bgColor: hasDirectText ? effectiveBackground(el) : null,
      fontSize: parseFloat(style.fontSize),
      hasDirectText: hasDirectText,
      isInteractive: isInteractive,
      hasOwnBackground: hasOwnBackground,
    };
  });

  return {
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    elements: elements,
  };
}
"""


@dataclass
class Violation:
    check: str
    width: int
    message: str

    def format(self) -> str:
        return f"[{self.width}px] [{self.check}] {self.message}"


# ---------------------------------------------------------------------------
# Color math (WCAG 2.1 contrast)
# ---------------------------------------------------------------------------

_RGB_RE = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+))?\)")


def _parse_rgb(css_color: str | None) -> tuple[float, float, float] | None:
    if not css_color:
        return None
    m = _RGB_RE.match(css_color)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(rgb1: tuple[float, float, float], rgb2: tuple[float, float, float]) -> float:
    l1, l2 = _relative_luminance(rgb1), _relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# Checks — each takes the extracted DOM dict + the viewport width being tested
# ---------------------------------------------------------------------------


def check_overflow(dom: dict, width: int) -> list[Violation]:
    """Horizontal overflow at this width — the DOM-as-text replacement for
    'does the screenshot show a horizontal scrollbar'. Reports the root-cause
    element(s) (overflowing while their own parent doesn't), not every
    descendant caught in the same overflow, and caps the list at 3."""
    if dom["scrollWidth"] <= dom["clientWidth"] + 1:
        return []
    elements = dom["elements"]
    by_idx = {e["idx"]: e for e in elements}
    culprits = []
    for e in elements:
        if e["right"] <= width + 1:
            continue
        parent = by_idx.get(e["parentIdx"])
        if parent is None or parent["right"] <= width + 1:
            culprits.append(e)
    culprits.sort(key=lambda e: -e["right"])
    return [
        Violation(
            "VIEWPORT_OVERFLOW",
            width,
            f"`{e['sel']}` extends to {e['right']:.0f}px, beyond the {width}px viewport — "
            "check for a missing width_option/Container clamp or an unconstrained-width child.",
        )
        for e in culprits[:3]
    ]


def check_touch_targets(dom: dict, width: int) -> list[Violation]:
    """Interactive elements under the 44x44px minimum touch target. Groups
    repeats by selector so N identical small icon buttons produce one line,
    not N."""
    small = [
        e
        for e in dom["elements"]
        if e["isInteractive"] and min(e["width"], e["height"]) < MIN_TOUCH_TARGET
    ]
    groups: dict[str, list[dict]] = {}
    for e in small:
        groups.setdefault(e["sel"], []).append(e)
    violations = []
    for sel, members in groups.items():
        smallest = min(members, key=lambda e: min(e["width"], e["height"]))
        count = f"{len(members)} elements matching" if len(members) > 1 else "Element"
        violations.append(
            Violation(
                "TOUCH_TARGET_TOO_SMALL",
                width,
                f"{count} `{sel}` under {MIN_TOUCH_TARGET}x{MIN_TOUCH_TARGET}px "
                f"(smallest: {smallest['width']:.0f}x{smallest['height']:.0f}px).",
            )
        )
    return violations


def check_contrast(dom: dict, width: int) -> list[Violation]:
    """WCAG text contrast under 4.5:1, using the nearest non-transparent
    ancestor background as the effective background (computed in JS, since
    that walk needs live computed styles)."""
    violations = []
    seen: set[tuple[str, str, str]] = set()
    for e in dom["elements"]:
        if not e["hasDirectText"] or e["bgColor"] is None:
            continue
        fg, bg = _parse_rgb(e["color"]), _parse_rgb(e["bgColor"])
        if fg is None or bg is None:
            continue
        ratio = _contrast_ratio(fg, bg)
        if ratio < MIN_CONTRAST_RATIO:
            key = (e["sel"], e["color"], e["bgColor"])
            if key in seen:
                continue
            seen.add(key)
            violations.append(
                Violation(
                    "LOW_CONTRAST",
                    width,
                    f"`{e['sel']}` text contrast is {ratio:.2f}:1 (needs \u2265 "
                    f"{MIN_CONTRAST_RATIO}:1) — {e['color']} on {e['bgColor']}.",
                )
            )
    return violations


def _rects_overlap(a: dict, b: dict, min_fraction: float = OVERLAP_MIN_FRACTION) -> bool:
    left, right = max(a["left"], b["left"]), min(a["right"], b["right"])
    top, bottom = max(a["top"], b["top"]), min(a["bottom"], b["bottom"])
    if right <= left or bottom <= top:
        return False
    overlap_area = (right - left) * (bottom - top)
    smaller_area = min(a["width"] * a["height"], b["width"] * b["height"])
    return smaller_area > 0 and (overlap_area / smaller_area) >= min_fraction


def _is_ancestor(ancestor_idx: int, node_idx: int, by_idx: dict[int, dict]) -> bool:
    node = by_idx.get(node_idx)
    while node is not None and node["parentIdx"] != -1:
        if node["parentIdx"] == ancestor_idx:
            return True
        node = by_idx.get(node["parentIdx"])
    return False


def check_overlap(dom: dict, width: int) -> list[Violation]:
    """Unintentional overlap between two content-bearing elements — restricted
    to elements in normal flow (position: static/relative), since fixed/
    absolute is how Dialogs, SpeedDials, and Tooltips *intentionally* float
    over content, and restricted to 'meaningful' elements (has its own
    background, has direct text, or is interactive) rather than every
    structural wrapper div, to keep this from being O(n^2) noise."""
    by_idx = {e["idx"]: e for e in dom["elements"]}
    candidates = [
        e
        for e in dom["elements"]
        if e["position"] in ("static", "relative")
        and (e["hasOwnBackground"] or e["hasDirectText"] or e["isInteractive"])
    ]
    violations = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            if a["idx"] == b["parentIdx"] or b["idx"] == a["parentIdx"]:
                continue
            if _is_ancestor(a["idx"], b["idx"], by_idx) or _is_ancestor(b["idx"], a["idx"], by_idx):
                continue
            if _rects_overlap(a, b):
                key = tuple(sorted((a["sel"], b["sel"])))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                violations.append(
                    Violation(
                        "ELEMENT_OVERLAP",
                        width,
                        f"`{a['sel']}` and `{b['sel']}` visually overlap.",
                    )
                )
    return violations


def check_misaligned_left_edges(dom: dict, width: int) -> list[Violation]:
    """Siblings sharing a parent and a tag+class signature (a strong signal
    they're meant to read as identical rows/cards) whose left edges don't
    match, when they're stacked vertically (a side-by-side row/Grid of the
    same width is a different, intentional layout and is excluded)."""
    groups: dict[tuple, list[dict]] = {}
    for e in dom["elements"]:
        key = (e["parentIdx"], e["tag"], tuple(e["classes"]))
        groups.setdefault(key, []).append(e)

    violations = []
    for (_parent_idx, tag, classes), members in groups.items():
        if len(members) < 3:
            continue
        tops = [e["top"] for e in members]
        if max(tops) - min(tops) < ALIGNMENT_EPSILON:
            continue  # side-by-side row, not a stacked column
        lefts = [e["left"] for e in members]
        if max(lefts) - min(lefts) <= ALIGNMENT_EPSILON:
            continue
        median_left = sorted(lefts)[len(lefts) // 2]
        outlier = max(members, key=lambda e: abs(e["left"] - median_left))
        cls_str = "." + ".".join(classes) if classes else ""
        violations.append(
            Violation(
                "MISALIGNED_LEFT_EDGE",
                width,
                f"{len(members)} siblings matching `{tag.lower()}{cls_str}` don't share a "
                f"left edge (range {min(lefts):.0f}\u2013{max(lefts):.0f}px) — e.g. "
                f"`{outlier['sel']}`.",
            )
        )
    return violations


def check_font_scale(dom: dict, width: int) -> list[Violation]:
    """Informational: how many distinct font-sizes are in use. Not a hard
    pass/fail — there's no way to know an app's intended type scale from the
    DOM alone — but a page with a dozen distinct sizes almost never has a
    deliberate one, so this is worth a look even though it isn't a violation
    of a specific rule the way the others are."""
    sizes = sorted(
        {round(e["fontSize"], 1) for e in dom["elements"] if e["hasDirectText"] and e["fontSize"]}
    )
    if len(sizes) > MAX_DISTINCT_FONT_SIZES:
        return [
            Violation(
                "FONT_SCALE_SPRAWL",
                width,
                f"{len(sizes)} distinct font-sizes in use "
                f"({', '.join(f'{s:g}px' for s in sizes)}) — consider consolidating to a "
                "smaller type scale (informational, not a hard rule).",
            )
        ]
    return []


CHECKS = (
    check_overflow,
    check_touch_targets,
    check_contrast,
    check_overlap,
    check_misaligned_left_edges,
    check_font_scale,
)


def run_checks(dom: dict, width: int) -> list[Violation]:
    violations: list[Violation] = []
    for check in CHECKS:
        violations += check(dom, width)
    return violations


def lint_url(url: str, widths=DEFAULT_WIDTHS, timeout: int = 30000) -> list[Violation]:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    all_violations: list[Violation] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle")
        except PlaywrightError as e:
            browser.close()
            raise ConnectionError(f"Could not load {url} — is the app being served? ({e})") from e
        for width in widths:
            page.set_viewport_size({"width": width, "height": VIEWPORT_HEIGHT})
            # Same loading-overlay wait as the screenshot loop in
            # iterating-on-panel-apps.md — a page with no .pn-loading element
            # (e.g. this check running against a non-Panel page) passes
            # immediately, since the selector then matches nothing. A timeout
            # here means the app never finished loading at this width — worth
            # a violation in its own right, not a crash that discards every
            # width already checked.
            try:
                page.wait_for_function(
                    "() => !document.querySelector('.pn-loading')", timeout=timeout
                )
            except PlaywrightError:
                all_violations.append(
                    Violation(
                        "LOAD_TIMEOUT",
                        width,
                        f"App did not finish loading within {timeout}ms at {width}px "
                        "(a .pn-loading overlay never cleared) — checks at this width "
                        "were skipped.",
                    )
                )
                continue
            page.wait_for_timeout(150)
            dom = page.evaluate(DOM_EXTRACT_JS)
            all_violations += run_checks(dom, width)
        browser.close()
    return all_violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument(
        "--widths",
        default=",".join(str(w) for w in DEFAULT_WIDTHS),
        help="comma-separated viewport widths, default 1400,768,390",
    )
    args = parser.parse_args(argv)
    widths = [int(w) for w in args.widths.split(",")]

    try:
        violations = lint_url(args.url, widths=widths)
    except ConnectionError as e:
        print(f"layout_lint: {e}", file=sys.stderr)
        return 2
    for v in violations:
        print(v.format())
    if not violations:
        print(f"layout_lint: clean ({len(widths)} widths checked)")
        return 0
    print(
        f"\nlayout_lint: {len(violations)} violation(s) across {len(widths)} widths",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
