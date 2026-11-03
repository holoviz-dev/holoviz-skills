"""Model-free tests for outreach/scripts/make_voice.py: spec handling, not speech."""

import importlib.util
import json
import pathlib

import pytest

SCRIPTS = (
    pathlib.Path(__file__).resolve().parents[1] / "contributing-to-holoviz/skills/outreach/scripts"
)


@pytest.fixture(scope="module")
def mv():
    spec = importlib.util.spec_from_file_location("make_voice", SCRIPTS / "make_voice.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lexicon_respells_whole_words_longest_first(mv):
    lexicon = {"CVEs": "see vee eez", "CVE": "see vee ee", "12 Nov": "November twelfth"}
    assert mv.spoken("blocks CVEs on 12 Nov", lexicon) == "blocks see vee eez on November twelfth"
    # inside another word or a hyphenated name, nothing changes
    assert mv.spoken("CVEscan and pre-CVE", lexicon) == "CVEscan and pre-CVE"


def test_shipped_voices_have_a_clip_and_transcript(mv):
    metas = sorted(mv.VOICES.glob("*.json"))
    assert metas, "assets/voices ships no voice"
    for meta in metas:
        data = json.loads(meta.read_text())
        assert data["text"].strip()
        wav = meta.with_suffix(".wav")
        assert wav.exists()
        assert wav.stat().st_size < 500_000, "keep shipped clips under the large-file check"


def test_shipped_voice_resolves_without_rendering(mv, tmp_path):
    spec = json.loads(json.dumps(mv.EXAMPLE))
    engine = mv.Engine(spec["voice"], tmp_path)
    (name,) = spec["voice"]["speakers"]
    ref, text, line = mv.references(spec, engine)[name]
    assert ref == mv.VOICES / "measured.wav"
    assert text == json.loads((mv.VOICES / "measured.json").read_text())["text"]
    assert line is None  # a saved clip, not one of the spec's lines


def test_unknown_shipped_voice_names_the_shipped_ones(mv, tmp_path):
    spec = {"voice": {"speakers": {"narrator": {"voice": "nope"}}}, "lines": []}
    with pytest.raises(SystemExit, match="measured"):
        mv.references(spec, mv.Engine(spec["voice"], tmp_path))


def test_cache_keys_depend_on_text_take_and_engine(mv, tmp_path):
    ref = mv.VOICES / "measured.wav"
    q8 = mv.Engine({"lang": "en"}, tmp_path)
    bf16 = mv.Engine({"lang": "en", "engine": "qwen-tts"}, tmp_path)
    a = q8.clone_path("Hello there.", ref, "ref", 1)
    assert a == q8.clone_path("Hello there.", ref, "ref", 1)
    assert a != q8.clone_path("Hello there.", ref, "ref", 2)
    assert a != q8.clone_path("Hello again.", ref, "ref", 1)
    assert a != bf16.clone_path("Hello there.", ref, "ref", 1)


def test_unknown_engine_is_refused(mv, tmp_path):
    with pytest.raises(SystemExit, match="engine"):
        mv.Engine({"engine": "llama-tts"}, tmp_path)


def test_captions_hold_after_a_line_but_never_overlap_the_next(mv):
    placed = [
        {"id": "a", "start": 0.4, "end": 2.0, "window_end": 5.0, "text": "First.", "phrases": []},
        {"id": "b", "start": 2.2, "end": 4.0, "window_end": 5.0, "text": "Second.", "phrases": []},
    ]
    a, b = mv.captions(placed)
    assert a["end"] == pytest.approx(2.15)  # held 0.4 s, cut 0.05 s before the next line
    assert b["end"] == pytest.approx(4.4)
