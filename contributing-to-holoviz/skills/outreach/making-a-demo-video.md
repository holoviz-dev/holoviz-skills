# Making a Demo Video

A short clip for YouTube, LinkedIn or X that shows one HoloViz feature or
release, or teases a blog post. The video is one self-contained HTML file whose
frames are a pure function of time, and a recorder gets the same MP4 every run.
These are defaults, not a template.

## Contents

- [Making a Demo Video](#making-a-demo-video)
  - [Contents](#contents)
  - [Purpose: demo or teaser](#purpose-demo-or-teaser)
  - [Workflow: beat sheet before the file](#workflow-beat-sheet-before-the-file)
  - [Story](#story)
  - [Pacing](#pacing)
  - [Facts only](#facts-only)
  - [Style](#style)
  - [The HTML contract](#the-html-contract)
  - [Checking frames](#checking-frames)
  - [Exporting to MP4](#exporting-to-mp4)
  - [Revisions](#revisions)

## Purpose: demo or teaser

Settle this first: the story and the ending differ. When the source is a blog
post, ask, because reviewers read a promotional teaser as an ad.

- **Feature demo:** sells one feature or release and ends on the install
  command and the URL.
- **Blog teaser:** sells the post's idea. It opens with the post's title and
  subtitle, reuses the post's own examples, and mentions the tool once, near
  the end. Draft links stay out of the video; the link goes in the caption.

## Workflow: beat sheet before the file

Reply first with a **beat sheet and four keyframes only**, and write the file
after the user approves. A story change costs one message now and a rewrite
later.

- **Beat sheet:** time range, label, headline and picture for each screen,
  adding up to the full duration.
- **Keyframes:** rough ASCII layouts of the opening, problem, fix and close.
  They show placement as well as copy.
- **Aspect ratio:** 1920×1080 for YouTube and most LinkedIn posts, 1080×1920
  for Shorts, Reels or vertical. Users often want the other one after a first
  cut. Plan for both.
- Raise open choices (branding, naming a competitor, which API to show) in the
  same reply. One approval then settles them.

## Story

Every screen has a **label** (PROBLEM, FIX, THE SKILL), one **headline** and one
**picture**. The label tells the viewer how to read the headline.

- **Opening (3–5 s):** name the subject in the first frame: the project and a
  one-line promise for a demo, the post's title and subtitle for a teaser.
- **Problem:** the cost, shown on the source's own example and numbers. Call
  it a problem before showing it.
- **Fix:** the same example with only the fix changed.
- **How (demos):** the few lines of real code behind the fix, which keep the
  claim honest.
- **Conclusion:** what the tool does for the viewer ("cleanup keeps slop out
  of your codebase") and its install command.
- **Close:** a reason, not an instruction. "Read the full post" gets ignored;
  "The full post covers 8 pitfalls and their fixes" says why.

Each headline is a plain statement the viewer can check against the picture.
Avoid garden paths: "You pay tokens for every line an agent reads…" opens
like a feature and turns into a warning, and at feed speed nobody rereads.

## Pacing

Keep attention with a steady rhythm of new screens, each held long enough to
take in.

- **Under about 40 s**, with a new screen every 5–8 s: about a second to
  animate in, then a hold.
- **Reveal at once.** Highlight all six phrases together; a staggered reveal
  of ten items asks the viewer to track ten things.
- **Too fast means too much.** When reviewers can't keep up, cut a screen or a
  detail. Half speed doubles the length and the video is still dense.
- A screen with a simple message can hold for less; reviewers watched one at
  1.5x.
- Keep the headline and the picture in the same place on every screen, move
  one thing at a time, and run a thin progress bar along the bottom.

## Facts only

- Every number and claim comes from the source or the project's docs. A count
  the example makes visible ("2 of 5 steps ran") persuades as well as an
  invented "10× faster".
- **Run the tool.** If the video shows a tool's output, run it on the example
  and use what it prints.
- **Counts match the screen.** If the headline says "10 problems", ten things
  are marked under it.
- Check the current API on the project site before writing code (Panel's
  newer docs use `pn.ui.*`). If you can't confirm a name, use the documented
  older one and say so.
- Prefer wording from the project's site, docs or post; it's already been
  reviewed.
- Don't name a competitor unless the source does or the user asks.
- Run on-screen copy through the [deslop skill](../deslop/SKILL.md). Short
  lines hide slop poorly.

## Style

Feeds autoplay without sound, and the video has to read muted. Don't add audio
unless asked.

- **Headlines of about eight words or fewer**, at 72–130 px on a 1080 px-tall
  stage. Check at phone feed size.
- **Code at 30 px or more.** If the snippet doesn't fit, show fewer lines, or
  keep it as texture and put the point in large tags on top ("already in
  utils.py").
- **The project's palette on a flat background**, with one meaning per color
  for the whole video (red = problem, green = fix).
- **Motion that explains:** fades, short slides, highlights, typed commands.
- Keep the project or post name in a corner from the second screen on. Clips
  get shared without the post text.

## The HTML contract

One `.html` file with CSS, JS and data inline and nothing loaded from the
network: recorders and previews often run offline. Use a system font
stack, or embed fonts as `data:` URIs.

- A fixed-size stage (for example 1920×1080 px) scaled to fit the window.
- `window.duration` set to the agreed length, and `async window.seek(t)` that
  awaits `document.fonts.ready` and calls a pure `render(t)`.
- **Every pixel is a function of `t`:** no `Date.now`, `performance.now`,
  `requestAnimationFrame` loop, `setTimeout`, `setInterval`, CSS transitions,
  `@keyframes` or unseeded `Math.random`. A recorder calls `seek` at any time
  in any order.
- `#t=12.5` (or `?t=12.5`) in the URL renders one frame for previews. Some
  previews drop the query string.
- **Keep the timeline apart from the layout**, with one layout table per
  orientation, so vertical is a layout change and not a rewrite.
- **Change speed in one place:** `render(t * speed)` in `seek`, and divide
  `duration` by `speed`.

```js
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ramp = (t, a, b) => clamp((t - a) / (b - a));      // 0→1 over [a, b]
const easeOut = x => 1 - (1 - x) ** 3;
// opacity for an element visible on [a, b) with fade in/out
const win = (t, a, b, fadeIn = 0.4, fadeOut = 0.4) =>
  t < a || t >= b ? 0 : Math.min(easeOut(ramp(t, a, a + fadeIn)), 1 - ramp(t, b - fadeOut, b));

window.duration = 30;
window.seek = async t => { await document.fonts.ready; render(t); };
```

## Checking frames

1. Grep the file for the banned APIs.
2. Screenshot the keyframe times and a few mid-transition frames in every
   orientation you deliver, then look at the images yourself. Check for
   unplanned wraps, a headline running into the picture, overlaps with the
   corner label, and text that leaves before it can be read.
3. If the recorder's machine lacks the intended font, check the longest
   headline's wrap there too.

Playwright takes these screenshots the same way it records the MP4: call
`seek(t)`, then `page.screenshot()`. A contact sheet (several frames scaled
into one image) reviews a whole video at once. Without Playwright, use the
session's preview tool and say which frames you couldn't check.

## Exporting to MP4

Drive `seek` from a headless browser and pipe frames to ffmpeg. Frames are
pure, and rendering slower than real time doesn't change the video.

```python
import asyncio, os, subprocess
from playwright.async_api import async_playwright

W, H, FPS = 1920, 1080, 30

async def record(src="demo.html", out="demo.mp4"):
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "image2pipe", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
         "-movflags", "+faststart", out],
        stdin=subprocess.PIPE,
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H})
        await page.goto(f"file://{os.path.abspath(src)}")
        duration = await page.evaluate("window.duration")
        for i in range(round(duration * FPS)):
            await page.evaluate("t => window.seek(t)", i / FPS)
            ff.stdin.write(await page.screenshot(type="png"))
        await browser.close()
    ff.stdin.close()
    ff.wait()

asyncio.run(record())
```

H.264 with `yuv420p` and `+faststart` uploads cleanly to YouTube, LinkedIn and
X. Set the viewport to the stage size.

**No headless browser?** Say so, and don't silently switch renderers. The
fallback that holds up is one scene description (draw ops per element, plus
each element's opacity, offset and scale per frame) feeding both a Python
renderer (PIL piped to ffmpeg) for the MP4 and an HTML canvas that replays the
same states for `seek(t)`. Neither has its own timeline, and the two can't
drift. Nimbus Sans and DejaVu Sans Mono share metrics with Helvetica and Menlo,
which keeps line breaks the same as in the browser. Show the user stills first.

**Music,** if asked: you can't hear what you generate, and the user has to
check it. A platform library track (LinkedIn, YouTube) usually fits better and
avoids licensing questions. Keep it around −16 to −20 LUFS.

## Revisions

- Keep output filenames the same across revisions. Links in drafts and threads
  then point at the latest cut.
- Conflicting feedback often has one cause: "slower" and "under 40 s" both
  mean too much on each screen, and cutting material satisfies both.
