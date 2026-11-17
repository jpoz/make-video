"""Build timeline.json from video.json and the real voice lengths in out/voice.json.

Each scene is long enough for its voice plus a lead, a tail, and its own minimum.
Each line gets "marks": a [start, end] time for every word of its text. The times come from
out/words.json (measured by align.py) when it has the line; otherwise they are estimated from
each word's position in the text. Cues ("at" a word) and caption breaks use these marks.
With music.snap, cue times move to the nearest eighth note so sound and picture land together.
Captions are cut here once, so the burned-in captions and the .srt/.vtt files agree.

Run: python3 timeline.py   (no dependencies)
"""

import difflib
import json
import re
from pathlib import Path
from validate import load_spec, spec_hash, speech_hash, line_text, require

ROOT = Path(__file__).parent
SPEC = load_spec()
voice = json.loads((ROOT / "out/voice.json").read_text(encoding="utf-8"))
require(voice.get("spec_hash") == spec_hash(SPEC), "voice data is stale; run ./make.sh voice")
require(voice.get("speech_hash") == speech_hash(SPEC), "narration settings changed; run ./make.sh voice")
VOICE = {s["id"]: s["lines"] for s in voice["scenes"]}
TM = {"gap": 0.35, "lead": 0.5, "tail": 0.8, "min": 4.0, **SPEC.get("timing", {})}
MUSIC = {"style": "pop", "bpm": 112, "snap": True, **SPEC.get("music", {})}
BEAT = 60 / MUSIC["bpm"]
CAPTION_MAX = 58  # characters per caption cue
ALIGN = TM.get("align", True) is not False
WORDS_FILE = ROOT / "out/words.json"
WORDS = json.loads(WORDS_FILE.read_text(encoding="utf-8")).get("lines", {}) if ALIGN and WORDS_FILE.exists() else {}
WORD = re.compile(r"\S+")


def norm(word):
    """Compare words without case, punctuation, or hyphens (the same rule as align.py)."""
    return re.sub(r"[^\w']+", "", word.lower()).replace("_", "")


def marks(text, say, start, dur, heard):
    """[start, end] for each word of text. heard holds measured [word, start, end] for say.split().

    Text and say can differ ("video.json" is said "video dot jason"). Words that are the same in
    both take their own times; a run of text words that differs takes the times of the say words
    in its place, shared in order.
    """
    spans = [m.span() for m in WORD.finditer(text)]
    if heard and len(heard) == len(say.split()) and spans:
        tw, sw = [norm(text[a:b]) for a, b in spans], [norm(w) for w in say.split()]
        out = [None] * len(spans)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, tw, sw, autojunk=False).get_opcodes():
            n, m = i2 - i1, j2 - j1
            for r in range(n):
                if m == 0:  # text words that are not spoken: a moment at the gap
                    at = heard[j1][1] if j1 < len(heard) else heard[-1][2]
                    a = b = at
                else:
                    k0 = j1 + r * m // n
                    k1 = max(k0, j1 - (-(r + 1) * m // n) - 1)
                    a, b = heard[k0][1], heard[k1][2]
                out[i1 + r] = [round(start + a, 3), round(start + b, 3)]
        return out, True
    size = max(1, len(text))
    return [[round(start + dur * s / size, 3), round(start + dur * e / size, 3)] for s, e in spans], False


def char_time(line, i):
    """Film time at character i of a line's text: inside a word, part way through its mark."""
    for (s, e), (a, b) in zip((m.span() for m in WORD.finditer(line["text"])), line["marks"]):
        if i < e:
            return a + (b - a) * max(0, i - s) / max(1, e - s)
    return line["start"] + line["dur"]


def word_time(lines, word, nth=0):
    """Start of the nth match of a word (or phrase) in a scene's voice."""
    for ln in lines:
        i = -1
        while True:
            i = ln["text"].find(word, i + 1)
            if i < 0:
                break
            if nth == 0:
                return char_time(ln, i)
            nth -= 1
    raise SystemExit(f'cue word "{word}" is not in the voice lines')


def chunks(text):
    """Split a line into caption cues of at most CAPTION_MAX characters; no short last cue."""
    out, cur = [], ""
    words = [word[i:i + CAPTION_MAX] for word in text.split() for i in range(0, len(word), CAPTION_MAX)]
    for w in words:
        if cur and len(cur) + 1 + len(w) > CAPTION_MAX:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    if len(out) > 1 and len(out[-1]) < 14:
        a = out[-2].split()
        if len(a) > 1 and len(a[-1]) + 1 + len(out[-1]) <= CAPTION_MAX:
            out[-2], out[-1] = " ".join(a[:-1]), a[-1] + " " + out[-1]
    return out


scenes, events, captions, t, aligned_lines = [], [], [], 0.0, 0
for sc in SPEC["scenes"]:
    sid, S = sc["id"], t
    require(sid in VOICE, f"scene {sid}: missing voice data; run ./make.sh voice")
    require([v["text"] for v in VOICE[sid]] == [line_text(line) for line in sc.get("lines", [])], f"scene {sid}: voice lines do not match the script; run ./make.sh voice")
    lines, lt = [], S + sc.get("lead", TM["lead"])
    for v, src in zip(VOICE.get(sid, []), sc.get("lines", [])):
        require(v["dur"] > 0, f"scene {sid}: line duration must be positive")
        if SPEC.get("narration", {}).get("mode", "tts") != "none":
            require(bool(v.get("file")) and (ROOT / v["file"]).is_file(), f"scene {sid}: missing voice file; run ./make.sh voice")
        say = src if isinstance(src, str) else src.get("say", src["text"])
        heard = (WORDS.get(v.get("file") or "") or {}).get("words")
        mk, aligned = marks(v["text"], say, round(lt, 3), v["dur"], heard)
        lines.append({**v, "start": round(lt, 3), "marks": mk, "aligned": aligned})
        aligned_lines += aligned
        lt += v["dur"] + TM["gap"]
    vend = lt - TM["gap"] if lines else S
    E = max(S + sc.get("min", TM["min"]), vend + sc.get("tail", TM["tail"]))
    cues = {}
    for c in sc.get("cues", []):
        ct = (S + c["time"] if "time" in c else word_time(lines, c["at"], c.get("nth", 0))) + c.get("offset", 0.0)
        if MUSIC["snap"] and c.get("snap", "time" not in c):
            ct = round(ct / (BEAT / 2)) * (BEAT / 2)
        require(round(S, 3) <= round(ct, 3) < round(E, 3), f"cue {sid}.{c['label']}: {ct:.3f}s is outside scene {S:.3f}..{E:.3f}s; adjust offset, lead, tail, or snap")
        cues[c["label"]] = round(ct, 3)
        events.append({"t": round(ct, 3), "scene": sid, "label": c["label"], "sound": c.get("sound", "none")})
    for ln in lines:
        # each caption starts when its first word is spoken and lasts until the next one starts
        parts, at, cursor = chunks(ln["text"]), [], 0
        for p in parts:
            cursor = ln["text"].find(p.split()[0], cursor)
            at.append(char_time(ln, cursor))
            cursor += len(p.split()[0])
        at[0] = ln["start"]
        at.append(ln["start"] + ln["dur"])
        for k, p in enumerate(parts):
            captions.append({"a": round(at[k], 3), "b": round(max(at[k + 1], at[k]), 3), "text": p})
    scenes.append({
        "id": sid, "start": round(S, 3), "end": round(E, 3),
        **{k: sc[k] for k in ("chapter", "card", "music", "visual") if k in sc},
        "lines": lines, "cues": cues,
    })
    t = E

# hold each caption a little past its words, but never over the next one
for i, c in enumerate(captions):
    nxt = captions[i + 1]["a"] if i + 1 < len(captions) else t
    c["b"] = round(min(c["b"] + 0.3, nxt), 3)

tl = {
    "note": "Generated by timeline.py from video.json and out/voice.json. Do not edit by hand.",
    "spec_hash": spec_hash(SPEC),
    "speech_hash": voice["speech_hash"],
    "name": SPEC["name"], "title": SPEC.get("title", SPEC["name"]),
    "fps": SPEC.get("fps", 60), "duration": round(t, 3), "bpm": MUSIC["bpm"],
    "scenes": scenes, "events": sorted(events, key=lambda e: e["t"]),
    "captions": captions, "burn_captions": SPEC.get("captions", True),
}
(ROOT / "timeline.json").write_text(json.dumps(tl, indent=1, ensure_ascii=False), encoding="utf-8")
for s in scenes:
    print(f'{s["id"]:14} {s["start"]:7.2f} -> {s["end"]:7.2f}  ({s["end"] - s["start"]:5.2f}s)')
total_lines = sum(len(s["lines"]) for s in scenes)
timing = f"measured word times for {aligned_lines}/{total_lines} lines" if aligned_lines else "estimated word times"
print(f"duration {tl['duration']:.2f}s, {len(events)} cues, {len(captions)} captions, {timing}")
