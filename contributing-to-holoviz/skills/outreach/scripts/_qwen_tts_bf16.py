"""Render Qwen3-TTS jobs in bf16 with the official qwen-tts package (run in its own venv).

make_voice.py calls this with a JSON list of jobs on stdin and waits:

    [{"kind": "design", "text": ..., "instruct": ..., "language": "English", "out": "a.wav"},
     {"kind": "clone", "text": ..., "ref_audio": "ref.wav", "ref_text": ...,
      "language": "English", "out": "b.wav"}]

Each model loads once per call, and each clone reference is turned into a
voice-clone prompt once. bf16 runs on Apple's GPU (mps), CUDA or CPU; unlike
GGML's Metal backend it has the bf16 kernels. Set it up once, in a venv of
its own because qwen-tts pins its own transformers:

    python -m venv ~/.venvs/qwen-tts
    ~/.venvs/qwen-tts/bin/pip install qwen-tts soundfile

or point ``QWEN_TTS_PYTHON`` at another venv's python.
"""

import json
import sys

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODELS = {
    "design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}
device = (
    "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
)
jobs = json.load(sys.stdin)
for kind in ("design", "clone"):
    todo = [j for j in jobs if j["kind"] == kind]
    if not todo:
        continue
    model = Qwen3TTSModel.from_pretrained(MODELS[kind], device_map=device, dtype=torch.bfloat16)
    prompts = {}
    for j in todo:
        if kind == "design":
            wavs, sr = model.generate_voice_design(
                text=j["text"], instruct=j["instruct"], language=j["language"]
            )
        else:
            key = (j["ref_audio"], j["ref_text"])
            if key not in prompts:
                prompts[key] = model.create_voice_clone_prompt(
                    ref_audio=j["ref_audio"], ref_text=j["ref_text"]
                )
            wavs, sr = model.generate_voice_clone(
                text=j["text"], language=j["language"], voice_clone_prompt=prompts[key]
            )
        sf.write(j["out"], wavs[0], sr)
        print(f"{kind}: {j['out']}", flush=True)
    del model
