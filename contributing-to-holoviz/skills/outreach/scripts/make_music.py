"""Render a background score from a JSON spec written from a video's beat sheet.

The score follows the video: sections start at the beat sheet's times, each
concept gets a motif that enters when the concept appears on screen, and hits
from make_sfx.py land on the exact frames of on-screen events with the music
ducked under them. Numpy writes the notes; ffmpeg places the hits, ducks the
music, normalizes loudness with a true-peak ceiling and measures the result,
so nothing clips or jumps out. Layers also fade in over their first notes.
Deterministic for a given ffmpeg version: the same spec writes the same WAV,
so commit the spec, not the audio. Requires ffmpeg.

    python make_music.py score.json --out music.wav
    python make_music.py --example > score.json
"""

import argparse
import json
import pathlib
import sys
import tempfile
import zlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _ffmpeg  # noqa: E402
import make_sfx  # noqa: E402

SR = 48_000
MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}
NOTES = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}
BASE_LAYERS = {"pad", "keys", "bass", "drums"}

EXAMPLE = {
    "duration": 120,
    "bpm": 120,
    "key": "F",
    "mode": "lydian",
    "seed": "lumen-ai-explainer",
    "feel": "half",
    "chord_bars": 2,
    "progression": [0, 5, 3, 4],
    "texture": 0.6,
    "motifs": {
        "coordinator": [4, 2, 0],
        "agent": [0, 2, 4, 2],
        "tools": [4, 5, 4],
        "context": "pulse",
    },
    "sections": [
        {"t": 0, "layers": ["pad"], "gain": 4},
        {"t": 10, "layers": ["pad", "coordinator"], "gain": 2},
        {"t": 24, "layers": ["pad", "keys", "coordinator", "agent"]},
        {"t": 48, "layers": ["pad", "keys", "bass", "agent", "tools"]},
        {"t": 60, "layers": ["pad", "keys", "bass", "agent", "context", "drums"]},
        {"t": 94, "layers": "all", "swell": True, "gain": 2},
        {"t": 108, "layers": ["pad", "agent"], "resolve": True},
    ],
    "loudness": -20,
    "hits": [["swoosh-pop", 64.6, 2], ["success", 89.1, 3], ["sparkle", 96.6, 0]],
}


def times(duration):
    return np.arange(int(SR * duration)) / SR


def envelope(t, attack, decay):
    return np.minimum(t / attack, 1) * np.exp(-t / decay)


def mtof(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def filtered(x, lo=None, hi=None):
    """Gentle FFT band-limit; lo/hi in Hz, either may be None."""
    spectrum = np.fft.rfft(x)
    f = np.maximum(np.fft.rfftfreq(len(x), 1 / SR), 1)
    if hi:
        spectrum /= np.sqrt(1 + (f / hi) ** 4)
    if lo:
        spectrum /= np.sqrt(1 + (lo / f) ** 4)
    return np.fft.irfft(spectrum, len(x))


# --- instruments -------------------------------------------------------------
def electric_piano(freq, duration, vel):
    t = times(duration)
    x = (
        np.sin(2 * np.pi * freq * t)
        + 0.3 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t / 0.25)
        + 0.08 * np.sin(2 * np.pi * 7 * freq * t) * np.exp(-t / 0.04)
    )
    return vel * x * envelope(t, 0.008, 1.3) * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t))


def pad(freq, duration, vel):
    t = times(duration)
    x = sum(np.sin(2 * np.pi * freq * d * t) for d in (0.997, 1.0, 1.003)) / 3
    x += 0.2 * np.sin(2 * np.pi * 2 * freq * t)
    fade = np.minimum(t / 0.8, 1) * np.minimum((duration - t) / 0.8, 1)
    return vel * x * np.clip(fade, 0, 1)


def pluck(freq, duration, vel):
    t = times(duration)
    x = np.sin(2 * np.pi * freq * t) * envelope(t, 0.002, 0.25)
    x += 0.3 * np.sin(2 * np.pi * 4 * freq * t) * envelope(t, 0.001, 0.03)
    return vel * x


def bass(freq, duration, vel):
    t = times(duration)
    return vel * np.sin(2 * np.pi * freq * t) * envelope(t, 0.01, 0.6)


def kick(vel):
    t = times(0.3)
    f = 50 + 70 * np.exp(-t / 0.025)
    return vel * np.sin(2 * np.pi * np.cumsum(f) / SR) * envelope(t, 0.002, 0.09)


def snare(vel, seed):
    t = times(0.25)
    body = filtered(noise(len(t), seed), hi=2500) * envelope(t, 0.002, 0.06)
    body /= np.max(np.abs(body))
    return vel * (0.7 * body + 0.3 * np.sin(2 * np.pi * 190 * t) * envelope(t, 0.002, 0.04))


def hat(vel, seed):
    t = times(0.05)
    x = filtered(noise(len(t), seed), lo=7000) * envelope(t, 0.001, 0.012)
    return vel * x / np.max(np.abs(x))


# --- score -------------------------------------------------------------------
class Score:
    def __init__(self, spec):
        self.spec = spec
        self.beat = 60 / spec["bpm"]
        self.bar = 4 * self.beat
        self.n = int(SR * spec["duration"])
        self.rng = np.random.default_rng(zlib.crc32(str(spec.get("seed", "")).encode()))
        self.tonic = 60 + NOTES[spec.get("key", "C")]
        self.scale = MODES[spec.get("mode", "major")]
        self.tracks = {k: np.zeros(self.n + SR * 4) for k in ("music", "drums")}
        self.motifs = spec.get("motifs", {})
        self.sections = sorted(spec["sections"], key=lambda s: s["t"])
        self.warnings = []
        for s in self.sections:
            off = s["t"] / self.bar - round(s["t"] / self.bar)
            if abs(off) > 0.02:
                self.warnings.append(
                    f"section at {s['t']}s is {off * self.bar:+.2f}s off a bar line"
                )

    def degree(self, d, octave=0):
        o, i = divmod(d, 7)
        return self.tonic + 12 * (o + octave) + self.scale[i]

    def chord(self, d, notes=5):
        return [self.degree(d + 2 * k, -1) for k in range(notes)]

    def add(self, track, start, x):
        buf = self.tracks[track]
        i = int(start * SR)
        m = min(len(x), len(buf) - i)
        if i >= 0 and m > 0:
            buf[i : i + m] += x[:m]

    def layers_at(self, t):
        current = self.sections[0]
        for s in self.sections:
            if s["t"] <= t + 1e-6:
                current = s
        layers = current["layers"]
        if layers == "all":
            layers = sorted(BASE_LAYERS | set(self.motifs))
        return current, set(layers)

    def render(self):
        prog = self.spec.get("progression", [0, 5, 3, 4])
        chord_bars = self.spec.get("chord_bars", 1)
        half = self.spec.get("feel") == "half"
        seen = set()
        entered = {}
        bars = int(np.ceil(self.spec["duration"] / self.bar))
        for b in range(bars):
            t0 = b * self.bar
            section, layers = self.layers_at(t0)
            resolving = section.get("resolve")
            degree = 0 if resolving else prog[(b // chord_bars) % len(prog)]
            chord = self.chord(degree)
            for layer in layers:
                entered.setdefault(layer, b)
            # a layer comes in over its first few notes instead of at full level;
            # chord layers count chords, the rest count bars
            ramp = {}
            for k in layers:
                step = (b - entered[k]) // (chord_bars if k in ("pad", "keys") else 1)
                ramp[k] = (0.5, 0.8, 1)[min(step, 2)]
            new_chord = resolving or b % chord_bars == 0
            if "pad" in layers and new_chord:
                hold = (self.spec["duration"] - t0) if resolving else chord_bars * self.bar
                if not (resolving and "resolved" in seen):
                    for m in chord[:4]:
                        self.add("music", t0, pad(mtof(m), hold + 0.6, 0.06 * ramp["pad"]))
                    if resolving:
                        seen.add("resolved")
            if "keys" in layers and new_chord and not resolving:
                for j, m in enumerate(chord):
                    vel = 0.13 * ramp["keys"] * self.rng.uniform(0.85, 1)
                    self.add(
                        "music",
                        t0 + j * 0.018 + self.rng.uniform(0, 0.01),
                        electric_piano(mtof(m), chord_bars * self.bar * 0.9, vel),
                    )
            if "bass" in layers and not resolving:
                root = mtof(self.degree(degree, -2))
                self.add("music", t0, bass(root, 1.5 * self.beat, 0.45 * ramp["bass"]))
                self.add(
                    "music", t0 + 2.5 * self.beat, bass(root, 1.4 * self.beat, 0.35 * ramp["bass"])
                )
            if "drums" in layers and not resolving:
                self.drums(t0, b, half, ramp["drums"])
            for name, motif in self.motifs.items():
                if name not in layers or (resolving and name in seen):
                    continue
                first = name not in seen
                seen.add(name)
                if motif == "pulse":
                    root = mtof(self.degree(0, -1))
                    for k in range(8):
                        self.add("music", t0 + k * self.beat / 2, pluck(root, 0.3, 0.07))
                elif first or b % 4 == 0:
                    vel = 0.16 if first else 0.08
                    for k, d in enumerate(motif):
                        self.add(
                            "music",
                            t0 + k * self.beat / 2,
                            pluck(mtof(self.degree(d, 1)), 0.6, vel),
                        )
        for s in self.sections:
            if s.get("swell"):
                self.swell(s["t"])
        return self.mix()

    def drums(self, t0, b, half, level=1):
        snare_beats = (2,) if half else (1, 3)
        self.add("drums", t0, kick(0.9 * level))
        if not half:
            self.add("drums", t0 + 2.5 * self.beat, kick(0.6 * level))
        for beat in snare_beats:
            self.add("drums", t0 + beat * self.beat + 0.012, snare(0.35 * level, b * 10 + beat))
        for beat in range(4):
            for k, offset in enumerate((0, 0.62)):  # swung eighths
                vel = 0.10 * level * self.rng.uniform(0.6, 1)
                self.add(
                    "drums", t0 + (beat + offset) * self.beat, hat(vel, b * 100 + beat * 2 + k)
                )

    def swell(self, t):
        d = self.bar
        x = filtered(noise(int(SR * d), 77), lo=800, hi=6000)
        ramp = np.linspace(0, 1, len(x))
        self.add("music", t - d, 0.05 * x / np.max(np.abs(x)) * ramp**3)

    def mix(self):
        n = self.n
        music = self.tracks["music"][:n] + 0.8 * self.tracks["drums"][:n]
        # per-section gain in dB, crossfaded over a second, so the payoff can lift
        gain_db = np.zeros(n)
        for s in self.sections:
            gain_db[int(s["t"] * SR) :] = s.get("gain", 0)
        ramp = np.ones(SR) / SR
        gain_db = np.convolve(np.pad(gain_db, (SR - 1, 0), mode="edge"), ramp, "valid")
        music *= 10 ** (gain_db / 20)
        texture = self.spec.get("texture", 0.5)
        # tape wobble, warm low-pass, vinyl hiss and crackle, scaled by texture
        idx = np.arange(n) + SR * texture * 0.0025 * np.sin(2 * np.pi * 0.45 * np.arange(n) / SR)
        music = np.interp(idx, np.arange(n), music)
        music = filtered(music, lo=50, hi=8000 - 4800 * texture)
        hiss = 0.006 * texture * filtered(noise(n, 7), hi=6000)
        crackle = np.zeros(n)
        pos = self.rng.integers(0, n, int(self.spec["duration"] * 9 * texture))
        crackle[pos] = self.rng.uniform(-1, 1, len(pos)) * self.rng.uniform(0.05, 0.25, len(pos))
        crackle = 0.5 * texture * np.convolve(crackle, np.exp(-np.arange(40) / 6), "same")
        left = 0.7 * music + 0.3 * np.roll(music, int(SR * 0.012)) + hiss + crackle
        right = 0.7 * music + 0.3 * np.roll(music, int(SR * 0.019)) + np.roll(hiss + crackle, 999)
        out = np.stack([left, right], 1)
        fade = np.ones(n)
        fade[-SR * 3 :] = np.linspace(1, 0, SR * 3)
        out *= fade[:, None]
        return out


def finish(score, music, out_path):
    """Place the hits, duck under them, and master the mix, all in ffmpeg."""
    hits = score.spec.get("hits", [])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        bed = tmp / "music.wav"
        _ffmpeg.write_wav(bed, 0.25 * music / np.max(np.abs(music)))
        scan = _ffmpeg.measure(bed)
        inputs, chains, labels = [bed], [], []
        for k, (name, t, *gain) in enumerate(hits, start=1):
            gain = gain[0] if gain else 3
            if gain > 6:
                score.warnings.append(f"hit {name} at {t}s asked for +{gain} LU; capped at +6")
                gain = 6
            path = tmp / f"hit{k}.wav"
            make_sfx.save(path, make_sfx.SOUNDS[name][0]())
            window = (scan["t"] > t - 2) & (scan["t"] <= t)
            bed_lufs = scan["momentary"][window].mean() if window.any() else -40
            volume = bed_lufs + gain - _ffmpeg.loudest_moment(path)
            ms = int(round(t * 1000))
            inputs.append(path)
            chains.append(f"[{k}]adelay={ms}:all=1,volume={volume:.3f}dB[h{k}]")
            labels.append(f"[h{k}]")
        if hits:
            graph = ";".join(
                chains
                + [
                    "".join(labels) + f"amix=inputs={len(hits)}:normalize=0:duration=longest,"
                    # the sidechain must outlast the music, or the compressor ends the mix early
                    f"apad=whole_dur={score.spec['duration']},asplit[sc][fx]",
                    "[0][sc]sidechaincompress=threshold=0.02:ratio=4:attack=10:release=350[duck]",
                    "[duck][fx]amix=inputs=2:normalize=0:duration=first[pre]",
                ]
            )
        else:
            graph = "[0]anull[pre]"  # codespell:ignore anull
        mode = _ffmpeg.loudnorm(out_path, score.spec.get("loudness", -20), graph, inputs)
        if mode != "linear":
            score.warnings.append(
                "loudnorm fell back to dynamic mode, which pumps the level; "
                "lower the loudest hits"
            )
    return _ffmpeg.measure(out_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", nargs="?", help="score spec JSON")
    parser.add_argument("--out", default="music.wav", help="output WAV")
    parser.add_argument("--example", action="store_true", help="print an example spec and exit")
    args = parser.parse_args()
    if args.example:
        print(json.dumps(EXAMPLE, indent=2))
        return
    if not args.spec:
        parser.error("give a spec file, or --example")
    score = Score(json.loads(pathlib.Path(args.spec).read_text()))
    stats = finish(score, score.render(), args.out)
    # ebur128 reports no short-term value until 3 s have passed; skip those,
    # and count anything 20 LU under the average as quiet, so a fade-in from
    # silence isn't reported as a jump
    raw = stats["short_term"]
    st = np.maximum(raw, stats["integrated"] - 20)
    valid = (raw[30:] > -100) & (raw[:-30] > -100)
    rises = (st[30:] - st[:-30])[valid]
    rise = float(rises.max()) if len(rises) else 0.0
    loudest = float(stats["momentary"].max())
    if rise > 6:
        score.warnings.append(
            f"music gets {rise:.1f} LU louder within 3 s somewhere; "
            "add layers more gradually or lower that section's gain"
        )
    if loudest - stats["integrated"] > 10:
        score.warnings.append("loudest moment is over 10 LU above the average; lower the hits")
    for w in score.warnings:
        print("warning:", w)
    print(
        f"integrated {stats['integrated']} LUFS, loudest moment {loudest:.1f} LUFS, "
        f"true peak {stats['true_peak']} dBFS, largest 3 s rise {rise:.1f} LU"
    )
    ends = [s["t"] for s in score.sections[1:]] + [score.spec["duration"]]
    for s, end in zip(score.sections, ends):
        span = (stats["t"] > s["t"] + 0.4) & (stats["t"] <= end)
        power = np.mean(10 ** (stats["momentary"][span] / 10)) if span.any() else 1e-12
        level = 10 * np.log10(power)
        layers = s["layers"] if s["layers"] == "all" else ", ".join(s["layers"])
        print(f"{s['t']:6.1f}s  {level:6.1f} LUFS  {layers}")
    print(f"wrote {args.out} ({score.spec['duration']}s)")


if __name__ == "__main__":
    main()
