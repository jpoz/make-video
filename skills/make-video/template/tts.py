# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["kokoro-onnx==0.4.9", "numpy", "soundfile"]
# ///
"""Voice-over: one Kokoro WAV per line of video.json. Local, free, no API key.

Writes out/voice/<scene>-<n>-<hash>.wav and out/voice.json (line lengths in seconds).
Lines are cached by their spoken text, so editing one line re-renders only that line.
A line is a string, or {"text": caption form, "say": spoken form} when they differ
(code names, acronyms, file names: "video.json" is said "video dot jason").

The model (~115 MB) downloads once to $MAKE_VIDEO_MODELS (default ~/.cache/make-video/models).
Run: uv run tts.py            List voices: uv run tts.py --voices
"""

import hashlib
import json
import os
import sys
import urllib.request
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
MODELS = Path(os.environ.get("MAKE_VIDEO_MODELS", Path.home() / ".cache/make-video/models"))
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ["kokoro-v1.0.int8.onnx", "voices-v1.0.bin"]


def fetch():
    MODELS.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        p = MODELS / f
        if not p.exists():
            print(f"downloading {f} ...", file=sys.stderr)
            urllib.request.urlretrieve(BASE + f, str(p) + ".part")
            os.replace(str(p) + ".part", p)


def main():
    fetch()
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    engine = Kokoro.from_session(
        ort.InferenceSession(str(MODELS / FILES[0]), providers=["CPUExecutionProvider"]),
        str(MODELS / FILES[1]),
    )
    if "--voices" in sys.argv:
        print(" ".join(sorted(engine.get_voices())))
        return

    spec = json.loads((ROOT / "video.json").read_text())
    voice, speed, lang = spec.get("voice", "af_heart"), spec.get("speed", 1.0), spec.get("lang", "en-us")
    out = ROOT / "out/voice"
    out.mkdir(parents=True, exist_ok=True)
    result = {"voice": voice, "scenes": []}
    for sc in spec["scenes"]:
        lines = []
        for n, ln in enumerate(sc.get("lines", [])):
            text, say = (ln, ln) if isinstance(ln, str) else (ln["text"], ln.get("say", ln["text"]))
            key = hashlib.sha256(f"{voice}:{speed}:{lang}:{say}".encode()).hexdigest()[:12]
            path = out / f'{sc["id"]}-{n}-{key}.wav'
            if not path.exists():
                samples, rate = engine.create(say, voice=voice, speed=speed, lang=lang)
                # trim near-silence at both ends so the timing is the speech itself
                idx = np.where(np.abs(samples) > 0.01)[0]
                samples = samples[max(0, idx[0] - int(0.03 * rate)) : idx[-1] + int(0.08 * rate)]
                with wave.open(str(path), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
                    w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
            with wave.open(str(path)) as w:
                dur = w.getnframes() / w.getframerate()
            lines.append({"text": text, "file": str(path.relative_to(ROOT)), "dur": round(dur, 3)})
            print(f'{sc["id"]:14} {dur:5.2f}s  {text}')
        result["scenes"].append({"id": sc["id"], "lines": lines})
    (ROOT / "out/voice.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
