"""Validate project inputs before voice generation or rendering. Standard library only."""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, label, minimum=0, positive=False):
    require(type(value) in (int, float) and math.isfinite(value), f"{label}: expected a finite number")
    require(value > minimum if positive else value >= minimum, f"{label}: must be {'greater than' if positive else 'at least'} {minimum}")


def line_text(line):
    return line if isinstance(line, str) else line["text"]


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def speech_settings(spec):
    """Resolve the selected provider and non-secret settings for cache checks."""
    mode = spec.get("narration", {}).get("mode", "tts")
    if mode != "tts":
        return {"provider": mode}
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        return {"provider": "kokoro", "voice": spec.get("voice", "af_heart"),
                "speed": spec.get("speed", 1.0), "lang": spec.get("lang", "en-us")}
    options = spec.get("narration", {}).get("narrate", {})
    command = shutil.which("narrate")
    stamp = None
    if command:
        stat = Path(command).stat()
        stamp = [stat.st_size, stat.st_mtime_ns]
    return {"provider": "narrate", "command": command, "command_stamp": stamp,
            **{name: options.get(name, os.environ.get(f"NARRATE_{name.upper()}", ""))
               for name in ("voice", "model", "style")}}


def speech_hash(spec):
    return spec_hash(speech_settings(spec))


def load_spec(root=ROOT):
    spec = json.loads((root / "video.json").read_text(encoding="utf-8"))
    require(isinstance(spec, dict), "video.json: expected an object")
    require(isinstance(spec.get("name"), str) and SAFE_NAME.fullmatch(spec["name"]), "name: use letters, digits, hyphens, or underscores; start with a letter or digit")
    require(spec["name"] not in {"video", "clip", "clip-silent"}, "name: video, clip, and clip-silent are reserved for intermediate renders")
    for field in ("title", "voice", "lang", "source"):
        if field in spec:
            require(isinstance(spec[field], str) and spec[field].strip(), f"{field}: expected nonempty text")
    if "captions" in spec:
        require(type(spec["captions"]) is bool, "captions: expected true or false")
    fps = spec.get("fps", 60)
    require(type(fps) is int and 1 <= fps <= 120, "fps: expected an integer from 1 to 120")
    number(spec.get("speed", 1), "speed", positive=True)
    output = spec.get("output", {})
    require(isinstance(output, dict), "output: expected an object")
    require(output.get("format", "landscape") in ("landscape", "portrait", "square"), "output.format: use landscape, portrait, or square")
    require(output.get("quality", "final") in ("preview", "final"), "output.quality: use preview or final")
    workers = output.get("workers", 2)
    require(type(workers) is int and 1 <= workers <= 32, "output.workers: expected an integer from 1 to 32")
    narration = spec.get("narration", {})
    require(isinstance(narration, dict), "narration: expected an object")
    mode = narration.get("mode", "tts")
    require(mode in ("tts", "recorded", "none"), "narration.mode: use tts, recorded, or none")
    narrate = narration.get("narrate", {})
    require(isinstance(narrate, dict), "narration.narrate: expected an object")
    require(set(narrate) <= {"voice", "model", "style"}, "narration.narrate: use voice, model, or style")
    for key, value in narrate.items():
        require(isinstance(value, str) and (key == "style" or value.strip()),
                f"narration.narrate.{key}: expected {'text' if key == 'style' else 'nonempty text'}")
    music = spec.get("music", {})
    require(isinstance(music, dict), "music: expected an object")
    require(music.get("style", "pop") in ("pop", "chip", "none"), "music.style: use pop, chip, or none")
    number(music.get("bpm", 112), "music.bpm", positive=True)
    if "seed" in music:
        require(type(music["seed"]) is int and 0 <= music["seed"] <= 2**53 - 1,
                "music.seed: expected an integer from 0 to 9007199254740991")
    if "snap" in music:
        require(type(music["snap"]) is bool, "music.snap: expected true or false")
    timing = spec.get("timing", {})
    require(isinstance(timing, dict), "timing: expected an object")
    for key in ("gap", "lead", "tail", "min"):
        if key in timing:
            number(timing[key], f"timing.{key}", positive=key == "min")
    brief = spec.get("brief", {})
    require(isinstance(brief, dict), "brief: expected an object")
    require(isinstance(brief.get("lede", ""), str), "brief.lede: expected text")
    for key in ("approach", "questions"):
        require(isinstance(brief.get(key, []), list) and all(isinstance(x, str) for x in brief.get(key, [])), f"brief.{key}: expected a list of text values")
    scenes = spec.get("scenes")
    require(isinstance(scenes, list) and scenes, "scenes: provide at least one scene")
    ids = set()
    for scene in scenes:
        require(isinstance(scene, dict), "scenes: each scene must be an object")
        sid = scene.get("id")
        require(isinstance(sid, str) and SAFE_NAME.fullmatch(sid), "scene.id: use letters, digits, hyphens, or underscores")
        require(sid not in ids, f"scene {sid}: duplicate id")
        ids.add(sid)
        for key in ("lead", "tail", "min"):
            if key in scene:
                number(scene[key], f"scene {sid}.{key}", positive=key == "min")
        if "card" in scene:
            card = scene["card"]
            require(isinstance(card, dict) and isinstance(card.get("title"), str) and card["title"].strip(), f"scene {sid}.card: provide a title")
            require(isinstance(card.get("kicker", ""), str), f"scene {sid}.card.kicker: expected text")
        if "chapter" in scene:
            require(isinstance(scene["chapter"], str), f"scene {sid}.chapter: expected text")
        if "visual" in scene:
            visual = scene["visual"]
            require(isinstance(visual, dict) and isinstance(visual.get("title"), str), f"scene {sid}.visual: provide a title")
            require(isinstance(visual.get("items"), list) and visual["items"] and all(isinstance(item, str) and item.strip() for item in visual["items"]), f"scene {sid}.visual.items: provide a nonempty list of text values")
        energy = scene.get("music", 0.7)
        if isinstance(energy, dict):
            require(set(energy) <= {"keys", "bass", "kick", "mar", "clap", "hat"}, f"scene {sid}.music: unknown layer")
        for value in energy.values() if isinstance(energy, dict) else [energy]:
            number(value, f"scene {sid}.music")
            require(value <= 1, f"scene {sid}.music: must be at most 1")
        lines = scene.get("lines", [])
        require(isinstance(lines, list), f"scene {sid}.lines: expected a list")
        for index, line in enumerate(lines):
            label = f"scene {sid}, line {index + 1}"
            require(isinstance(line, str) or isinstance(line, dict) and "text" in line, f"{label}: provide text")
            require(isinstance(line_text(line), str) and line_text(line).strip(), f"{label}: text must not be empty")
            if isinstance(line, dict):
                require(isinstance(line.get("say", line["text"]), str) and line.get("say", line["text"]).strip(), f"{label}: say must not be empty")
                if "duration" in line:
                    number(line["duration"], f"{label}.duration", positive=True)
            if mode == "recorded":
                require(isinstance(line, dict) and isinstance(line.get("audio"), str), f"{label}: recorded mode needs an audio file")
                require((root / Path(line["audio"]).expanduser()).is_file(), f"{label}: audio file does not exist: {line['audio']}")
                number(line.get("from", 0), f"{label}.from")
                if "to" in line:
                    number(line["to"], f"{label}.to", line.get("from", 0), positive=True)
        cues = scene.get("cues", [])
        require(isinstance(cues, list), f"scene {sid}.cues: expected a list")
        labels = set()
        for cue in cues:
            require(isinstance(cue, dict), f"scene {sid}: each cue must be an object")
            label = cue.get("label")
            require(isinstance(label, str) and label.strip(), f"scene {sid}: cue needs a label")
            require(label not in labels, f"scene {sid}: duplicate cue {label}")
            labels.add(label)
            require(("at" in cue) != ("time" in cue), f"cue {sid}.{label}: provide either at or time")
            if "at" in cue:
                word = cue["at"]
                require(isinstance(word, str) and word.strip(), f"cue {sid}.{label}: at must not be empty")
                nth = cue.get("nth", 0)
                require(type(nth) is int and nth >= 0, f"cue {sid}.{label}: nth must be a nonnegative integer")
                count = sum(len(list(re.finditer(f"(?={re.escape(word)})", line_text(line)))) for line in lines)
                require(nth < count, f"cue {sid}.{label}: occurrence {nth} of {word!r} is missing from the text")
            else:
                number(cue["time"], f"cue {sid}.{label}.time")
            number(cue.get("offset", 0), f"cue {sid}.{label}.offset", minimum=-math.inf)
            require(cue.get("sound", "none") in ("pop", "chime", "click", "lock", "none"), f"cue {sid}.{label}: unknown sound")
            if "snap" in cue:
                require(type(cue["snap"]) is bool, f"cue {sid}.{label}.snap: expected true or false")
    return spec


def check_timeline(spec, root=ROOT):
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    require(timeline.get("spec_hash") == spec_hash(spec), "timeline is stale; run ./make.sh voice")
    require(timeline.get("speech_hash") == speech_hash(spec), "narration settings changed; run ./make.sh voice")
    number(timeline["duration"], "timeline.duration", positive=True)
    require([s["id"] for s in timeline["scenes"]] == [s["id"] for s in spec["scenes"]], "timeline scene list does not match video.json")
    for scene, source in zip(timeline["scenes"], spec["scenes"]):
        require(len(scene["lines"]) == len(source.get("lines", [])), f"scene {scene['id']}: missing timeline lines")
        for line in scene["lines"]:
            number(line["dur"], "line duration", positive=True)
            if spec.get("narration", {}).get("mode", "tts") != "none":
                require(bool(line.get("file")) and (root / line["file"]).is_file(), f"scene {scene['id']}: missing voice file; run ./make.sh voice")
        for label, time in scene["cues"].items():
            require(scene["start"] <= time < scene["end"], f"cue {scene['id']}.{label}: outside its scene")
    return timeline


def audio_signature(spec, root=ROOT):
    paths = [root / p for p in ("video.json", "validate.py", "tts.py", "timeline.py", "score.py", "music.py", "mix.py")]
    paths += [root / p for p in ("tts.py.lock", "music.py.lock", "mix.py.lock") if (root / p).exists()]
    paths += [root / Path(line["audio"]).expanduser() for s in spec["scenes"] for line in s.get("lines", []) if isinstance(line, dict) and "audio" in line]
    if (root / "out/extra.wav").exists():
        paths.append(root / "out/extra.wav")
    state = [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
    state.append(("speech", speech_hash(spec)))
    return hashlib.sha256(json.dumps(state).encode()).hexdigest()


if __name__ == "__main__":
    try:
        spec = load_spec()
        command = sys.argv[1] if len(sys.argv) > 1 else ""
        if command == "--mode":
            print(spec.get("narration", {}).get("mode", "tts"))
        elif command == "--backend":
            print(speech_settings(spec)["provider"])
        elif command == "--audio-current":
            check_timeline(spec)
            signature = (ROOT / "out/audio.signature").read_text()
            require(signature == audio_signature(spec) and (ROOT / "out/audio-mix.mp3").is_file() and (ROOT / "out/music.wav").is_file(), "audio needs a rebuild")
        elif command == "--stamp-audio":
            (ROOT / "out/audio.signature").write_text(audio_signature(spec))
        else:
            if command == "--timeline":
                check_timeline(spec)
            elif command:
                raise ValueError(f"unknown option: {command}")
            print("project inputs are valid")
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"check failed: {error}", file=sys.stderr)
        sys.exit(1)
