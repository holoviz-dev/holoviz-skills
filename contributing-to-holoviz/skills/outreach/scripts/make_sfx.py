"""Generate original UI sound effects for HoloViz demo and explainer videos.

Deterministic for a given ffmpeg version: the same arguments always write the
same WAV, so commit this script, not the audio. Numpy writes the sounds and
ffmpeg levels each to the same loudness under a -1.5 dBFS peak ceiling, so
none clips or startles. The sounds are synthesized here, so they carry the
repository's license and need no SOURCES.md entry. Requires ffmpeg.

    python make_sfx.py --list
    python make_sfx.py --out sfx/                  # every sound + all-sounds.wav
    python make_sfx.py bubble success --pitch -2   # two sounds, two semitones down
"""

import argparse
import pathlib

import _ffmpeg
import numpy as np

SR = 48_000
PITCH = 1.0  # frequency multiplier for tonal parts, set from --pitch


def times(duration):
    return np.arange(int(SR * duration)) / SR


def envelope(t, attack, decay):
    return np.minimum(t / attack, 1) * np.exp(-t / decay)


def osc(freq):
    """Sine with continuous phase; ``freq`` is Hz per sample or a constant."""
    freq = np.broadcast_to(np.asarray(freq, dtype=float), np.shape(freq) or (1,))
    return np.sin(2 * np.pi * np.cumsum(freq * PITCH) / SR)


def tone(freq, t):
    return osc(np.full_like(t, freq))


def band_noise(n, lo, hi, seed):
    """Seeded noise band-passed in the frequency domain (no scipy needed)."""
    spectrum = np.fft.rfft(np.random.default_rng(seed).standard_normal(n))
    freqs = np.maximum(np.fft.rfftfreq(n, 1 / SR), 1)
    width = np.log(hi / lo) / 2.5
    spectrum *= np.exp(-0.5 * (np.log(freqs / np.sqrt(lo * hi)) / width) ** 2)
    return np.fft.irfft(spectrum, n)


def room(x, mix=0.18, seed=3):
    """Short stereo reverb from two decaying noise impulses."""
    ir_t = times(0.45)
    channels = []
    for s in (seed, seed + 1):
        ir = np.random.default_rng(s).standard_normal(len(ir_t)) * np.exp(-ir_t / 0.09)
        ir[0] = 0
        wet = np.convolve(x, ir)
        dry = np.pad(x, (0, len(ir) - 1))
        channels.append(dry + mix * wet / (np.max(np.abs(wet)) + 1e-9) * np.max(np.abs(x)))
    return np.stack(channels, 1)


def layer(duration, *events):
    """Mix ``(start_seconds, signal)`` events into one buffer."""
    n = int(SR * duration)
    out = np.zeros(n)
    for start, x in events:
        i = int(start * SR)
        out[i : i + len(x)] += x[: n - i]
    return out


def bubble():
    t = times(0.16)
    return osc(380 + 900 * (1 - np.exp(-t / 0.03))) * envelope(t, 0.003, 0.045)


def boing():
    t = times(0.55)
    f = 220 * (1 + 0.35 * np.exp(-t / 0.15) * np.sin(2 * np.pi * 14 * t))
    return osc(f) * envelope(t, 0.004, 0.16) + 0.25 * osc(2 * f) * envelope(t, 0.004, 0.07)


def pluck(freq=660, duration=0.5):
    t = times(duration)
    body = tone(freq, t) * envelope(t, 0.002, 0.18)
    attack = 0.35 * tone(4 * freq, t) * envelope(t, 0.001, 0.025)
    return body + attack


def success():
    return layer(1.1, (0, pluck(784, 0.4)), (0.08, pluck(988, 0.4)), (0.16, pluck(1319, 0.9)))


def sparkle(seed=5):
    rng = np.random.default_rng(seed)
    t = times(0.12)
    events = []
    for k in range(9):
        freq = 2000 * 2 ** (rng.integers(0, 12) / 12)
        start = k * 0.07 + rng.uniform(0, 0.02)
        events.append((start, 0.6 ** (k / 4) * tone(freq, t) * envelope(t, 0.001, 0.03)))
    return layer(0.9, *events)


def swoosh_pop():
    air = band_noise(int(SR * 0.45), 400, 4000, seed=2)
    ramp = np.linspace(0, 1, len(air))
    air *= np.sin(np.pi * ramp) ** 3 * (0.4 + 0.6 * ramp)
    return layer(0.7, (0, 0.5 * air / np.max(np.abs(air))), (0.38, bubble()))


def tap():
    t = times(0.08)
    knock = tone(1100, t) * envelope(t, 0.0005, 0.012)
    click = band_noise(len(t), 1500, 5000, seed=9) * envelope(t, 0.0003, 0.004)
    return knock + 0.13 * click


def riser():
    t = times(0.6)
    rise = np.minimum(t / 0.5, 1) ** 2
    cutoff = np.exp(-np.maximum(t - 0.55, 0) / 0.01)
    return 0.6 * osc(300 * 2 ** (2.5 * t / 0.6)) * rise * cutoff


SOUNDS = {
    "bubble": (bubble, "rising pop, for a box or chip appearing"),
    "boing": (boing, "springy wobble, for something dropping in and settling"),
    "success": (success, "three-note rising pluck, for the final result"),
    "sparkle": (sparkle, "scattered high plinks, for a reveal or payoff"),
    "swoosh-pop": (swoosh_pop, "air sweep landing on a bubble, for a token arriving"),
    "tap": (tap, "soft woody tick, for keystrokes or small landings"),
    "riser": (riser, "short pitch-up, for anticipation before a reveal"),
}


def save(path, x, loudness=-16, ceiling_db=-1.5):
    """Write a stereo WAV whose loudest 400 ms sits at ``loudness`` LUFS.

    Levelling by loudness rather than peak makes every sound equally loud to
    the ear, and ffmpeg's limiter keeps the peak under ``ceiling_db``, so no
    sound clips or startles next to the others.
    """
    stereo = room(x)
    stereo = stereo - stereo.mean(axis=0)
    raw = pathlib.Path(str(path) + ".raw.wav")
    _ffmpeg.write_wav(raw, 0.5 * stereo / np.max(np.abs(stereo)))
    try:
        _ffmpeg.level_short_sound(raw, path, loudness, ceiling_db)
    finally:
        raw.unlink(missing_ok=True)


def main():
    global PITCH
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="sounds to render (default: all)")
    parser.add_argument("--list", action="store_true", help="list sounds and exit")
    parser.add_argument("--out", default=".", help="output directory")
    parser.add_argument("--pitch", type=float, default=0, help="shift tonal parts by N semitones")
    parser.add_argument(
        "--loudness",
        type=float,
        default=-16,
        help="loudness of each sound's loudest 400 ms, in LUFS",
    )
    args = parser.parse_args()

    if args.list:
        for name, (_, use) in SOUNDS.items():
            print(f"{name:11s} {use}")
        return
    unknown = set(args.names) - SOUNDS.keys()
    if unknown:
        parser.error(f"unknown sound(s): {', '.join(sorted(unknown))}; see --list")

    PITCH = 2 ** (args.pitch / 12)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = {name: SOUNDS[name][0]() for name in args.names or SOUNDS}
    for name, x in rendered.items():
        save(out_dir / f"{name}.wav", x, args.loudness)
        print(f"{name:11s} {len(x) / SR:.2f}s  {out_dir / name}.wav")
    if not args.names:
        gap = np.zeros(int(SR * 0.45))
        reel = np.concatenate([np.concatenate([x, gap]) for x in rendered.values()])
        save(out_dir / "all-sounds.wav", reel, args.loudness)


if __name__ == "__main__":
    main()
