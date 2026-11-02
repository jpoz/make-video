# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["kokoro-onnx==0.4.9", "numpy", "soundfile"]
# ///
"""Voice-over: one WAV per line of video.json, via narrate or local Kokoro.

GEMINI_API_KEY selects the narrate command; otherwise speech uses local Kokoro.

Writes out/voice/<scene>-<n>-<hash>.wav and out/voice.json (line lengths in seconds).
Lines are cached by their spoken text, so editing one line re-renders only that line.
A line is a string, or {"text": caption form, "say": spoken form} when they differ
(code names, acronyms, file names: "video.json" is said "video dot jason").

For local speech, the model (~115 MB) downloads once to $MAKE_VIDEO_MODELS
(default ~/.cache/make-video/models).
Run: ./make.sh voice    Local voices: uv run tts.py --voices    Gemini voices: narrate -voices
"""

import array
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path

from validate import load_spec, spec_hash, speech_settings, speech_hash

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


def narrate_line(say, path, settings):
    """Send spoken text on stdin; publish only a complete, validated PCM WAV."""
    with tempfile.TemporaryDirectory(prefix="narrate-", dir=path.parent) as scratch:
        raw = Path(scratch) / "speech.wav"
        part = Path(scratch) / "normalized.wav"
        command = [settings["command"], "-q", "-f", "-", "-o", str(raw)]
        for key in ("voice", "model", "style"):
            if settings[key] or key == "style":
                command.extend([f"-{key}", settings[key]])
        result = subprocess.run(command, input=say, capture_output=True, text=True)
        if result.returncode:
            detail = result.stderr.strip()
            for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                if os.environ.get(name):
                    detail = detail.replace(os.environ[name], "[redacted]")
            raise ValueError(f"narrate exited {result.returncode}: {detail}")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw),
                        "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(part)], check=True)
        with wave.open(str(part), "rb") as audio:
            samples = array.array("h", audio.readframes(audio.getnframes()))
            if not any(samples):
                raise ValueError("narrate returned empty or silent audio; change the text or delivery style")
        os.replace(part, path)


def main():
    spec = load_spec()
    mode = spec.get("narration", {}).get("mode", "tts")
    settings = speech_settings(spec)
    backend = settings["provider"]
    if backend == "narrate" and "--voices" not in sys.argv and not settings["command"]:
        raise ValueError("GEMINI_API_KEY is set, but narrate is not on PATH; install narrate or unset GEMINI_API_KEY to use local voices")
    engine = None
    if backend == "kokoro" or "--voices" in sys.argv:
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
    result = {"voice": settings.get("voice", voice), "mode": mode, "provider": backend,
              "spec_hash": spec_hash(spec), "speech_hash": speech_hash(spec), "scenes": []}
    if mode == "tts":
        print(f"speech provider: {backend}")
    for sc in spec["scenes"]:
        lines = []
        for n, ln in enumerate(sc.get("lines", [])):
            text, say = (ln, ln) if isinstance(ln, str) else (ln["text"], ln.get("say", ln["text"]))
            if mode == "none":
                duration = ln.get("duration", max(1, len(text.split()) / 2.5)) if isinstance(ln, dict) else max(1, len(text.split()) / 2.5)
                lines.append({"text": text, "file": None, "dur": round(duration, 3)})
                continue
            key = hashlib.sha256(json.dumps([settings, say], sort_keys=True).encode()).hexdigest()[:12]
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
            elif not path.exists() and backend == "narrate":
                narrate_line(say, path, settings)
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
    except (ValueError, OSError, wave.Error, EOFError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"voice failed: {error}") from error
