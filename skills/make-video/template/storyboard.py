"""Build storyboard.html: one self-contained page to review the film before the full render.

It holds the real voice + music mix (out/audio-mix.mp3), one real frame per scene (out/board/*.jpg),
the script with each cue word marked, and the brief from video.json. Playing the audio highlights
the current scene and line. With --final it embeds the finished film (out/<name>.mp4) instead.

Run after: uv run mix.py --audio && node render.mjs --board
Run: python3 storyboard.py [--final]   (no dependencies)
"""

import base64
import html
import json
import re
import sys
from pathlib import Path
from validate import load_spec, check_timeline

ROOT = Path(__file__).parent
OUT = ROOT / "out"
spec = load_spec()
tl = check_timeline(spec)
final = "--final" in sys.argv


def data_uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


cue_spec = {s["id"]: s.get("cues", []) for s in spec["scenes"]}
frames = {p.stem: data_uri(p, "image/jpeg") for p in sorted((OUT / "board").glob("*.jpg"))}
missing = [s["id"] for s in tl["scenes"] if s["id"] not in frames]
if missing:
    raise SystemExit("missing storyboard frames: " + ", ".join(missing) + "; run ./make.sh storyboard")
data = {
    "title": tl["title"],
    "duration": tl["duration"],
    "voice": spec.get("voice", "af_heart") if spec.get("narration", {}).get("mode", "tts") == "tts" else spec["narration"]["mode"],
    "music": spec.get("music", {}).get("style", "pop"),
    "brief": spec.get("brief", {}),
    "scenes": [
        {"id": s["id"], "start": s["start"], "end": s["end"], "card": s.get("card"), "cues": s["cues"],
         "cueSpec": cue_spec.get(s["id"], []), "lines": [{"text": l["text"], "start": l["start"], "dur": l["dur"]} for l in s["lines"]]}
        for s in tl["scenes"]
    ],
    "frames": frames,
}
if final:
    data["video"] = data_uri(OUT / f"{tl['name']}.mp4", "video/mp4")
else:
    data["audio"] = data_uri(OUT / "audio-mix.mp3", "audio/mpeg")

page = (ROOT / "storyboard.template.html").read_text(encoding="utf-8")
values = {
    "TITLE": html.escape(tl["title"], quote=True),
    "STAGE": "final cut" if final else "draft for review",
    "DATA": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
}
page = re.sub(r"__(TITLE|STAGE|DATA)__", lambda match: values[match[1]], page)
(ROOT / "storyboard.html").write_text(page, encoding="utf-8")
print(f"wrote storyboard.html ({len(page) / 1e6:.1f} MB)")
