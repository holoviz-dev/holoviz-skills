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
  - [Real footage](#real-footage)
  - [The HTML contract](#the-html-contract)
  - [Checking frames](#checking-frames)
  - [Exporting to MP4](#exporting-to-mp4)
  - [Generated sound effects](#generated-sound-effects)
  - [Generated music](#generated-music)
    - [Loudness](#loudness)
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
  of your codebase"), with its install command.
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
- **Reveal at once.** Highlight every flagged line together; a staggered
  reveal of ten items asks the viewer to track ten things.
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

## Real footage

When the demo is about something on screen (a Panel app, a widget, an
interactive plot), show the real thing instead of redrawing it. Footage of the
actual app is its own proof.

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
- The page shows no cursor. Draw one in the HTML, moving as a function of `t`
  toward the element that changes, so the viewer knows where the click
  happened.
- Crop to the part of the app that changes, and capture at
  `device_scale_factor=2`. A full-window screenshot shrunk into a 1080 px frame
  makes UI text unreadable at feed size.
- If Playwright can't run, ask the user for screenshots or a screen recording
  of the app. Don't fake the UI with drawn rectangles and call it the app.

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
2. Screenshot each scene's settled frame (just before it fades out) and a
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
3. Read each still as the target viewer, with the sound off. Check the
   message:
   - can they say what the screen claims without the narration?
   - would the audience know every term? An account executive doesn't know
     CI/CD or lock files; say what it does for the customer instead;
   - does a label imply something false? An axis titled "codes without AI
     help" next to a Conda chip says Conda writes code;
   - is every claim in the sources? Flag commercial claims (licensing,
     pricing) for the user to confirm.
4. If the recorder's machine lacks the intended font, check the longest
   headline's wrap there too.
5. After fixing, re-shoot the same frames before moving on, and repeat until
   a pass finds nothing. Show the user a contact sheet of the settled frames
   with each cut.

Playwright takes these screenshots the same way it records the MP4: call
`seek(t)`, then `page.screenshot()`. A contact sheet (several frames scaled
into one image) reviews a whole video at once. Without Playwright, use the
session's preview tool and say which frames you couldn't check.

Re-render only the frames of scenes that changed: render frames to numbered
images, then encode them in one ffmpeg pass. Splitting the frame range across
a few parallel Playwright processes keeps each command inside a sandbox's
time limit on long videos.

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

**Music,** if asked: generate a score that follows the video (see
[Generated music](#generated-music)). You can't hear it, so the user has to
check it; if they'd rather have a produced track, a platform library track
(LinkedIn, YouTube) avoids licensing questions. Keep it around −16 to −20
LUFS.

## Generated sound effects

When the user asks for sound, generate effects with
[`scripts/make_sfx.py`](scripts/make_sfx.py) rather than downloading them.
They're original, carry the repository's license and need no credit, and the
script writes the same WAV for the same arguments, so commit the script call,
not the audio.

```bash
python scripts/make_sfx.py --list                 # names and what each is for
python scripts/make_sfx.py --out sfx/             # every sound + all-sounds.wav
python scripts/make_sfx.py bubble --pitch -2      # retune after feedback
```

- **Each effect marks an event already on screen** (a box appearing, a token
  landing), timed to that frame. Sound never carries meaning the picture
  doesn't, since feeds autoplay muted.
- **Cue them from the timeline.** Keep a list of `(sound, t, gain)` built from
  the same named times the animation uses, and mix it with ffmpeg at export.
  The audio then shares one clock with `seek(t)` and can't drift.
- **You can't hear the output.** Hand the user `all-sounds.wav` first and
  change parameters from their words ("softer", "lower"); don't describe a
  sound as pleasant.

## Generated music

Write a score spec from the beat sheet and render it with
[`scripts/make_music.py`](scripts/make_music.py). The music is unique to the
video because it's built from the video's own timeline, and it's original, so
it carries the repository's license like the sound effects. Commit the spec
next to the HTML, not the WAV.

```bash
python scripts/make_music.py --example > score.json   # start from the example
python scripts/make_music.py score.json --out music.wav
```

The script prints the loudness of each section and warns when a section
doesn't start on a bar line. Map the video to the spec like this:

- **Tempo from the beat sheet.** Pick `bpm` so every section time lands on a
  bar line, and fix any warning by changing the tempo, not the picture's
  times. Beats every 10–14 s with times on even seconds fit 120 BPM with
  `"feel": "half"` (it reads as a relaxed 60).
- **One `section` per beat-sheet change,** with `t` from the same named times
  the animation uses.
- **A motif per concept** in `motifs` (scale degrees, or `"pulse"` for a low
  repeating root), added to `layers` from the section where that concept
  first appears on screen. Progressive disclosure on screen becomes the
  arrangement building up.
- **The payoff gets `"layers": "all"`, `"swell": true` and a few dB of
  `gain`,** so it's the first time the full arrangement plays and the loudest
  section in the printout. Keep the opening quiet with a negative `gain`.
- **The close gets `"resolve": true`,** which holds the tonic under the final
  card while the music fades over the last 3 s.
- **`hits`** are `[sound, t, LU]` from `make_sfx.py`, at the frames of
  on-screen events. The number is how far above the music just before the
  hit it lands (default 3, capped at 6), and the music ducks under each one.
- **Mood picks `key`, `mode` and `texture`.** Explainers suit major or
  `lydian` with `texture` around 0.5 (tape wobble, warm filter, vinyl
  crackle); a launch demo suits `major` or `mixolydian` with less texture.
- Change `seed` for a different take with the same structure.

Hand the user the WAV with the section printout and change the spec from their
words; you can't judge whether it sounds good.

### Loudness

Both scripts master their output through `scripts/_mastering.py`, so nothing
they write clips or startles: a sudden loud moment is the fastest way to make
a viewer scroll away or reach for the volume.

- **Peaks stay under −1.5 dBFS.** A look-ahead limiter holds every sample
  under the ceiling, with headroom for the MP4 encoder.
- **The music is set by loudness, not peak:** `loudness` in the spec
  (default −20 LUFS integrated), inside the −16 to −20 range for a bed
  under a video. Sound effects are each levelled to the same loudness
  (`--loudness`, default −16 LUFS for their loudest 400 ms), so a short tap
  and a long chime sound equally loud.
- **Layers fade in over their first bars**, so a new instrument doesn't
  arrive at full level.
- **`make_music.py` warns** when the music gets more than 6 LU louder within
  3 s, or the loudest moment is more than 10 LU above the average. Fix the
  spec (add layers more gradually, lower a section's `gain` or a hit) until
  the warnings are gone; don't hand over a score that still prints one.

## Revisions

- Keep output filenames the same across revisions. Links in drafts and threads
  then point at the latest cut.
- Conflicting feedback often has one cause: "slower" and "under 40 s" both
  mean too much on each screen, and cutting material satisfies both.
