# Making a Demo Video

A short clip for YouTube, LinkedIn or X that shows one HoloViz feature or
release, or teases a blog post. The video is one self-contained HTML file whose
frames are a pure function of time, and a recorder gets the same MP4 every run.
These are defaults, not a template.

## Contents

- [Purpose: demo or teaser](#purpose-demo-or-teaser)
- [Long-form: briefings and comparisons](#long-form-briefings-and-comparisons)
- [Workflow: beat sheet before the file](#workflow-beat-sheet-before-the-file)
- [Story](#story)
- [Pacing](#pacing)
- [Facts only](#facts-only)
- [Style](#style)
- [Real footage](#real-footage)
- [Concept shots: SVG, Canvas, WebGL](#concept-shots-svg-canvas-webgl)
- [The HTML contract](#the-html-contract)
- [Checking frames](#checking-frames)
- [Exporting to MP4](#exporting-to-mp4)
- [Revisions](#revisions)

Voice, captions, music and sound effects are in
[Adding Voice and Music](adding-voice-and-music.md).

## Purpose: demo or teaser

Settle this first: the story and the ending differ. When the source is a blog
post, ask, because reviewers read a promotional teaser as an ad.

- **Feature demo:** sells one feature or release and ends on the install
  command and the URL.
- **Blog teaser:** sells the post's idea. It opens with the post's title and
  subtitle, reuses the post's own examples, and mentions the tool once, near
  the end. Draft links stay out of the video; the link goes in the caption.

## Long-form: briefings and comparisons

A walkthrough for a team review or a customer call, or a comparison of several
builds, can run 2–5 minutes. The length changes the structure, not the rules
for each screen.

- **A contents screen** right after the title lists each part with its start
  time, and a numbered chapter card opens each part under the same name. Add
  them past about 90 s or with three or more parts; a single story under that
  needs neither.
- **Keep the times in sync.** Retiming or inserting a screen moves every later
  start time, so update the contents screen in the same pass.
- **YouTube chapters:** put the same timestamps in the description, the first
  at `0:00`, at least three of them, each chapter 10 s or longer.
- **End on what the audience decides:** open questions for an internal review,
  next steps for a customer, instead of an install command.
- **Road bumps** (what broke, the fix, the lesson) suit an internal review. For
  a customer, keep the lesson and drop the bumps.
- **Pacing:** a new screen every 8–15 s, and a caption the viewer reads one at
  a time can hold for 2–3 s.

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
  of your codebase"), with its install command.
- **Close:** a reason, not an instruction. "Read the full post" gets ignored;
  "The full post covers 8 pitfalls and their fixes" says why.

Each headline is a plain statement the viewer can check against the picture.
Avoid garden paths: "You pay tokens for every line an agent reads…" opens
like a feature and turns into a warning, and at feed speed nobody rereads.

- **Introduce before you use.** Anything new on screen (a made-up company, a
  second environment, a term) gets one line on why it's there before it
  appears.
- **Plain words for a general audience.** Replace internal codes with words
  ("P1" becomes "fix now", `env_a` becomes "Company A") and keep product names
  as small labels. When a real screen still shows the codes, add a legend.
- **Frame a test as "expected"**, not "right", so a picture of the target
  doesn't read as a result.

## Pacing

Keep attention with a steady rhythm of new screens, each held long enough to
take in.

- **Under about 40 s**, with a new screen every 5–8 s: about a second to
  animate in, then a hold.
- **Reveal at once.** Highlight every flagged line together; a staggered
  reveal of ten items asks the viewer to track ten things. That holds for
  lists. When the viewer has to keep two cases apart (Company A, then Company
  B), show the first in full before the second appears.
- **Too fast means too much.** When reviewers can't keep up, cut a screen or a
  detail. Half speed doubles the length and the video is still dense.
- A screen with a simple message can hold for less.
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
- **Measure comparisons equally.** Run every option the same number of times
  with the same checks, and put the sample size on screen ("3 runs per
  company"). One run against three isn't an accuracy difference.
- **Quote aggregates over one capture.** When a screenshot's own figures differ
  from the eval's means, quote the means.
- Run on-screen copy through the [deslop skill](../deslop/SKILL.md). Short
  lines hide slop poorly.

## Style

Feeds autoplay without sound, and the video has to read muted. Add audio only
when asked, as a pass after the silent cut ([Adding Voice and Music](adding-voice-and-music.md)).

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

## Real footage

When the demo is about something on screen (a Panel app, a widget, an
interactive plot), show the real thing instead of redrawing it. Footage of the
actual app is its own proof.

**Write a shot list before opening the browser.** One line per scene: the
claim it makes, the screenshot that proves it, and whether the claim holds for
this audience. For a customer, ask it against what they already have (an
existing eval tool, guardrails already in place): a "before" shot where the
model refuses anyway, or "no redeploy" when the app isn't wired up yet, fails
on paper and costs a re-shoot once captured.

Capture it with Playwright when it's available. Serve the app, drive it with
the same steps a user would take, and take a screenshot after each step:

```python
import subprocess, time
from playwright.sync_api import sync_playwright

server = subprocess.Popen(["panel", "serve", "app.py", "--port", "5006"])
time.sleep(3)  # or poll the port until it answers
try:
    with sync_playwright() as p:
        page = p.chromium.launch().new_page(
            viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        page.goto("http://localhost:5006/app")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="step0.png")
        page.get_by_text("Run").click()          # each step the demo shows
        page.wait_for_load_state("networkidle")
        page.screenshot(path="step1.png")
finally:
    server.terminate()
```

- **Stills over a screen recording.** One screenshot per state, embedded as
  `data:` URIs and crossfaded or zoomed as a function of `t`, keeps the video
  deterministic and small. Playwright's `record_video_dir` captures in real
  time, and its timing depends on the machine. If you need continuous motion
  (a slider sweep), embed the clip and set `video.currentTime` in `seek`,
  awaiting the `seeked` event before returning.
- **Make the app repeatable:** seeded or fixed data, a fixed viewport, and a
  wait for the app to settle (`networkidle`, or a selector the app renders
  once it's ready) before each screenshot.
- **Serve with `--dev` from the start** (`panel serve app.py --dev`), so edits
  reload without restarting the server between captures.
- **Click by locator** (`get_by_role`, `get_by_text`), never by screen
  coordinates, which shift when the zoom or viewport changes.
- **Move the mouse away before each shot** (`page.mouse.move(0, 0)`), or the
  last click leaves hover styles and tooltips in the frame.
- **Save straight into the project** (for example `footage/`). If the capture
  tool writes somewhere your file tools can't read, change its save folder
  before the first capture instead of asking the user to copy each batch.
- The page shows no cursor. Draw one in the HTML, moving as a function of `t`
  toward the element that changes, so the viewer knows where the click
  happened.
- Crop to the part of the app that changes, and capture at
  `device_scale_factor=2`. A full-window screenshot shrunk into a 1080 px frame
  makes UI text unreadable at feed size.
- **Take close-ups at full scale** with `page.screenshot(clip=...)`, not by
  zooming the browser out or capturing at a reduced scale: the saved file keeps
  the scale it was taken at, and upscaling it later blurs the text.
- If Playwright can't run, ask the user for screenshots or a screen recording
  of the app. Don't fake the UI with drawn rectangles and call it the app.
- **Walk through a screenshot that is the subject.** Zoom to one region at a
  time with a highlight and one caption, instead of showing the whole screen
  and moving on.
- **Screenshots match the numbers.** Capture from the same code and run as
  every figure on screen, note each capture's run ID and time, and recapture
  after any fix. Keep an older capture only where it is the evidence for the
  old behavior.

## Concept shots: SVG, Canvas, WebGL

When there's no footage yet, or the subject is an idea rather than a screen
("Datashader counts points per pixel"), abstract motion is the picture. It
shows the idea and never stands in for the product's UI, and the headline
still carries the claim, since a muted viewer can't decode a metaphor without
it. Replace it with real footage once that exists.

| Use | When | Cost |
|---|---|---|
| SVG | the default: diagrams, outlines, morphing shapes, kinetic type | holds are skipped when recording; text stays checkable |
| Canvas 2D | thousands of points or particles | every frame is screenshotted; text drawn in it can't be checked |
| WebGL | shaders, colour ramps over a grid, 3D | pin versions, `preserveDrawingBuffer: true`; headless output can differ from your screen, so check stills |

- **Same contract:** every particle and uniform comes from `t` and a seeded
  random generator; generate data once at load, never per frame.
- **One shape, never cut.** Carry one thing through the whole video (points
  that become a grid, then counts, then a coloured image) instead of cutting
  between unrelated pictures, and make the claim visible in it: if the
  headline says points hide each other, the overplotted points must actually
  hide the structure.
- **Text stays in the DOM** over the canvas, so the checks still apply; mark
  full-bleed canvases and outline SVGs `data-background` so text over them
  isn't reported.
- **A flat vector look works for concept videos:** deep navy sky with slow,
  twinkling stars, one saturated palette shared by the 2D canvas and the
  shader, rounded tiles and pills, flat drop shadows, and reveals with a
  slight overshoot (`easeOutBack`). Take the style, not another studio's
  characters or branding.
- **Headless sandboxes** without a GPU render WebGL with
  `--use-gl=swiftshader --enable-unsafe-swiftshader`; pass each to
  `check_video.py` and `record_video.py` as `--chromium-arg=<flag>`.

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

Check after every edit, not once before export: a fix on one screen often
breaks its neighbour, and the user shouldn't be the one who finds it.

1. Grep the file for the banned APIs.
2. Run [`scripts/check_video.py`](scripts/check_video.py) on the page (and on
   the burned-caption page, with `--srt` and `--narration`). It seeks the
   whole timeline and reports, as time ranges, console errors, text over
   text, text over an image, canvas, SVG or a card, text within 24 px of a
   box it doesn't belong to, clipped and undersized text, and captions whose
   words differ from the narration; it exits 1 on any of them. It can't see
   text drawn inside a canvas, judge a message, or catch a shape crossing
   text, so the stills below are still needed.
3. Screenshot each scene's settled frame (just before it fades out) and a
   few mid-transition frames in every orientation you deliver, then look at
   the images yourself. Check the layout:
   - unplanned wraps, and a headline running into the picture;
   - text crossing a shape's outline, such as a label sitting on a Venn
     circle's stroke, or text spilling out of the region it belongs to;
   - chips, boxes or labels touching their neighbours, and anything clipped
     at the stage edge;
   - collisions with the corner label, the draft tag and the progress bar;
   - a moving element (a packet, a cursor) passing over text;
   - text that leaves before it can be read.
4. Read each still as the target viewer, with the sound off. Check the
   message:
   - can they say what the screen claims without the narration?
   - would the audience know every term? An account executive doesn't know
     CI/CD or lock files; say what it does for the customer instead;
   - does a label imply something false? An axis titled "codes without AI
     help" next to a Conda chip says Conda writes code;
   - is every claim in the sources? Flag commercial claims (licensing,
     pricing) for the user to confirm.
5. If the recorder's machine lacks the intended font, check the longest
   headline's wrap there too.
6. After fixing, re-run the check and re-shoot the same frames before moving on, and repeat until
   a pass finds nothing. Show the user a contact sheet of the settled frames
   with each cut.

Playwright takes these screenshots the same way it records the MP4: call
`seek(t)`, then `page.screenshot()`. A contact sheet (several frames scaled
into one image) reviews a whole video at once. Without Playwright, use the
session's preview tool and say which frames you couldn't check.

## Exporting to MP4

Record with [`scripts/record_video.py`](scripts/record_video.py), which drives
`seek(t)` in headless Chromium and pipes frames to ffmpeg:

```bash
python scripts/record_video.py demo.html --out demo.mp4
python scripts/record_video.py demo.html --out demo.mp4 --audio mix.wav --srt captions.srt
python scripts/record_video.py vertical.html --size 1080x1920 --out vertical.mp4
```

It splits the timeline across parallel browser pages and reuses the last
screenshot while nothing changes, so held screens cost nothing. A bottom
progress bar (`#progress`, `#bar` or `[data-progress]`) is hidden in the page
and drawn by ffmpeg, since it would otherwise change every frame. The output
is H.264, `yuv420p`, `+faststart`, which uploads cleanly to YouTube, LinkedIn
and X.

- **Expose `window.frameKey(t)`** on any page with a canvas or WebGL: a string
  of every value the frame is drawn from, rounded to what changes pixels.
  Without it the recorder can't see inside a canvas and screenshots every
  frame. Build it from the same inputs `render(t)` uses, leave out the
  progress bar, and step anything that drifts constantly (twinkling stars) at
  a few updates a second so held scenes repeat. On the Datashader concept
  video this halved the screenshots, with pixel-identical output.
- **`--burn-captions out.mp4`** renders each caption cue once as a transparent
  image (the page's `#caption`, with `?captions=1`) and overlays them on the
  plain cut with ffmpeg, fading like the page does, instead of recording the
  video a second time.
- **Render music and frames at the same time;** both need only the voice's
  timeline. Together these took a full rebuild from about 2.7 minutes to
  70 s.
- **Estimate the render before starting it.** Frames are duration × fps (95 s
  at 30 fps is 2,850). A one-CPU sandbox with a per-command time limit may not
  finish a video past about 60 s, so hand the command to the user's machine
  instead. When a render runs in the background, check its process or the
  growing output file; a `sleep` returning says nothing about the recorder.

**No headless browser?** Say so, and don't silently switch renderers. The
fallback that holds up is one scene description (draw ops per element, plus
each element's opacity, offset and scale per frame) feeding both a Python
renderer (PIL piped to ffmpeg) for the MP4 and an HTML canvas that replays the
same states for `seek(t)`. Neither has its own timeline, and the two can't
drift. Nimbus Sans and DejaVu Sans Mono share metrics with Helvetica and Menlo,
which keeps line breaks the same as in the browser. Show the user stills first.

## Revisions

- Keep output filenames the same across revisions. Links in drafts and threads
  then point at the latest cut.
- Conflicting feedback often has one cause: "slower" and "under 40 s" both
  mean too much on each screen, and cutting material satisfies both.
