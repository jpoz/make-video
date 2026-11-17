# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["faster-whisper==1.2.1"]
# ///
"""Word timing: measure when each spoken word starts and ends in every voice line.

Reads out/voice.json, listens to each line's WAV with a small Whisper model, and matches the
words it hears to the line's spoken text ("say"). Writes out/words.json:

    {"model": "base.en", "lines": {"out/voice/intro-0-ab12.wav": {"words": [["This", 0.03, 0.21], ...], "matched": 0.95}}}

Times are seconds from the start of the line's file. Words that were not heard clearly get times
between their heard neighbours. A line where fewer than half of the words match is stored with
"words": null, and timeline.py uses its text-position estimate for that line.

Lines are cached by file name (the name contains a hash of the speech), so only new lines are measured.
The model (~150 MB) downloads once to $MAKE_VIDEO_MODELS/whisper (default ~/.cache/make-video/models).
Any failure here is a warning, not an error: the film still builds with estimated word times.

Run: ./make.sh voice   (or uv run align.py; turn off with "timing": {"align": false})
"""

import difflib
import json
import os
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).parent
MODELS = Path(os.environ.get("MAKE_VIDEO_MODELS", Path.home() / ".cache/make-video/models"))
VERSION = 1  # bump when the matching changes, so cached results are measured again
MIN_MATCH = 0.5


def norm(word):
    """Compare words without case, punctuation, or hyphens: "Make-video," == "makevideo"."""
    return re.sub(r"[^\w']+", "", word.lower()).replace("_", "")


def load_audio(path):
    """A voice WAV (16-bit PCM, any rate, mono or stereo) as 16 kHz mono float32, which Whisper expects."""
    import numpy as np

    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path.name}: expected 16-bit PCM")
        rate, channels = w.getframerate(), w.getnchannels()
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16000 and len(samples):
        n = max(1, round(len(samples) * 16000 / rate))
        samples = np.interp(np.arange(n) * rate / 16000, np.arange(len(samples)), samples).astype(np.float32)
    return samples


def model_for(lang):
    """Whisper model and language code for a Kokoro-style language such as en-us or fr-fr."""
    code = {"cmn": "zh"}.get(lang.split("-")[0].lower(), lang.split("-")[0].lower())
    if code == "en":
        return "base.en", "en"
    return "base", code if len(code) == 2 else None


def match(say, heard, dur):
    """Give every word of `say` a [start, end] time from the `heard` (word, start, end) list.

    Returns (words, matched): words is [[word, start, end], ...] for say.split(), and matched is
    the fraction of say words that were heard exactly. Returns (None, matched) below MIN_MATCH.
    """
    words = say.split()
    if not words:
        return None, 0.0
    a, b = [norm(w) for w in words], [norm(h[0]) for h in heard]
    times, exact = [None] * len(words), 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        # equal runs match word for word; a replaced run of the same length is the same words heard differently
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = [heard[j1 + k][1], heard[j1 + k][2]]
            if op == "equal":
                exact += i2 - i1
    matched = exact / len(words)
    if matched < MIN_MATCH:
        return None, matched
    # words between two anchors share the gap in proportion to their length
    i = 0
    while i < len(words):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and times[j] is None:
            j += 1
        left = times[i - 1][1] if i > 0 else 0.0
        right = times[j][0] if j < len(words) else dur
        right = max(left, right)
        weights = [len(w) + 1 for w in words[i:j]]
        total, t = sum(weights), left
        for k, w in zip(range(i, j), weights):
            step = (right - left) * w / total
            times[k] = [t, t + step]
            t += step
        i = j
    # keep times inside the file and in order
    out, last = [], 0.0
    for w, (s, e) in zip(words, times):
        s = min(max(s, last, 0.0), dur)
        e = min(max(e, s), dur)
        out.append([w, round(s, 3), round(e, 3)])
        last = s
    return out, round(matched, 3)


def main():
    sys.path.insert(0, str(ROOT))
    from validate import load_spec, line_text

    spec = load_spec()
    if spec.get("narration", {}).get("mode", "tts") == "none" or spec.get("timing", {}).get("align", True) is False:
        return
    voice = json.loads((ROOT / "out/voice.json").read_text(encoding="utf-8"))
    model_name, language = model_for(spec.get("lang", "en-us"))
    path = ROOT / "out/words.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    keep = old.get("model") == model_name and old.get("version") == VERSION
    cached = old.get("lines", {}) if keep else {}

    jobs = []
    for sc_voice, sc in zip(voice["scenes"], spec["scenes"]):
        for v, ln in zip(sc_voice["lines"], sc.get("lines", [])):
            say = ln if isinstance(ln, str) else ln.get("say", line_text(ln))
            if v.get("file"):
                jobs.append((v["file"], say, v["dur"]))

    result = {"note": "Generated by align.py. Do not edit by hand.", "model": model_name, "version": VERSION, "lines": {}}
    todo = [j for j in jobs if j[0] not in cached]
    model = None
    if todo:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=str(MODELS / "whisper"))
        except Exception as error:  # missing package, no network for the first download, bad model file
            print(f"word timing is off for {len(todo)} lines: {error}", file=sys.stderr)
            print("cues and captions use estimated word times; set \"timing\": {\"align\": false} to stop trying", file=sys.stderr)
    weak = 0
    for file, say, dur in jobs:
        if file in cached:
            result["lines"][file] = cached[file]
        elif model is not None:
            try:
                segments, _ = model.transcribe(load_audio(ROOT / file), language=language, word_timestamps=True, beam_size=5,
                                               initial_prompt=say, condition_on_previous_text=False, vad_filter=False)
                heard = [(w.word.strip(), w.start, w.end) for s in segments for w in (s.words or [])]
            except Exception as error:  # a bad file must not stop the build; the line keeps its estimate
                print(f"word timing failed for {file}: {error}", file=sys.stderr)
                continue
            words, matched = match(say, heard, dur)
            result["lines"][file] = {"words": words, "matched": matched}
            if words is None:
                weak += 1
                print(f"word timing: only {matched:.0%} of the words matched in {file}; it uses estimates", file=sys.stderr)
        if file in result["lines"] and result["lines"][file]["words"] is None and file in cached:
            weak += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part.json")
    tmp.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    measured = sum(1 for v in result["lines"].values() if v["words"])
    print(f"word timing: {measured}/{len(jobs)} lines measured ({model_name})" + (f", {weak} use estimates" if weak else ""))


if __name__ == "__main__":
    main()
