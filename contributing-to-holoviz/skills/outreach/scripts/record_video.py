"""Record a demo video HTML file to MP4 by calling its ``window.seek(t)``.

Frames are pure functions of ``t``, so the page can be recorded in pieces and
in parallel. A frame that's unchanged from the one before (a hold) reuses the
previous screenshot. The page says what changed in one of two ways:

- ``window.frameKey(t)``, if defined: a string of every value the frame is
  drawn from. This works for canvas and WebGL pages too.
- otherwise the page's HTML, which only sees DOM changes, so pages with a
  ``<canvas>`` or ``<video>`` and no ``frameKey`` are screenshotted every frame.

A progress bar, which changes every frame, is hidden in the page and drawn by
ffmpeg instead. Burned-in captions are rendered once per cue as transparent
images and overlaid with ffmpeg, rather than recording the whole video again.

    python record_video.py demo.html --out demo.mp4
    python record_video.py demo.html --out demo.mp4 --audio mix.wav --srt captions.srt
    python record_video.py demo.html --out demo.mp4 --burn-captions demo-captioned.mp4
    python record_video.py vertical.html --size 1080x1920 --out vertical.mp4
"""

import argparse
import asyncio
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _ffmpeg  # noqa: E402

PREPARE = """sel => {
  const bar = sel ? document.querySelector(sel) : null;
  let info = null;
  if (bar) {
    const r = bar.getBoundingClientRect(), c = getComputedStyle(bar).backgroundColor;
    info = {color: c, height: Math.round(r.height) || 8,
            bottom: Math.round(innerHeight - r.bottom)};
    bar.style.visibility = 'hidden';
    window.__bar = bar;
  }
  return {bar: info, live: document.querySelector('canvas, video') !== null,
          keyed: typeof window.frameKey === 'function'};
}"""
DOM_STATE = """async t => {
  await window.seek(t);
  // inlined images never change, and comparing megabytes of base64 per frame is slow
  let html = document.documentElement.outerHTML.replace(/(src|href)="data:[^"]*"/g, '');
  return window.__bar ? html.replace(window.__bar.outerHTML, '') : html;
}"""


def hex_color(css):
    nums = [int(float(v)) for v in re.findall(r"[\d.]+", css)[:3]]
    return "0x" + "".join(f"{v:02x}" for v in nums) if len(nums) == 3 else "0x5bb4ea"


def url(args, captions=False):
    uri = pathlib.Path(args.html).resolve().as_uri()
    return uri + ("?captions=1" if captions else "")


async def chunk(browser, args, frames, out, duration, size):
    w, h = size
    page = await browser.new_page(viewport={"width": w, "height": h})
    await page.goto(url(args))
    info = await page.evaluate(PREPARE, args.progress or None)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "image2pipe",
        "-c:v",
        "mjpeg",
        "-r",
        str(args.fps),
        "-i",
        "-",
    ]
    if info["bar"]:
        bar, offset = info["bar"], frames.start / args.fps
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"color=c={hex_color(bar['color'])}:s={w}x{bar['height']}:r={args.fps}",
            "-filter_complex",
            f"[0][1]overlay=x='-w+w*(t+{offset})/{duration}':y=H-h-{bar['bottom']}:shortest=1,format=yuv420p",
        ]
    else:
        cmd += ["-pix_fmt", "yuv420p"]
    cmd += ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    mode = (
        "every"
        if args.every_frame
        else ("key" if info["keyed"] else ("every" if info["live"] else "dom"))
    )
    last, shot, fresh = object(), None, 0
    for i in frames:
        t = i / args.fps
        if mode == "key":
            state = await page.evaluate("t => window.frameKey(t)", t)
            if state != last:
                await page.evaluate("t => window.seek(t)", t)
        elif mode == "dom":
            state = await page.evaluate(DOM_STATE, t)
        else:
            await page.evaluate("t => window.seek(t)", t)
            state = object()
        if state != last:
            shot, last = await page.screenshot(type="jpeg", quality=args.quality), state
            fresh += 1
        await asyncio.to_thread(ff.stdin.write, shot)
    await page.close()
    ff.stdin.close()
    if await asyncio.to_thread(ff.wait):
        raise SystemExit("ffmpeg failed while encoding frames")
    return fresh, mode


async def record(args, video_out):
    from playwright.async_api import async_playwright

    size = tuple(int(v) for v in args.size.lower().split("x"))
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=args.chromium_arg or [])
        probe = await browser.new_page()
        await probe.goto(url(args))
        duration = await probe.evaluate("window.duration")
        await probe.close()
        n = round(duration * args.fps)
        step = -(-n // args.workers)
        ranges = [range(k, min(k + step, n)) for k in range(0, n, step)]
        parts = [video_out.with_suffix(f".part{k}.mp4") for k in range(len(ranges))]
        results = await asyncio.gather(
            *(chunk(browser, args, r, part, duration, size) for r, part in zip(ranges, parts))
        )
        await browser.close()
    listing = video_out.with_suffix(".parts.txt")
    listing.write_text("".join(f"file '{part.resolve()}'\n" for part in parts))
    _ffmpeg.ffmpeg(
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(video_out),
    )
    for path in (*parts, listing):
        path.unlink()
    print(
        f"{n} frames, {sum(f for f, _ in results)} screenshotted "
        f"({results[0][1]} holds), {args.workers} workers"
    )
    return duration


async def caption_images(args, size, workdir):
    """One transparent PNG per caption cue, cut to the caption's box, with its position."""
    from playwright.async_api import async_playwright

    w, h = size
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=args.chromium_arg or [])
        page = await browser.new_page(viewport={"width": w, "height": h})
        await page.goto(url(args, captions=True))
        cues = await page.evaluate("window.CAPTIONS || []")
        sel = args.caption_selector
        for k, cue in enumerate(cues):
            mid = (cue["start"] + cue["end"]) / 2
            await page.evaluate("t => window.seek(t)", mid)
            box = await page.evaluate(
                """sel => {
              const cap = document.querySelector(sel);
              if (!cap) return null;
              // show only the caption: hide every element that neither holds it nor sits inside it
              for (const el of document.querySelectorAll('body *'))
                if (!el.contains(cap) && !cap.contains(el)) el.style.visibility = 'hidden';
              for (let e = cap.parentElement; e; e = e.parentElement)
                e.style.background = 'transparent';
              document.documentElement.style.background = 'transparent';
              cap.style.opacity = 1;
              const r = cap.getBoundingClientRect();
              return {x: Math.floor(r.left), y: Math.floor(r.top),
                      w: Math.ceil(r.width), h: Math.ceil(r.height)};
            }""",
                sel,
            )
            if not box or box["w"] < 2:
                await page.reload()
                continue
            png = workdir / f"cap{k:03d}.png"
            await page.screenshot(
                path=str(png),
                omit_background=True,
                clip={"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]},
            )
            out.append(
                {"png": png, "x": box["x"], "y": box["y"], "start": cue["start"], "end": cue["end"]}
            )
            await page.reload()  # restore what was hidden for the next cue
        await browser.close()
    return out


def burn_captions(args, video, out, size, duration):
    """Overlay the caption images on a recorded video, fading each in and out like the page does."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        caps = asyncio.run(caption_images(args, size, pathlib.Path(tmp)))
        if not caps:
            raise SystemExit(
                "no caption cues found (window.CAPTIONS) or no element matches --caption-selector"
            )
        inputs, chain, last = ["-i", str(video)], [], "0:v"
        fade = args.caption_fade
        for k, c in enumerate(caps, start=1):
            inputs += [
                "-loop",
                "1",
                "-framerate",
                str(args.fps),
                "-t",
                f"{duration:.3f}",
                "-i",
                str(c["png"]),
            ]
            s, e = c["start"], c["end"]
            chain.append(
                f"[{k}:v]format=rgba,fade=t=in:st={s:.3f}:d={fade}:alpha=1,"
                f"fade=t=out:st={max(s, e - fade):.3f}:d={fade}:alpha=1[c{k}]"
            )
            chain.append(
                f"[{last}][c{k}]overlay=x={c['x']}:y={c['y']}:enable='between(t,{s:.3f},{e:.3f})'[v{k}]"
            )
            last = f"v{k}"
        _ffmpeg.ffmpeg(
            *inputs,
            "-filter_complex",
            ";".join(chain),
            "-map",
            f"[{last}]",
            "-c:v",
            "libx264",
            "-preset",
            args.preset,
            "-crf",
            str(args.crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        )
    print(f"burned {len(caps)} captions into {out}")


def mux(video, audio, srt, out):
    args, maps, codecs = ["-i", str(video)], ["-map", "0:v"], ["-c:v", "copy"]
    if audio:
        args += ["-i", str(audio)]
        maps += ["-map", f"{len(args) // 2 - 1}:a"]
        codecs += ["-c:a", "aac", "-b:a", "192k", "-metadata:s:a:0", "language=eng"]
    if srt:
        args += ["-i", str(srt)]
        maps += ["-map", f"{len(args) // 2 - 1}:s"]
        codecs += [
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata:s:s:0",
            "title=English",
            "-disposition:s:0",
            "default",
        ]
    _ffmpeg.ffmpeg(*args, *maps, *codecs, "-movflags", "+faststart", str(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("html", help="video HTML with window.duration and window.seek(t)")
    parser.add_argument("--out", default="demo.mp4", help="output MP4")
    parser.add_argument("--size", default="1920x1080", help="stage size, WxH")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--crf", type=int, default=18, help="x264 quality, lower is better")
    parser.add_argument("--preset", default="veryfast", help="x264 preset")
    parser.add_argument("--quality", type=int, default=92, help="JPEG quality of each screenshot")
    parser.add_argument("--workers", type=int, default=max(2, min(10, (os.cpu_count() or 4) - 2)))
    parser.add_argument(
        "--progress",
        default="#progress, #bar, [data-progress]",
        help="CSS selector of a bottom progress bar to draw in ffmpeg ('' for none)",
    )
    parser.add_argument("--every-frame", action="store_true", help="screenshot every frame")
    parser.add_argument("--audio", help="audio file to mux in")
    parser.add_argument("--srt", help="SRT to embed as a soft caption track")
    parser.add_argument(
        "--burn-captions", help="also write this MP4 with the page's captions burned in"
    )
    parser.add_argument("--caption-selector", default="#caption", help="the page's caption element")
    parser.add_argument(
        "--caption-fade", type=float, default=0.15, help="caption fade in and out, s"
    )
    parser.add_argument("--chromium-arg", action="append", help="extra Chromium flag (repeatable)")
    args = parser.parse_args()
    out = pathlib.Path(args.out)
    size = tuple(int(v) for v in args.size.lower().split("x"))
    video_out = out if not (args.audio or args.srt) else out.with_suffix(".video.mp4")
    duration = asyncio.run(record(args, video_out))
    if args.burn_captions:
        burned = pathlib.Path(args.burn_captions)
        burned_video = burned if not args.audio else burned.with_suffix(".video.mp4")
        burn_captions(args, video_out, burned_video, size, duration)
        if burned_video != burned:
            mux(burned_video, args.audio, args.srt, burned)
            burned_video.unlink()
    if video_out != out:
        mux(video_out, args.audio, args.srt, out)
        video_out.unlink()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
