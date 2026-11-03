"""Check a demo video HTML file for layout and caption defects before anyone watches it.

Seeks the page through its whole timeline in headless Chromium and reports, as
time ranges, what a viewer would notice and an agent reviewing stills misses:

- **error:** a console error or uncaught exception
- **overlap:** visible text from two elements drawn on top of each other
- **covers:** visible text drawn over an image, canvas, video or SVG
  (except one marked ``data-background``)
- **crowded:** text within ``--gap`` px of a box it doesn't belong to
- **clipped:** text cut off by the stage edge or an ``overflow: hidden`` box
- **small:** visible text under ``--min-font`` px (on a 1080 px stage)
- **captions:** an SRT cue whose words differ from the narration spec
- **seam:** with ``--loop``, the last frame differs from the first

    python check_video.py demo.html
    python check_video.py demo.html --srt voice.srt --narration narration.json
    python check_video.py loop.html --loop
    python check_video.py webgl.html --chromium-arg=--use-gl=swiftshader \
        --chromium-arg=--enable-unsafe-swiftshader

Exits 1 when anything fails, so it can gate a build.
"""

import argparse
import asyncio
import json
import pathlib
import re
import sys

PROBE = r"""([minFont, gap]) => {
  const isHidden = cs => cs.display === 'none' || cs.visibility === 'hidden';
  const opacity = el => {
    let o = 1;
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (isHidden(cs)) return 0;
      o *= parseFloat(cs.opacity);
    }
    return o;
  };
  // the visible part of an element: its box cut by every clipping ancestor
  const clipOf = el => {
    let c = {l: 0, t: 0, r: innerWidth, b: innerHeight};
    for (let e = el.parentElement; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (/(hidden|clip|auto|scroll)/.test(cs.overflow + cs.overflowX + cs.overflowY)) {
        const r = e.getBoundingClientRect();
        c = {l: Math.max(c.l, r.left), t: Math.max(c.t, r.top),
             r: Math.min(c.r, r.right), b: Math.min(c.b, r.bottom)};
      }
    }
    return c;
  };
  const cut = (r, c) => ({l: Math.max(r.left ?? r.l, c.l), t: Math.max(r.top ?? r.t, c.t),
                          r: Math.min(r.right ?? r.r, c.r), b: Math.min(r.bottom ?? r.b, c.b)});
  const area = r => Math.max(0, r.r - r.l) * Math.max(0, r.b - r.t);
  const meet = (a, b) => area({l: Math.max(a.l, b.l), t: Math.max(a.t, b.t),
                               r: Math.min(a.r, b.r), b: Math.min(a.b, b.b)});
  const name = el => {
    const text = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
    const tag = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
      + (el.classList[0] ? '.' + el.classList[0] : '');
    return text ? `${tag} "${text}"` : tag;
  };

  const texts = new Map();
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    const node = walk.currentNode, el = node.parentElement;
    if (!node.textContent.trim() || !el || /^(SCRIPT|STYLE|TITLE)$/.test(el.tagName)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1);
    if (rects.length) texts.set(el, (texts.get(el) || []).concat(rects));
  }
  const items = [];
  for (const [el, rects] of texts) {
    if (opacity(el) < 0.05) continue;
    const clip = clipOf(el);
    const shown = rects.map(r => cut(r, clip)).filter(r => area(r) > 0);
    const full = rects.reduce((s, r) => s + r.width * r.height, 0);
    items.push({el, shown, full, seen: shown.reduce((s, r) => s + area(r), 0),
                size: parseFloat(getComputedStyle(el).fontSize)});
  }
  const pictures = [...document.querySelectorAll('img, canvas, video, svg')]
    // a full-bleed background marked data-background is meant to sit under text
    .filter(e => !e.parentElement?.closest('svg') && !e.hasAttribute('data-background')
                 && opacity(e) >= 0.05)
    .map(e => ({el: e, r: cut(e.getBoundingClientRect(), clipOf(e))}))
    .filter(p => area(p.r) > 0);

  // painted boxes: anything with a visible background or border
  const painted = el => {
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor.match(/[\d.]+/g) || [];
    const alpha = bg.length === 4 ? parseFloat(bg[3]) : (bg.length === 3 ? 1 : 0);
    return alpha > 0.3 || parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderLeftWidth) > 0;
  };
  const stage = document.body.firstElementChild;
  const boxes = [...document.body.querySelectorAll('*')]
    .filter(e => e !== stage && !/^(SCRIPT|STYLE|CANVAS|IMG|VIDEO)$/.test(e.tagName)
                 && !e.closest('svg')
                 && painted(e) && opacity(e) >= 0.05)
    .map(e => ({el: e, r: cut(e.getBoundingClientRect(), clipOf(e))}))
    .filter(b => area(b.r) > 0 && area(b.r) < 0.5 * innerWidth * innerHeight);
  const grow = (r, g) => ({l: r.l - g, t: r.t - g, r: r.r + g, b: r.b + g});
  const related = (a, b) => a.contains(b) || b.contains(a);

  const issues = [];
  for (const it of items) {
    if (it.full - it.seen > 0.03 * it.full && it.full - it.seen > 40)
      issues.push(['clipped', name(it.el)]);
    if (it.seen > 0 && it.size < minFont) issues.push(['small', `${name(it.el)} at ${it.size}px`]);
    for (const p of pictures) {
      if (p.el.contains(it.el) || it.el.closest('svg') === p.el) continue;
      const hit = it.shown.reduce((s, r) => s + meet(r, p.r), 0);
      if (hit > 40) issues.push(['covers', `${name(it.el)} over ${name(p.el)}`]);
    }
  }
  for (const it of items) for (const bx of boxes) {
    if (related(it.el, bx.el)) continue;
    const over = it.shown.reduce((s, r) => s + meet(r, bx.r), 0);
    if (over > 40) { issues.push(['covers', `${name(it.el)} over ${name(bx.el)}`]); continue; }
    // connectors (→, ·) sit close on purpose
    if ((it.el.textContent || '').trim().length <= 2) continue;
    const near = it.shown.reduce((s, r) => s + meet(grow(r, gap), bx.r), 0);
    if (near > 0) issues.push(['crowded', `${name(it.el)} within ${gap}px of ${name(bx.el)}`]);
  }
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
    const a = items[i], b = items[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    let hit = 0;
    for (const ra of a.shown) for (const rb of b.shown) hit += meet(ra, rb);
    if (hit > 40 && hit > 0.02 * Math.min(a.seen, b.seen))
      issues.push(['overlap', `${name(a.el)} / ${name(b.el)}`]);
  }
  return issues;
}"""


def ranges(times, step):
    """Collapse sample times into 'a-b s' spans."""
    spans, start, last = [], None, None
    for t in sorted(times):
        if start is None:
            start = last = t
        elif t - last > step * 1.5:
            spans.append((start, last))
            start = last = t
        else:
            last = t
    if start is not None:
        spans.append((start, last))
    return ", ".join(f"{a:.2f}s" if a == b else f"{a:.2f}-{b:.2f}s" for a, b in spans)


def srt_cues(path):
    blocks = re.split(r"\n\s*\n", pathlib.Path(path).read_text().strip())
    return [" ".join(b.splitlines()[2:]).strip() for b in blocks if len(b.splitlines()) >= 3]


def check_captions(srt, narration):
    def words(s):
        return re.sub(r"\s+", " ", s).strip()

    lines = json.loads(pathlib.Path(narration).read_text())["lines"]
    if all("t" in line for line in lines):
        lines = sorted(lines, key=lambda line: line["t"])
    spoken = [line["text"] for line in lines]
    cues = srt_cues(srt)
    problems = []
    if len(cues) != len(spoken):
        problems.append(f"{len(cues)} caption cues for {len(spoken)} narration lines")
    for k, (cue, line) in enumerate(zip(cues, spoken), start=1):
        if words(cue) != words(line):
            problems.append(f"cue {k} reads {cue!r}, narration says {line!r}")
    return problems


async def check_page(args):
    from playwright.async_api import async_playwright

    w, h = (int(v) for v in args.size.lower().split("x"))
    found, errors = {}, []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=args.chromium_arg or [])
        page = await browser.new_page(viewport={"width": w, "height": h})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(pathlib.Path(args.html).resolve().as_uri())
        duration = await page.evaluate("window.duration")
        n = int(duration / args.step)
        times = [round(k * args.step, 3) for k in range(n + 1) if k * args.step < duration]
        times.append(round(duration - 1 / 30, 3))
        for t in times:
            await page.evaluate("t => window.seek(t)", t)
            for kind, what in await page.evaluate(PROBE, [args.min_font, args.gap]):
                found.setdefault((kind, what), []).append(t)
        seam = None
        if args.loop:
            await page.evaluate("t => window.seek(t)", 0)
            first = await page.screenshot()
            await page.evaluate("t => window.seek(t)", duration)
            seam = first != await page.screenshot()
        await browser.close()
    return found, errors, seam


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("html", help="video HTML with window.duration and window.seek(t)")
    parser.add_argument("--size", default="1920x1080", help="stage size, WxH")
    parser.add_argument("--step", type=float, default=0.25, help="seconds between checked frames")
    parser.add_argument(
        "--min-font", type=float, default=24, help="smallest allowed font size in px"
    )
    parser.add_argument(
        "--gap", type=float, default=24, help="closest text may come to another element's box, px"
    )
    parser.add_argument("--srt", help="captions to compare with --narration")
    parser.add_argument("--narration", help="narration spec the captions must match")
    parser.add_argument(
        "--loop", action="store_true", help="the video loops: last frame must equal first"
    )
    parser.add_argument(
        "--chromium-arg",
        action="append",
        help="extra Chromium flag, repeatable (e.g. --use-gl=swiftshader for WebGL pages)",
    )
    args = parser.parse_args()

    found, errors, seam = asyncio.run(check_page(args))
    failures = 0
    for e in dict.fromkeys(errors):
        print(f"error: {e}")
        failures += 1
    order = ["overlap", "covers", "crowded", "clipped", "small"]
    for (kind, what), times in sorted(
        found.items(), key=lambda kv: (order.index(kv[0][0]), min(kv[1]))
    ):
        print(f"{kind}: {what}  [{ranges(times, args.step)}]")
        failures += 1
    if args.srt and args.narration:
        for problem in check_captions(args.srt, args.narration):
            print(f"captions: {problem}")
            failures += 1
    if seam:
        print("seam: the last frame differs from the first")
        failures += 1
    print(f"{failures} problem(s)" if failures else "ok: no problems found")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
