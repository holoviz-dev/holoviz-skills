# Adding Voice and Music

Narration, captions, music and sound effects for a demo or explainer video
built on the [HTML contract](making-a-demo-video.md#the-html-contract). Feeds
autoplay muted, so add audio only when the user asks, deliver the silent cut
first, and let no sound carry a claim the picture doesn't.

## Contents

- [Narration](#narration)
- [Captions](#captions)
- [Music](#music)
- [Sound effects](#sound-effects)
- [Mixing and loudness](#mixing-and-loudness)

Every script here caches or reproduces its output from a spec, so commit the
spec and the script call, not the audio. You can't hear any of it: hand the
user the file and change the spec from their words.

## Narration

Write a narration spec and render it with
[`scripts/make_voice.py`](scripts/make_voice.py), which runs the local
Qwen3-TTS models through `faster-qwen3-tts`. Every speaker has one reference
take, and the Base model clones it for every line. Start from the voice this
skill ships, `"measured"`: a calm, quietly confident developer presenting at
a conference, the same clip on every machine.

```json
{
  "voice": {"lang": "en",
            "speakers": {"narrator": {"voice": "measured"}}},
  "lead": 0.4, "tail": 0.5, "loudness": -16,
  "timeline": {"bar": 0.1, "gap": 0.3, "pad": 0.7},
  "lexicon": {"hvPlot": "H V plot", "HoloViz": "holo viz"},
  "lines": [
    {"id": "open", "scene": "open", "text": "This diff does a lot, so let's look at what we can trim."},
    {"id": "keep", "scene": "keep", "text": "The docs already prefer speakers, so let's keep that one and let the other four go."}
  ]
}
```

```bash
python scripts/make_voice.py narration.json --out voice.wav --srt voice.srt --json voice.json
python scripts/make_voice.py narration.json --line keep --takes 4   # audition one line
python scripts/make_voice.py narration.json --pick 3                # steadiest take of every line
```

- **One speaker per voice, also for one narrator.** A speaker is
  `{"voice": name}` (a clip in [`assets/voices`](assets/voices/measured.json),
  with its transcript and the description it was designed from beside it),
  `{"line": id, "design": {"instruct": ...}, "take": n}` (that line rendered
  from a description) or `{"audio": path, "text": ...}` (a saved clip and its
  exact transcript). A line without `"speaker"` belongs to the first one.
  The clone step gets the reference's transcript as well as its audio, which
  carries the reference's delivery into every line along with its timbre.
  `voice.design` holds defaults shared by every speaker's design.
- **A description doesn't reproduce a voice; the clip does.** VoiceDesign
  has no seed, and the same description and take give a different voice on
  another machine or toolchain version. Once the user likes a designed voice,
  copy its reference take to `voices/<name>.wav` and switch the speaker to
  `{"audio": ..., "text": ...}`; before that, rewriting the reference line
  changes the voice. Commit the WAV when others must get the same voice. A
  voice the whole project should share goes in `assets/voices/` as
  `<name>.wav` plus `<name>.json` (`text`, `instruct`, how it was made), and
  keep the clip under the 500 KB large-file check: about 5 s of 48 kHz mono.
- **Pick the reference for its delivery.** Every clone inherits it, and a
  flat statement as the reference gives a flat speaker. Use the speaker's
  liveliest line (a reveal, a question, a reaction).
- **Describe a person, not a timbre.** Say who is speaking, to whom and
  where: "a man in his late thirties co-hosting a relaxed explainer podcast,
  natural American accent, warm mid-low voice, lively intonation", and say
  what to avoid ("never corporate", "not an announcer", "never squeaky or
  cartoonish"). "Bright", "bubbly" or "reacts with surprise" drifts toward a
  high, cartoonish voice. A brand voice (Anaconda's is a curious,
  encouraging guide) becomes a person in a scene: "showing a teammate
  something neat she found", not "professional and confident", which reads
  as a corporate announcer. Don't describe or name a real person.
- **Pick the voice by measurement, then by ear.** You can't hear the takes,
  but you can measure each take's median pitch and how much it moves (the
  standard deviation in semitones around the median). Natural speaking pitch
  is about 165–255 Hz for a woman and 85–180 Hz for a man; a take far above
  that sounds cartoonish. Movement is liveliness: under about 2.5 semitones
  sounds flat or robotic, 3–4 calm and even, and 5–6 an enthusiastic
  presenter, which reviewers of a technical walkthrough found too lively.
  `--line <reference> --takes 4` renders candidate voices; keep the ones in
  range nearest the energy the user wants, and let them choose by ear.
- **For a calmer voice, change three things together:** describe the
  delivery ("measured and even, speaks steadily without hype, never
  excited"), make a plain statement the reference line, and pick for
  moderate movement. Lowering `design.temp` to 0.5 flattens it further,
  toward robotic. Calm and experienced descriptions drift low and male; say
  "woman" or "mid-range voice" when that matters.
- **Let the narration set the timeline** whenever the screens can move.
  Fixed scene times leave each screen silent for however long its line falls
  short, and viewers hear those waits as the video stalling. Give lines a
  `"scene"` and no `"t"`: a scene's first line starts `lead` s into it, its
  lines follow `timeline.gap` s apart, and it ends `pad` s after its last
  line, rounded up to `timeline.bar`.
  `make_voice.py` writes the scene times to `--timeline timeline.json` for
  the page and the score to read. Without music, use a `bar` of 0.1 and a
  `pad` of about 0.7 (about 1.1 s from one line to the next); with music,
  keep `bar` equal to the music's bar (3 s at 80 BPM). Use `"t"` only when
  the picture can't move, such as footage cut to a fixed length.
- **Write one walkthrough, not a line per screen.** Each line picks up from
  the last ("Start with…", "Then there are two spots…", "After that…",
  "So that's…"); lines that each open fresh ("First up", "Now", "Oh, and")
  sound like separate recordings however steady the voice. Keep lines to one
  thought of similar length. A two-part quip ("Nine entries? It's really
  three.") puts half a second of silence mid-line, and a run of them chops
  the narration up. Open with a hook the viewer recognizes ("Ever plotted a
  big dataset and just gotten a blob? Let's fix that."). For a two-host
  conversation, short reactions ("Right.", "Exactly.") as their own lines,
  with `timeline.gap` 0.25, make it sound like talk.
- **Pick each line's take with `--pick`.** Clones of one reference still
  vary from line to line, in pace (2.4–3.6 words a second in one narration)
  and in pitch (one line 3 semitones above the rest sounds like another
  speaker), and that swing breaks the flow. `--pick 6` renders takes 1–6 of
  every line in one model load per speaker, keeps the take nearest the
  median pace and the reference's pitch with no pause over 0.45 s, and
  writes the choices into the spec as `"take"`. On the shipped voice it
  kept all eight lines within 114–124 Hz.
- **Cut the reference from the narration the user chose.** The user judges
  a voice by its lines, which are clones and drift from a designed
  reference take. Once they pick a narration, cut whole lines of it (about
  10 s, at 24 kHz to stay under the 500 KB check) from its voice track, not
  the compressed MP4, with their exact spoken transcript, and make that the
  reference.
- **Visuals follow the speech, not the other way around.** `voice.json` holds
  each line's phrases, split at sentence ends, colons and ellipses and timed
  from the pauses in the take (by character count when a pause is too short
  to find). Time each visual event to the word that names it: a helper like
  `at(scene, word, fallback)` finds the phrase containing the word and
  estimates the word's time from its position. Expose the event times as
  `window.EVENTS` so the build can place sound effects on them.
- **The voice repeats the screen.** A line says about what the headline says,
  in one sentence; don't read code aloud, and run the lines through deslop.
- **With fixed times, fit the line to the screen, not the voice to the
  line.** Each line starts `lead` s after its screen. When a line runs past
  `tail` s before the next screen, the script prints how many words fit at
  this voice's pace; cut words, because sped-up speech sounds wrong.
- **Pauses come from punctuation inside a line and from `timeline.gap`
  between lines.** The prompt is just the line: each ellipsis or colon adds
  0.3–0.5 s and slows the words around it, a full stop adds a short beat,
  and dropping commas removes pauses and speeds the read up. For a pause
  that must land (a beat between a problem and its fix, before the
  product's name appears), split the line into two lines in the same scene:
  `timeline.gap` (0.5 s) then sets the silence exactly, and each half gets
  its own take.
- **Respell anything the model might read wrong** in `lexicon`, which
  changes only what the model hears; captions keep the on-screen spelling.
  Spell acronyms the way they're said, not letter by letter with spaces:
  `"CVEs": "see vee eez"`, `"CISO": "see-so"` (`"C V Es"` came out wrong).
  Write out dates and symbols: `"12 Nov": "November twelfth"`,
  `"500+": "five hundred plus"`. Listen to every respelled line once.
- Every line is levelled to the target before mixing, because clones of
  the same reference can differ by several dB.
- **Check the words.** TTS models sometimes drop or repeat words. If
  whisper.cpp is installed, transcribe the voice track and compare it with
  the spec.
- **Install and locate the engine.** `uv tool install faster-qwen3-tts` (it
  shares the Hugging Face cache, so weights aren't downloaded twice). The
  script looks in `$FASTER_QWEN3_TTS`, then PATH, then beside the running
  Python and in conda envs, and runs it with `--backend ggml --quant Q8_0`:
  on Apple silicon GGML's Metal library has no `kernel_get_rows_bf16`, so
  `--quant BF16` segfaults, and `--backend torch` needs CUDA graphs. Each
  speaker's uncached lines go through one `faster-qwen3-tts serve` process,
  because model loads, not speech, dominate short lines.
- **bf16 is optional.** `"engine": "qwen-tts"` in `voice` renders the same
  spec in the models' native bf16 through the official `qwen-tts` package
  ([`scripts/_qwen_tts_bf16.py`](scripts/_qwen_tts_bf16.py), on Apple's GPU,
  CUDA or CPU), which avoids Q8_0's quantization but is slower. It needs its
  own venv (`pip install qwen-tts soundfile`, since it pins its own
  transformers) at `~/.venvs/qwen-tts` or `$QWEN_TTS_PYTHON`. Takes are
  cached per engine, so switching re-renders every line; a saved `"audio"`
  reference keeps the voice, and only the clones change.
- Check the models' licenses.

## Captions

`make_voice.py` writes an SRT and a JSON of cue times measured from the takes.

- **Soft track and sidecar.** `record_video.py --srt` embeds the SRT as a
  `mov_text` track; also upload the SRT beside the video, since LinkedIn and X
  ignore embedded tracks.
- **Burned in,** for feeds that show no captions: draw the JSON cues in the
  HTML as a function of `t` (shown with `?captions=1`), and let
  `record_video.py --burn-captions` overlay them on the plain cut, so there's
  no second recording.
- Captions sit below the picture. Let the browser wrap them
  (`text-wrap: balance`) rather than keeping the SRT's line breaks, which leave
  one-word lines.

## Music

Render a score with [`scripts/make_music.py`](scripts/make_music.py). Start
from the `lofi-jazz` preset with only the scene times:

```json
{"preset": "lofi-jazz", "duration": 54, "seed": "my-video",
 "scenes": [0, 6, 12, 18, 24, 30, 36, 42, 48]}
```

```bash
python scripts/make_music.py score.json --out music.wav
python scripts/make_music.py --preset lofi-jazz --scenes 0,6,12 --duration 18
```

The preset fits the tempo so every scene starts on a bar line (80 BPM for 6 s
scenes), plays ii9–V9–Imaj9–vi9 with off-beat comping, swung hats and vinyl
texture, starts with pad, keys and bass, adds drums from the second scene and
resolves on the last. A preset render checks itself for 6 LU jumps and
lowers the offending section's gain until none is left (`--fix` does the
same for a hand-written spec), so don't tune gains unless the user asks.
Change `seed` for another take with the same structure, and cache the WAV by
a hash of the spec so later builds skip it.

For a calmer, documentary feel use `"preset": "cinematic"`: D lydian at
80 BPM half-time, I–V–vi–IV one bar per chord, pad, keys and bass from the
start, a rising motif from the second scene, a swell on the scene before the
close, and no drums. Two bars per chord stretched the opening fade-in into a
jump warning; the jump check ignores the deliberate two-bar fade-in at the
start of the track.

Write `sections` by hand (`--example` prints a full spec) only when the user
wants a specific arrangement:

- **Tempo and sections from the beat sheet.** One section per scene change,
  each on a bar line; fix a bar-line warning by changing `bpm`, not the
  picture's times. Scenes 10–14 s apart on even seconds fit 120 BPM with
  `"feel": "half"`.
- **A motif per concept** in `motifs` (scale degrees, or `"pulse"`), added to
  `layers` where that concept first appears on screen.
- **Build from a full start.** A lone pad followed by a new layer trips the
  6 LU jump warning; start with two or three layers instead.
- **The payoff** gets `"layers": "all"`, `"swell": true` and a little `gain`;
  **the close** gets `"resolve": true`, which holds the tonic while the music
  fades over the last 3 s.
- **Mood picks `key`, `mode` and `texture`:** major or `lydian` around 0.5
  for an explainer, `major` or `mixolydian` with less texture for a launch.

If the user would rather have a produced track, a platform library track
(LinkedIn, YouTube) avoids licensing questions.

## Sound effects

[`scripts/make_sfx.py`](scripts/make_sfx.py) generates original effects, so
they carry the repository's license and need no credit.

```bash
python scripts/make_sfx.py --list             # names and what each is for
python scripts/make_sfx.py --out sfx/         # every sound + all-sounds.wav
python scripts/make_sfx.py bubble --pitch -2  # retune after feedback
```

- **Each effect marks an event already on screen,** at that frame. When the
  page exposes `window.EVENTS`, read the times from it in the build rather
  than typing them, so effects stay on their events when the narration
  moves them. Put them
  in the score's `hits` as `[sound, t, LU]` (LU above the music just before,
  default 3, capped at 6) so the music ducks under each one. Keep hits out of
  narration.
- Don't imitate a recognizable app, phone or game sound. Sounds from elsewhere
  need a commercial-use license (CC0; never NonCommercial or NoDerivatives)
  and a row in a
  `SOURCES.md` beside the HTML.

## Mixing and loudness

The scripts master through `scripts/_mastering.py` and `scripts/_ffmpeg.py`,
so nothing clips or startles; a sudden loud moment is the fastest way to lose
a viewer.

- **Duck the music under the voice** with a sidechain from the voice track,
  then level the mix to −16 LUFS integrated with true peaks under −1.5 dBFS.
  `_ffmpeg.loudnorm(out, -16, graph, [music, voice])` takes a graph ending in
  `[pre]`:

  ```text
  [1]aformat=channel_layouts=stereo,asplit[vsc][vmix];
  [0][vsc]sidechaincompress=threshold=0.015:ratio=6:attack=40:release=600[bed];
  [bed][vmix]amix=inputs=2:normalize=0:duration=first[pre]
  ```

- **Levels:** voice at −16 LUFS; music alone at −20 to −22 under a voice, −16
  to −20 without one, and lower for a video watched at a desk or on a call.
- **Don't hand over a score that still prints a warning** (a 6 LU jump within
  3 s, or a peak 10 LU over the average); fix the spec first.
