"""Render a narration spec to a voice track, an SRT file and line timings.

Every line belongs to a speaker, and every speaker has one reference take: a
voice shipped in ``assets/voices`` (``{"voice": "measured"}``), a saved clip and
its transcript, or one of its own lines rendered from a written description by
Qwen3-TTS VoiceDesign. Every other line clones its
speaker's reference with the Base model, given the reference's transcript as
well as its audio, so the lines keep the reference's delivery. Both models run
locally through ``faster-qwen3-tts`` (GGML, Q8_0), or in bf16 through the
official ``qwen-tts`` package with ``"engine": "qwen-tts"``.

Lines with ``"t"`` are placed at that time, ``lead`` seconds after their screen
starts, and the script warns when one runs past its screen, so the fix is a
shorter line rather than a faster voice. Lines without ``"t"`` set the
timeline themselves and write it to ``--timeline``. Takes are cached by a hash
of everything that changes the audio, so only edited lines are rendered
again; commit the spec, this script and the saved references, not the takes.

    python make_voice.py --example > narration.json
    python make_voice.py narration.json --out voice.wav --srt voice.srt
    python make_voice.py narration.json --line open --takes 4   # audition one line
    python make_voice.py narration.json --pick 3                # steadiest take per line

The ``lexicon`` respells words for the model only ("hvPlot" -> "H V plot");
captions keep the on-screen spelling.
"""

import argparse
import glob
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _ffmpeg  # noqa: E402

EXAMPLE = {
    "duration": 12,
    "voice": {
        "lang": "en",
        "speakers": {"narrator": {"voice": "measured"}},
    },
    "lead": 0.4,
    "tail": 0.5,
    "loudness": -16,
    "lexicon": {"hvPlot": "H V plot", "HoloViz": "holo viz"},
    "lines": [
        {"id": "open", "t": 0, "text": "HoloViz Skills teach your agent hvPlot."},
        {"id": "close", "t": 6, "text": "One command installs them.", "take": 2},
    ],
}

LANGUAGES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
}
DESIGN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
CLONE_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
# shipped reference voices: <name>.wav plus <name>.json with its exact transcript
VOICES = pathlib.Path(__file__).resolve().parent.parent / "assets" / "voices"

# trim silence at both ends, drop rumble, match the video's sample rate
CLEAN = (
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,"
    "areverse,highpass=f=80,aresample=48000"
)


def spoken(text, lexicon):
    """Respell lexicon words for the model, longest first, whole words only."""
    for word in sorted(lexicon, key=len, reverse=True):
        text = re.sub(rf"(?<![\w-]){re.escape(word)}(?![\w-])", lexicon[word], text)
    return text


def find_binary(name, env_var, known):
    """$env_var, then PATH, then known install locations (globs allowed)."""
    candidates = [os.environ.get(env_var)] if os.environ.get(env_var) else []
    candidates += [shutil.which(name)]
    candidates += [str(pathlib.Path(sys.executable).parent / name)]
    for pattern in known:
        candidates += sorted(glob.glob(os.path.expanduser(pattern)))
    return next((c for c in candidates if c and pathlib.Path(c).is_file()), None)


def qwen3_binary():
    path = find_binary(
        "faster-qwen3-tts",
        "FASTER_QWEN3_TTS",
        [
            "~/.local/bin/faster-qwen3-tts",  # uv tool install faster-qwen3-tts
            "~/miniconda3/envs/*/bin/faster-qwen3-tts",
            "~/miniforge3/envs/*/bin/faster-qwen3-tts",
        ],
    )
    if not path:
        raise SystemExit(
            "faster-qwen3-tts not found; uv tool install faster-qwen3-tts, or set FASTER_QWEN3_TTS"
        )
    return path


def qwen_python():
    """The Python of a venv with the official qwen-tts package, for the bf16 engine.

    Not PATH: qwen-tts pins its own transformers, so it lives in a venv of its own.
    """
    for c in [os.environ.get("QWEN_TTS_PYTHON"), "~/.venvs/qwen-tts/bin/python"]:
        if c and pathlib.Path(c).expanduser().is_file():
            return str(pathlib.Path(c).expanduser())
    raise SystemExit(
        '"engine": "qwen-tts" needs a venv with `pip install qwen-tts soundfile`; '
        "set QWEN_TTS_PYTHON to its python"
    )


def finish(raw, clean):
    """Clean a raw take into the cache and drop the raw file."""
    _ffmpeg.ffmpeg("-i", str(raw), "-af", CLEAN, "-ac", "1", *_ffmpeg.BITEXACT, str(clean))
    pathlib.Path(raw).unlink(missing_ok=True)


def cached(cache, prefix, key):
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]
    return cache / f"{prefix}-{digest}.wav"


class Engine:
    """Where takes are cached and how they are rendered: GGML Q8_0 by default, or bf16."""

    def __init__(self, voice, cache):
        self.cache = cache
        self.lang = voice.get("lang")
        self.language = LANGUAGES.get(self.lang, "Auto")
        self.quant = voice.get("quant", voice.get("design", {}).get("quant", "Q8_0"))
        self.bf16 = voice.get("engine") == "qwen-tts"
        if voice.get("engine") not in (None, "ggml", "qwen-tts"):
            raise SystemExit(f'unknown engine {voice["engine"]!r}; use "ggml" or "qwen-tts"')

    def _key(self, key):
        # the same keys as earlier versions of this script, so cached takes stay valid
        key = {**key, "lang": self.lang, "quant": self.quant}
        if self.bf16:
            key["engine"] = "qwen-tts-bf16"
        return key

    def design_path(self, text, design, take):
        key = {
            "model": design.get("model", DESIGN_MODEL),
            "text": text,
            "instruct": design["instruct"],
            "take": take,
        }
        if "temp" in design:
            key["temp"] = design["temp"]
        return cached(self.cache, "design", self._key(key))

    def clone_path(self, text, ref, ref_text, take):
        key = {
            "model": CLONE_MODEL,
            "text": text,
            "ref": hashlib.sha256(pathlib.Path(ref).read_bytes()).hexdigest(),
            "ref_text": ref_text,
            "take": take,
        }
        return cached(self.cache, "clone", self._key(key))

    def design(self, text, design, take):
        """A take of ``text`` in a voice made from ``design["instruct"]``. VoiceDesign has no
        seed, so takes are numbered instead: each number is rendered once and kept."""
        clean = self.design_path(text, design, take)
        if clean.exists():
            return clean
        if self.bf16:
            self._bf16(
                [{"kind": "design", "text": text, "instruct": design["instruct"], "out": clean}]
            )
            return clean
        raw = clean.with_suffix(".raw.wav")
        # GGML's Metal library has no bf16 get_rows kernel, so --quant BF16
        # segfaults; Q8_0 avoids it
        cmd = [
            qwen3_binary(),
            "--backend",
            "ggml",
            "--quant",
            self.quant,
            "design",
            "--model",
            design.get("model", DESIGN_MODEL),
            "--language",
            self.language,
            "--text",
            text,
            "--instruct",
            design["instruct"],
            "--output",
            str(raw),
        ]
        if "temp" in design:
            cmd += ["--temperature", str(design["temp"])]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode or not raw.exists():
            raise SystemExit(
                f"faster-qwen3-tts design failed on {text!r}:\n{result.stderr[-2000:]}"
            )
        finish(raw, clean)
        return clean

    def clones(self, ref, ref_text, jobs):
        """Render ``[(text, clean_path), ...]`` that clone ``ref`` with one model load,
        since loading the model costs more than speaking a short line."""
        jobs = [(t, p) for t, p in jobs if not p.exists()]
        if not jobs:
            return
        print(f"cloning {len(jobs)} line(s) in one model load{' (bf16)' if self.bf16 else ''}")
        if self.bf16:
            self._bf16(
                [
                    {
                        "kind": "clone",
                        "text": t,
                        "ref_audio": str(ref),
                        "ref_text": ref_text,
                        "out": p,
                    }
                    for t, p in jobs
                ]
            )
            return
        with tempfile.TemporaryDirectory(dir=self.cache) as out:
            cmd = [
                qwen3_binary(),
                "--backend",
                "ggml",
                "--quant",
                self.quant,
                "serve",
                "--mode",
                "clone",
                "--model",
                CLONE_MODEL,
                "--ref-audio",
                str(ref),
                "--ref-text",
                ref_text,
                "--language",
                self.language,
                "--output-dir",
                out,
            ]
            stdin = "".join(" ".join(text.split()) + "\n" for text, _ in jobs) + "exit\n"
            result = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
            for k, (text, clean) in enumerate(jobs, start=1):
                raw = pathlib.Path(out) / f"out_{k:04d}.wav"
                if result.returncode or not raw.exists():
                    raise SystemExit(
                        f"faster-qwen3-tts serve failed on {text!r}:\n"
                        f"{(result.stdout + result.stderr)[-2000:]}"
                    )
                finish(raw, clean)

    def _bf16(self, jobs):
        """Render jobs in one ``_qwen_tts_bf16.py`` process (one load per model)."""
        payload = [
            {
                **{k: v for k, v in j.items() if k != "out"},
                "language": self.language,
                "out": str(pathlib.Path(j["out"]).with_suffix(".raw.wav")),
            }
            for j in jobs
        ]
        result = subprocess.run(
            [qwen_python(), str(pathlib.Path(__file__).with_name("_qwen_tts_bf16.py"))],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        for j, p in zip(jobs, payload):
            if result.returncode or not pathlib.Path(p["out"]).exists():
                raise SystemExit(
                    f"qwen-tts failed on {j['text']!r}:\n{(result.stdout + result.stderr)[-2000:]}"
                )
            finish(p["out"], j["out"])


def references(spec, engine):
    """Each speaker's reference ``(audio path, transcript, line id or None)``.

    A speaker is ``{"voice": name}`` (a clip shipped in ``assets/voices``),
    ``{"audio": path, "text": transcript}`` (a saved clip) or
    ``{"line": id, "design": {"instruct": ...}, "take": n}`` (that line rendered
    from the description). ``voice.design`` holds defaults for every speaker's design.
    """
    voice = spec["voice"]
    speakers = voice.get("speakers")
    if not speakers:
        raise SystemExit(
            "voice.speakers is missing; see --example. One narrator is one speaker: "
            '{"narrator": {"voice": "measured"}}'
        )
    lexicon = spec.get("lexicon", {})
    by_id = {line["id"]: line for line in spec["lines"]}
    refs = {}
    for name, sp in speakers.items():
        if "voice" in sp:
            # a voice shipped with this skill, the same clip on every machine
            meta = VOICES / f"{sp['voice']}.json"
            if not meta.exists():
                shipped = ", ".join(sorted(p.stem for p in VOICES.glob("*.json"))) or "none"
                raise SystemExit(
                    f"speaker {name!r}: no shipped voice {sp['voice']!r} (shipped: {shipped})"
                )
            refs[name] = (meta.with_suffix(".wav"), json.loads(meta.read_text())["text"], None)
            continue
        if "audio" in sp:
            # a saved reference: its transcript must be exactly what it says
            refs[name] = (pathlib.Path(sp["audio"]).expanduser(), sp["text"], None)
            continue
        line = by_id.get(sp.get("line"))
        if line is None:
            raise SystemExit(
                f'speaker {name!r} needs "voice", "audio" and "text", or a "line" that is a line id'
            )
        design = {**voice.get("design", {}), **sp.get("design", {})}
        if "instruct" not in design:
            raise SystemExit(f"speaker {name!r} has no design.instruct describing the voice")
        text = spoken(line["text"], lexicon)
        refs[name] = (engine.design(text, design, sp.get("take", 1)), text, line["id"])
    return refs


def speaker_of(spec, line):
    name = line.get("speaker", next(iter(spec["voice"]["speakers"])))
    if name not in spec["voice"]["speakers"]:
        raise SystemExit(f"line {line['id']!r} has unknown speaker {name!r}")
    return name


def render(spec, engine, take=None):
    """Every line's take, as ``{line id: path}``; ``take`` overrides each line's own."""
    refs = references(spec, engine)
    lexicon = spec.get("lexicon", {})
    paths, jobs = {}, {}
    for line in spec["lines"]:
        name = speaker_of(spec, line)
        ref, ref_text, ref_line = refs[name]
        text = spoken(line["text"], lexicon)
        if line["id"] == ref_line or text == ref_text:
            paths[line["id"]] = ref  # the reference already says this line
            continue
        path = engine.clone_path(text, ref, ref_text, take or line.get("take", 1))
        paths[line["id"]] = path
        jobs.setdefault(name, []).append((text, path))
    for name, js in jobs.items():
        engine.clones(refs[name][0], refs[name][1], js)
    return paths


def seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def split_phrases(text):
    """Sentences, colons and ellipses: the places a speaker stops for breath."""
    return [part for part in re.split(r"(?<=[.?!…:;])\s+", text.strip()) if part]


def phrase_spans(path, phrases, min_gap=0.12):
    """Start and end of each phrase inside a take, from its longest internal pauses.

    Falls back to splitting by character count when the take has fewer pauses
    than phrase breaks.
    """
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float)[:: w.getnchannels()]
    hop = sr // 100
    frames = len(x) // hop
    total = len(x) / sr
    if len(phrases) < 2 or frames < 10:
        return [(0.0, total)]
    rms = np.sqrt(np.mean(x[: frames * hop].reshape(frames, hop) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-9)
    silent = db < db.max() - 35
    runs, k = [], 0
    while k < frames:
        if silent[k]:
            j = k
            while j < frames and silent[j]:
                j += 1
            if k > 0 and j < frames and (j - k) / 100 >= min_gap:
                runs.append((k / 100, j / 100))
            k = j
        else:
            k += 1
    need = len(phrases) - 1
    if len(runs) < need:
        sizes = (
            np.cumsum([0] + [len(ph) for ph in phrases]) / sum(len(ph) for ph in phrases) * total
        )
        return [(float(sizes[i]), float(sizes[i + 1])) for i in range(len(phrases))]
    gaps = sorted(sorted(runs, key=lambda r: r[1] - r[0], reverse=True)[:need])
    edges = [0.0] + [g for gap in gaps for g in gap] + [total]
    return [(edges[2 * i], edges[2 * i + 1]) for i in range(len(phrases))]


def place(spec, engine):
    """Render every line and place it on the timeline, with fit warnings.

    Lines with a ``"t"`` are placed at that time. When no line has one, the
    dialogue sets the timeline instead: lines play in order within their
    ``"scene"``, ``timeline.gap`` s apart, and each scene ends on the next bar
    line (``timeline.bar`` s) after its last line plus ``timeline.pad``.
    """
    auto = all("t" not in line for line in spec["lines"])
    lines = list(spec["lines"]) if auto else sorted(spec["lines"], key=lambda line: line["t"])
    lead, tail = spec.get("lead", 0.4), spec.get("tail", 0.5)
    paths = render(spec, engine)
    takes = [
        (line, line.get("take", 1), paths[line["id"]], seconds(paths[line["id"]])) for line in lines
    ]
    starts, ends = {}, {}
    if auto:
        tl = spec.get("timeline", {})
        bar, gap, pad = tl.get("bar", 3.0), tl.get("gap", 0.35), tl.get("pad", 0.8)

        def scene_of(line):
            return line.get("scene", line["id"])

        scenes, t = {}, 0.0
        for sc in dict.fromkeys(scene_of(line) for line in lines):
            scenes[sc] = round(t, 3)
            cursor, ids = t + lead, []
            for line, _, _, length in takes:
                if scene_of(line) == sc:
                    starts[line["id"]] = cursor
                    cursor += length + gap
                    ids.append(line["id"])
            t = math.ceil(round((cursor - gap + pad) / bar, 6)) * bar
            ends.update({i: t for i in ids})
        spec["duration"] = t
        spec["_scenes"] = scenes
    placed, warnings = [], []
    for i, (line, take, path, length) in enumerate(takes):
        if auto:
            start, end = starts[line["id"]], ends[line["id"]]
        else:
            end = line.get("end", lines[i + 1]["t"] if i + 1 < len(lines) else spec["duration"])
            start = line["t"] + lead
            room = end - tail - start
            if length > room:
                words = len(line["text"].split())
                fit = int(words * room / length)  # this voice's own pace
                warnings.append(
                    f"{line['id']}: {length:.2f}s of speech in {room:.2f}s; "
                    f"cut it from {words} words to about {fit}"
                )
        phrases = split_phrases(line["text"])
        spans = phrase_spans(path, phrases)
        placed.append(
            {
                "id": line["id"],
                "scene": line.get("scene", line["id"]),
                "speaker": line.get("speaker"),
                "start": round(start, 3),
                "end": round(start + length, 3),
                "window_end": end,
                "take": take,
                "text": line["text"],
                "path": str(path),
                "phrases": [
                    {"text": ph, "start": round(start + a, 3), "end": round(start + b, 3)}
                    for ph, (a, b) in zip(phrases, spans)
                ],
            }
        )
    return placed, warnings


def mix(placed, spec, out):
    """Lay the takes on one timeline and level the result to ``loudness`` LUFS."""
    duration = spec["duration"]
    # clones can come out at different levels; match each line to the target
    # first, so one loud line can't push the final leveling into dynamic mode
    target = spec.get("loudness", -16)
    gains = []
    for p in placed:
        level = _ffmpeg.measure(p["path"])["integrated"]
        gains.append(0.0 if level < -60 else target - level)
        p["gain"] = round(gains[-1], 1)
    chains = [
        f"[{k}]volume={g:.2f}dB,adelay={int(round(p['start'] * 1000))}:all=1[v{k}]"
        for k, (p, g) in enumerate(zip(placed, gains))
    ]
    labels = "".join(f"[v{k}]" for k in range(len(placed)))
    graph = ";".join(
        chains
        + [
            f"{labels}amix=inputs={len(placed)}:normalize=0:duration=longest,"
            f"apad=whole_dur={duration},atrim=0:{duration}[pre]"
        ]
    )
    mode = _ffmpeg.loudnorm(out, spec.get("loudness", -16), graph, [p["path"] for p in placed])
    return mode


def stamp(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def captions(placed, hold=0.4):
    """Caption cues: each line from its first word, held a little after the last."""
    cues = []
    for i, p in enumerate(placed):
        stop = min(p["end"] + hold, p["window_end"] - 0.05)
        if i + 1 < len(placed):
            stop = min(stop, placed[i + 1]["start"] - 0.05)
        cues.append(
            {
                "id": p["id"],
                "scene": p.get("scene", p["id"]),
                "speaker": p.get("speaker"),
                "start": p["start"],
                "end": round(stop, 3),
                "text": p["text"],
                "phrases": p.get("phrases", []),
            }
        )
    return cues


def write_srt(cues, path):
    blocks = [
        f"{n}\n{stamp(c['start'])} --> {stamp(c['end'])}\n"
        f"{chr(10).join(textwrap.wrap(c['text'], 42))}\n"
        for n, c in enumerate(cues, start=1)
    ]
    pathlib.Path(path).write_text("\n".join(blocks))


def longest_pause(path):
    """The longest silence inside a take, in seconds (its ends are already trimmed)."""
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float)[:: w.getnchannels()]
    hop = sr // 100
    frames = len(x) // hop
    if frames < 2:
        return 0.0
    db = 20 * np.log10(np.sqrt(np.mean(x[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9)
    longest = run = 0
    for quiet in db < db.max() - 35:
        run = run + 1 if quiet else 0
        longest = max(longest, run)
    return longest / 100


def median_pitch(path):
    """Median fundamental frequency of a take in Hz, by autocorrelation of voiced 40 ms frames."""
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float)[:: w.getnchannels()]
    n, hop, lo, hi = int(0.04 * sr), int(0.01 * sr), int(sr / 400), int(sr / 70)
    f0 = []
    for i in range(0, len(x) - n, hop):
        frame = x[i : i + n]
        if np.sqrt(np.mean(frame**2)) < 500:
            continue
        frame = frame - frame.mean()
        ac = np.correlate(frame, frame, "full")[n - 1 :]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.5 * ac[0]:
            f0.append(sr / k)
    return float(np.median(f0)) if f0 else float("nan")


def measure(line, path):
    return len(line["text"].split()) / seconds(path), longest_pause(path)


def audition(spec, line_id, n, engine, out):
    """Render takes 1..n of one line back to back, with each take's pace and longest pause."""
    line = next((line for line in spec["lines"] if line["id"] == line_id), None)
    if line is None:
        raise SystemExit(f"no line with id {line_id!r}")
    name = speaker_of(spec, line)
    sp = spec["voice"]["speakers"][name]
    if sp.get("line") == line_id and "audio" not in sp:
        # this line is the speaker's reference: its takes are candidate voices
        design = {**spec["voice"].get("design", {}), **sp.get("design", {})}
        text = spoken(line["text"], spec.get("lexicon", {}))
        paths = [engine.design(text, design, k) for k in range(1, n + 1)]
        field = f'"take" on speaker {name!r} (this picks the voice for every line)'
    else:
        ref, ref_text, _ = references(spec, engine)[name]
        text = spoken(line["text"], spec.get("lexicon", {}))
        paths = [engine.clone_path(text, ref, ref_text, k) for k in range(1, n + 1)]
        engine.clones(ref, ref_text, [(text, p) for p in paths])
        field = f'"take" on line {line_id!r}'
    gap = np.zeros(int(0.8 * _ffmpeg.SR))
    parts = []
    for k, path in enumerate(paths, start=1):
        with wave.open(str(path)) as w:
            parts += [np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32768, gap]
        pace, pause = measure(line, path)
        print(f"take {k}: {seconds(path):.2f}s, {pace:.2f} words/s, longest pause {pause:.2f}s")
    _ffmpeg.write_wav(out, np.concatenate(parts))
    print(f"wrote {out}; set {field} to the one you want")


def pick(spec, n, engine):
    """Set each cloned line's ``"take"`` to the steadiest of takes 1..n.

    Lines read at very different speeds or pitches, or with a long pause in
    the middle, make a narration sound like separate recordings. Each line
    gets the take nearest the median pace of all takes and nearest its
    speaker's reference pitch, with any pause over 0.45 s counted against it.
    """
    refs = references(spec, engine)
    lexicon = spec.get("lexicon", {})
    candidates, jobs = {}, {}
    for line in spec["lines"]:
        name = speaker_of(spec, line)
        ref, ref_text, ref_line = refs[name]
        text = spoken(line["text"], lexicon)
        if line["id"] == ref_line or text == ref_text:
            continue  # the reference itself; its take picks the voice
        candidates[line["id"]] = [
            engine.clone_path(text, ref, ref_text, k) for k in range(1, n + 1)
        ]
        jobs.setdefault(name, []).extend((text, p) for p in candidates[line["id"]])
    for name, js in jobs.items():
        engine.clones(refs[name][0], refs[name][1], js)  # every take of every line in one load
    by_id = {line["id"]: line for line in spec["lines"]}
    ref_pitch = {name: median_pitch(ref) for name, (ref, _, _) in refs.items()}
    scores = {
        i: [(*measure(by_id[i], p), median_pitch(p)) for p in ps] for i, ps in candidates.items()
    }
    target = float(np.median([pace for s in scores.values() for pace, _, _ in s]))
    for i, options in scores.items():
        ref_hz = ref_pitch[speaker_of(spec, by_id[i])]

        def cost(k, options=options, ref_hz=ref_hz):
            pace, pause, hz = options[k]
            drift = abs(12 * np.log2(hz / ref_hz)) if hz > 0 and ref_hz > 0 else 0.0
            # a semitone of pitch drift costs as much as 0.5 words/s of pace: a line
            # 3 semitones off the reference sounds like another speaker
            return abs(pace - target) + 4 * max(0, pause - 0.45) + 0.5 * drift

        best = min(range(n), key=cost)
        by_id[i]["take"] = best + 1
        print(
            f"{i:12s} take {best + 1}  "
            + "  ".join(
                f"{k + 1}: {p:.2f} w/s, {q:.2f}s, {h:.0f} Hz" for k, (p, q, h) in enumerate(options)
            )
        )
    print(f"median pace {target:.2f} words/s")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", nargs="?", help="narration spec JSON")
    parser.add_argument("--out", default="voice.wav", help="output WAV")
    parser.add_argument("--srt", default="voice.srt", help="output SRT captions")
    parser.add_argument("--json", default="voice.json", help="output cue timings for the HTML")
    parser.add_argument("--cache", default=".voice-cache", help="cache directory for takes")
    parser.add_argument(
        "--timeline",
        default="timeline.json",
        help="with untimed lines: output scene start times and duration",
    )
    parser.add_argument("--line", help="audition one line by id (with --takes)")
    parser.add_argument("--takes", type=int, default=3, help="takes to audition")
    parser.add_argument(
        "--pick",
        type=int,
        metavar="N",
        help="render takes 1..N of every line, write the steadiest into the spec, then render",
    )
    parser.add_argument("--example", action="store_true", help="print an example spec and exit")
    args = parser.parse_args()
    if args.example:
        print(json.dumps(EXAMPLE, indent=2))
        return
    if not args.spec:
        parser.error("give a spec file, or --example")
    spec_path = pathlib.Path(args.spec)
    spec = json.loads(spec_path.read_text())
    cache = pathlib.Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    engine = Engine(spec["voice"], cache)
    if args.line:
        audition(spec, args.line, args.takes, engine, f"takes-{args.line}.wav")
        return
    if args.pick:
        pick(spec, args.pick, engine)
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote the chosen takes into {spec_path}")
    placed, warnings = place(spec, engine)
    mode = mix(placed, spec, args.out)
    if mode != "linear":
        warnings.append("loudnorm fell back to dynamic mode; check for a much louder line")
    cues = captions(placed)
    write_srt(cues, args.srt)
    pathlib.Path(args.json).write_text(json.dumps(cues, indent=1))
    if "_scenes" in spec:
        pathlib.Path(args.timeline).write_text(
            json.dumps({"duration": spec["duration"], "scenes": spec["_scenes"]}, indent=1)
        )
        print(
            f"timeline: {spec['duration']:.1f}s, scenes at "
            + ", ".join(f"{k} {v:.1f}" for k, v in spec["_scenes"].items())
        )
    for w in warnings:
        print("warning:", w)
    for p in placed:
        room = p["window_end"] - spec.get("tail", 0.5) - p["end"]
        print(
            f"{p['start']:6.2f}-{p['end']:6.2f}s  {room:+5.2f}s spare  take {p['take']:<3} "
            f"{p.get('gain', 0):+5.1f} dB  {p['id']}"
        )
    stats = _ffmpeg.measure(args.out)
    print(f"integrated {stats['integrated']} LUFS, true peak {stats['true_peak']} dBFS")
    print(f"wrote {args.out}, {args.srt}, {args.json}")


if __name__ == "__main__":
    main()
