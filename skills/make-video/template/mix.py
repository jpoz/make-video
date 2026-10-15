# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""Place the voice lines on the timeline, duck the music under the voice, and mix.

  uv run mix.py --audio   out/audio-mix.mp3 only (for the storyboard; no picture needed)
  uv run mix.py           out/<name>.mp4 (out/video.mp4 + the mix), out/<name>.srt, out/<name>.vtt

If out/extra.wav exists (a demo's own sound, sound effects), it is mixed into the bed and ducks too.
"""

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).parent
OUT = ROOT / "out"
SR = 48000
tl = json.loads((ROOT / "timeline.json").read_text())
NAME = tl["name"]
n = int((tl["duration"] + 0.5) * SR)


def read(path):
    with wave.open(str(path)) as w:
        rate, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float64) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return resample_poly(x, SR, rate) if rate != SR else x


voice = np.zeros(n)
for sc in tl["scenes"]:
    for ln in sc["lines"]:
        x = read(ROOT / ln["file"])
        i = int(ln["start"] * SR)
        voice[i : i + len(x)] += x[: n - i]
voiced = np.abs(voice) > 0.01
if voiced.any():
    voice *= 10 ** (-20 / 20) / np.sqrt(np.mean(voice[voiced] ** 2))  # speech at about -20 dBFS RMS
with wave.open(str(OUT / "voice.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(voice, -0.98, 0.98) * 32767).astype("<i2").tobytes())


def ts(t, sep="."):
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}{sep}{int(round(t % 1 * 1000)) % 1000:03d}"


caps = tl["captions"] or [{"a": ln["start"], "b": ln["start"] + ln["dur"], "text": ln["text"]} for sc in tl["scenes"] for ln in sc["lines"]]
vtt, srt = ["WEBVTT", ""], []
for k, c in enumerate(caps, 1):
    vtt += [f"{ts(c['a'])} --> {ts(c['b'])}", c["text"], ""]
    srt += [str(k), f"{ts(c['a'], ',')} --> {ts(c['b'], ',')}", c["text"], ""]
(OUT / f"{NAME}.vtt").write_text("\n".join(vtt))
(OUT / f"{NAME}.srt").write_text("\n".join(srt))

ins = ["-i", str(OUT / "music.wav"), "-i", str(OUT / "voice.wav")]
bed = "[0:a]aformat=channel_layouts=stereo[bed];"
if (OUT / "extra.wav").exists():
    ins += ["-i", str(OUT / "extra.wav")]
    bed = "[0:a][2:a]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo[bed];"
fc = (
    bed + "[1:a]aformat=channel_layouts=stereo,asplit=2[v1][vsc];"
    "[bed][vsc]sidechaincompress=threshold=0.02:ratio=5:attack=25:release=400[m];"
    "[m][v1]amix=inputs=2:normalize=0:weights='0.55 1'[mx];"
    "[mx]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]"
)
ff = ["ffmpeg", "-loglevel", "error", "-y", *ins]
if "--audio" in sys.argv:
    subprocess.run([*ff, "-filter_complex", fc, "-map", "[a]", "-ac", "2", "-b:a", "128k", str(OUT / "audio-mix.mp3")], check=True)
    print("wrote out/audio-mix.mp3")
    sys.exit(0)
vi = len(ins) // 2
subprocess.run([
    *ff, "-i", str(OUT / "video.mp4"), "-filter_complex", fc, "-map", f"{vi}:v", "-map", "[a]", "-ac", "2",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(OUT / f"{NAME}.mp4"),
], check=True)
print(f"wrote out/{NAME}.mp4, out/{NAME}.srt, out/{NAME}.vtt")
