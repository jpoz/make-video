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
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

from validate import load_spec, spec_hash

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
    spec = load_spec()
    mode = spec.get("narration", {}).get("mode", "tts")
    engine = None
    if mode == "tts" or "--voices" in sys.argv:
        fetch()
        import numpy as np
        import onnxruntime as ort
        from kokoro_onnx import Kokoro

        engine = Kokoro.from_session(
            ort.InferenceSession(str(MODELS / FILES[0]), providers=["CPUExecutionProvider"]),
            str(MODELS / FILES[1]),
        )
    if "--voices" in sys.argv:
        print(" ".join(sorted(engine.get_voices())))
        return

    voice, speed, lang = spec.get("voice", "af_heart"), spec.get("speed", 1.0), spec.get("lang", "en-us")
    if engine and voice not in engine.get_voices():
        raise ValueError(f"unknown voice {voice!r}; run uv run tts.py --voices")
    out = ROOT / "out/voice"
    out.mkdir(parents=True, exist_ok=True)
    result = {"voice": voice, "mode": mode, "spec_hash": spec_hash(spec), "scenes": []}
    for sc in spec["scenes"]:
        lines = []
        for n, ln in enumerate(sc.get("lines", [])):
            text, say = (ln, ln) if isinstance(ln, str) else (ln["text"], ln.get("say", ln["text"]))
            if mode == "none":
                duration = ln.get("duration", max(1, len(text.split()) / 2.5)) if isinstance(ln, dict) else max(1, len(text.split()) / 2.5)
                lines.append({"text": text, "file": None, "dur": round(duration, 3)})
                continue
            key = hashlib.sha256(f"{voice}:{speed}:{lang}:{say}".encode()).hexdigest()[:12]
            if mode == "recorded":
                source = ROOT / Path(ln["audio"]).expanduser()
                key = hashlib.sha256(source.read_bytes() + json.dumps([ln.get("from", 0), ln.get("to")]).encode()).hexdigest()[:12]
            path = out / f'{sc["id"]}-{n}-{key}.wav'
            if not path.exists() and mode == "recorded":
                probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source)], check=True, capture_output=True, text=True)
                length = float(probe.stdout)
                start, end = ln.get("from", 0), ln.get("to", length)
                if not 0 <= start < end <= length + 0.001:
                    raise ValueError(f"scene {sc['id']}, line {n + 1}: recording range must be within 0..{length:.3f}s")
                part = path.with_suffix(".part.wav")
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(source), "-ss", str(start), "-t", str(end - start), "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(part)], check=True)
                os.replace(part, path)
            elif not path.exists():
                samples, rate = engine.create(say, voice=voice, speed=speed, lang=lang)
                # trim near-silence at both ends so the timing is the speech itself
                idx = np.where(np.abs(samples) > 0.01)[0]
                if not len(idx):
                    raise ValueError(f"scene {sc['id']}, line {n + 1}: generated speech is silent; change say")
                samples = samples[max(0, idx[0] - int(0.03 * rate)) : idx[-1] + int(0.08 * rate)]
                part = path.with_suffix(".part.wav")
                with wave.open(str(part), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
                    w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
                os.replace(part, path)
            with wave.open(str(path)) as w:
                dur = w.getnframes() / w.getframerate()
            if dur < 0.001:
                raise ValueError(f"scene {sc['id']}, line {n + 1}: audio is empty")
            lines.append({"text": text, "file": str(path.relative_to(ROOT)), "dur": round(dur, 3)})
            print(f'{sc["id"]:14} {dur:5.2f}s  {text}')
        result["scenes"].append({"id": sc["id"], "lines": lines})
    (ROOT / "out/voice.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"voice failed: {error}") from error
