"""Thin ffmpeg wrappers for measuring loudness and writing WAVs.

Everything that decides how loud the output is goes through ffmpeg's own
filters (``ebur128``, ``loudnorm``, ``alimiter``, ``sidechaincompress``), so
the scripts here only write the notes. Output is bit-exact for a given ffmpeg
version (``+bitexact``), which is what lets the scripts promise the same file
for the same arguments.
"""

import json
import pathlib
import re
import shutil
import subprocess
import wave

import numpy as np

SR = 48_000
BITEXACT = ["-fflags", "+bitexact", "-flags:a", "+bitexact"]


def ffmpeg(*args):
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required (the video export already needs it)")
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True
    )
    if result.returncode:
        raise SystemExit(f"ffmpeg failed:\n{result.stderr[-2000:]}")
    return result.stderr


def write_wav(path, x):
    """Write float audio (mono or stereo, about -1..1) as 16-bit stereo."""
    x = x if x.ndim == 2 else np.stack([x, x], 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def measure(path):
    """EBU R128 scan: integrated LUFS, true peak, and per-100 ms M and S."""
    log = ffmpeg(
        "-v",
        "verbose",
        "-i",
        str(path),
        "-filter_complex",
        "ebur128=peak=true:framelog=verbose",
        "-f",
        "null",
        "-",
    )
    frames = re.findall(
        r" t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)\s+S:\s*(-?[\d.]+|-inf)", log
    )
    t, m, s = (np.array([float(v.replace("-inf", "-120")) for v in col]) for col in zip(*frames))
    summary = log[log.rfind("Summary:") :]
    integrated = float(re.search(r"I:\s*(-?[\d.]+) LUFS", summary).group(1))
    peak = float(
        re.search(r"Peak:\s*(-?[\d.]+|-inf) dBFS", summary).group(1).replace("-inf", "-120")
    )
    return {"t": t, "momentary": m, "short_term": s, "integrated": integrated, "true_peak": peak}


def loudest_moment(path):
    """Loudest 400 ms in LUFS, padding with silence so a 30 ms tap still measures."""
    padded = pathlib.Path(str(path) + ".pad.wav")
    ffmpeg("-i", str(path), "-af", "apad=pad_dur=1", *BITEXACT, str(padded))
    try:
        return float(measure(padded)["momentary"].max())
    finally:
        padded.unlink(missing_ok=True)


def level_short_sound(src, dst, loudness, ceiling_db=-1.5):
    """Set a short sound's loudest 400 ms to ``loudness`` LUFS, then limit its peaks."""
    gain = loudness - loudest_moment(src)
    limit = 10 ** (ceiling_db / 20)
    ffmpeg(
        "-i",
        str(src),
        "-af",
        f"volume={gain:.3f}dB,alimiter=limit={limit:.4f}:level=false",
        *BITEXACT,
        str(dst),
    )


def _loudnorm_stats(args, graph, base):
    log = ffmpeg(*args, "-filter_complex", graph + base + ":print_format=json", "-f", "null", "-")
    return json.loads(log[log.rfind("{") : log.rfind("}") + 1])


def loudnorm(dst, target, filter_complex, inputs, ceiling_db=-1.5):
    """Normalize a mix to ``target`` LUFS with a true-peak ceiling, without pumping.

    ``filter_complex`` must end in ``[pre]``. Three passes: measure, then bring
    the mix to the target with ``alimiter`` catching the peaks that gain pushes
    over, then a measured, linear ``loudnorm`` for the exact level and true peak.
    Limiting first is what keeps ``loudnorm`` in linear mode; its dynamic
    fallback rides the gain and makes quiet passages swell. Returns the
    normalization type ffmpeg reports, ``"linear"`` when all went to plan.
    """
    base = f"loudnorm=I={target}:TP={ceiling_db}:LRA=20"
    args = [a for path in inputs for a in ("-i", str(path))]
    first = _loudnorm_stats(args, filter_complex + ";[pre]", base)
    gain = target - float(first["input_i"])
    limit = 10 ** ((ceiling_db - 1) / 20)
    graph = filter_complex + f";[pre]volume={gain:.3f}dB,alimiter=limit={limit:.4f}:level=false,"
    m = _loudnorm_stats(args, graph, base)
    second = (
        f"{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
        f":offset={m['target_offset']}:linear=true:print_format=json"
    )
    log = ffmpeg(*args, "-filter_complex", graph + second + ",aresample=48000", *BITEXACT, str(dst))
    applied = json.loads(log[log.rfind("{") : log.rfind("}") + 1])
    return applied.get("normalization_type", "")
