# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""The score, made entirely in code (no samples, no licences). Reads timeline.json, writes out/music.wav.

Styles (video.json "music.style"):
  pop   bright groove: off-beat piano stabs, marimba hook, bouncy bass, kick, clap, hats; glockenspiel on cues
  chip  quiet chiptune bed: pulse-wave arpeggios, triangle bass, soft noise hats, small kick
  none  silence (voice only)

Each scene's "music" value (0..1) is its energy: more layers come in as it rises.
A scene can instead give the layers directly, e.g. "music": {"keys": 0.8, "bass": 0.6}.
Cue sounds (on the cue's time, already beat-snapped by timeline.py): pop, chime, click, lock, none.
This file is a starting point: change the chords, hooks and instruments to fit the film.

Run: uv run music.py
"""

import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
ROOT = Path(__file__).parent
rng = np.random.default_rng(23)
TL = json.loads((ROOT / "timeline.json").read_text())
SPEC = json.loads((ROOT / "video.json").read_text())
STYLE = SPEC.get("music", {}).get("style", "pop")
DUR = TL["duration"]
BEAT = 60.0 / TL["bpm"]
BAR = 4 * BEAT
E8 = BEAT / 2
N = int((DUR + 0.5) * SR)

# One chord per bar: I-V-vi-IV in F. v = stab voicing, root = bass, tones = melody notes (MIDI).
CHORDS = [
    dict(v=[57, 60, 65, 69], root=41, tones=[65, 69, 72, 77, 81]),  # F
    dict(v=[55, 60, 64, 67], root=36, tones=[64, 67, 72, 76, 79]),  # C
    dict(v=[57, 62, 65, 69], root=38, tones=[62, 65, 69, 74, 77]),  # Dm
    dict(v=[58, 62, 65, 70], root=34, tones=[62, 65, 70, 74, 77]),  # Bb
]
TONIC = CHORDS[0]


def layers(sc):
    """Layer levels (0..1) for a scene, from its energy or an explicit dict."""
    m = sc.get("music", 0.4 if "card" in sc else 0.7)
    if isinstance(m, dict):
        return {**dict(keys=0, mar=0, bass=0, kick=0, clap=0, hat=0), **m}
    e = float(m)
    on = lambda lo: 0.0 if e < lo else min(1.0, 0.5 + e / 2)
    return dict(keys=0.6 + 0.4 * e if e > 0 else 0, mar=on(0.5), bass=on(0.3), hat=on(0.45), kick=on(0.6), clap=on(0.85))


LEVELS = {s["id"]: layers(s) for s in TL["scenes"]}


def scene_at(t):
    for s in TL["scenes"]:
        if s["start"] <= t < s["end"]:
            return s["id"]
    return TL["scenes"][-1]["id"]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tvec(d):
    return np.arange(int(d * SR)) / SR


class Bus:
    def __init__(self):
        self.x = np.zeros((2, N))

    def add(self, t0, sig, pan=0.0, gain=1.0):
        i = int(t0 * SR)
        if i >= N or gain <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        sig = sig[: N - i] * gain
        a = (pan + 1) * np.pi / 4
        self.x[0, i : i + len(sig)] += sig * np.cos(a)
        self.x[1, i : i + len(sig)] += sig * np.sin(a)


def fade_tail(sig, d=0.03):
    n = min(len(sig), int(d * SR))
    sig[-n:] *= np.linspace(1, 0, n)
    return sig


def lowpass(x, hz, order=4):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x, axis=-1)


def highpass(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x, axis=-1)


def bandpass(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x, axis=-1)


# ---------- instruments ----------

def marimba(f, vel=0.5, dur=0.9):
    t = tvec(dur)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 7)
    y += 0.35 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 28)
    y += 0.12 * np.sin(2 * np.pi * f * 9.8 * t) * np.exp(-t * 70)
    return fade_tail(y * (1 - np.exp(-t * 2500)) * vel)


def glock(f, vel=0.4, dur=2.4):
    t = tvec(dur)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 2.2)
    y += 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 5)
    y += 0.18 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 11)
    return fade_tail(y * (1 - np.exp(-t * 4000)) * vel)


def stab(f, dur=0.16):
    """Short, round piano-ish stab."""
    t = tvec(dur + 0.08)
    y = np.zeros_like(t)
    for k, a in ((1, 1.0), (2, 0.35), (3, 0.25), (4, 0.08), (5, 0.06)):
        y += a * np.sin(2 * np.pi * f * k * t * (1 + 0.0015 * (k - 1)))
    env = (1 - np.exp(-t * 900)) * np.exp(-t * 9) * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    return y * env


def bass(f, dur):
    t = tvec(dur)
    ph = 2 * np.pi * np.cumsum(f * (1 + 0.12 * np.exp(-t * 60))) / SR
    y = np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)
    return fade_tail(y * (1 - np.exp(-t * 400)) * np.exp(-t * 3.5), 0.02)


def pulse(f, dur, duty=0.125, decay=9.0):
    t = tvec(dur)
    y = np.where((f * t) % 1.0 < duty, 1.0, -1.0) - (2 * duty - 1)
    return y * (1 - np.exp(-t * 800)) * np.exp(-t * decay) * np.clip((dur - t) / 0.01, 0, 1)


def tri(f, dur):
    t = tvec(dur)
    y = 4 * np.abs((f * t) % 1.0 - 0.5) - 1
    return y * (1 - np.exp(-t * 500)) * np.clip((dur - t) / 0.02, 0, 1) * np.exp(-t * 1.5)


def kick():
    t = tvec(0.4)
    ph = 2 * np.pi * np.cumsum(50 + 110 * np.exp(-t * 35)) / SR
    return np.sin(ph) * np.exp(-t * 9) * (1 - np.exp(-t * 2000))


def clap():
    t = tvec(0.25)
    env = sum(np.where(t >= d, np.exp(-(t - d) * 180), 0) for d in (0.0, 0.011, 0.022)) + np.exp(-t * 22) * 0.35
    return bandpass(rng.standard_normal(len(t)) * env, 900, 4500) * 0.9


def hat(vel):
    t = tvec(0.05)
    return highpass(rng.standard_normal(len(t)), 7000, 2) * np.exp(-t * 110) * vel


def tick():
    t = tvec(0.03)
    return highpass(rng.standard_normal(len(t)), 3000, 2) * np.exp(-t * 220) * 0.5


def lock_click():
    t = tvec(0.12)
    body = np.sin(2 * np.pi * 820 * t) * np.exp(-t * 60) + 0.6 * np.sin(2 * np.pi * 1640 * t) * np.exp(-t * 90)
    snap = bandpass(rng.standard_normal(len(t)), 2500, 7000) * np.exp(-t * 160) * 0.6
    tail = np.zeros_like(t)
    tail[int(0.045 * SR):] = body[: len(t) - int(0.045 * SR)] * 0.5
    return (body + snap + tail) * 0.6


# ---------- arrangement ----------

HOOKS = [  # marimba: eighth-note steps into the chord's tones (None = rest)
    [0, None, 2, 1, None, 3, 2, None],
    [4, None, 3, 2, None, 1, 2, None],
    [0, 2, None, 3, None, 2, 4, None],
    [3, None, 2, None, 1, 0, None, None],
]
KICK, CLAP = [0, 3, 4], [2, 6]
BASS = [(0, 0, 1.4), (2, 0, 0.8), (3, 12, 0.6), (5, 0, 0.9), (6, 7, 0.8)]  # (eighth, interval, length in 8ths)
ARP = [0, 1, 2, 3, 2, 1, 2, 3]


def bars(buses, end):
    b = 0
    while b * BAR < end:
        ch = CHORDS[b % len(CHORDS)]
        for k in range(8):
            tk = b * BAR + k * E8
            if tk >= end:
                break
            lv = LEVELS[scene_at(tk)]
            if STYLE == "chip":
                for h in range(2):  # sixteenth arpeggio
                    m = ch["v"][ARP[(2 * k + h) % 8] % 4] + 12 + (12 if k >= 4 and b % 2 else 0)
                    buses["keys"].add(tk + h * E8 / 2, pulse(mtof(m), E8 / 2 * 0.9), pan=0.2 * np.sin(k), gain=lv["keys"] * 0.09)
                if lv["bass"] and k in (0, 4):
                    buses["bass"].add(tk, tri(mtof(ch["root"]), BEAT * 1.9), gain=lv["bass"] * 0.5)
                if lv["bass"] and k in (3, 7):
                    buses["bass"].add(tk, tri(mtof(ch["root"] + 12), BEAT * 0.45), gain=lv["bass"] * 0.3)
            else:
                if lv["keys"] and k % 2 == 1:
                    for i, m in enumerate(ch["v"]):
                        buses["keys"].add(tk + i * 0.004, stab(mtof(m)), pan=-0.25 + 0.17 * i, gain=lv["keys"] * 0.16)
                if lv["mar"]:
                    step = HOOKS[b % 4][k]
                    if step is not None and (lv["mar"] >= 0.8 or rng.random() < lv["mar"] + 0.2):
                        buses["mar"].add(tk, marimba(mtof(ch["tones"][step]), 0.5), pan=0.3 * np.sin(k + b), gain=lv["mar"] * 0.7)
                if lv["bass"]:
                    for e, iv, ln in BASS:
                        if e == k:
                            buses["bass"].add(tk, bass(mtof(ch["root"] + iv), ln * E8), gain=lv["bass"] * 0.42)
                if lv["clap"] and k in CLAP:
                    buses["clap"].add(tk, clap(), pan=0.05, gain=lv["clap"] * 0.35)
            if lv["kick"] and k in KICK:
                buses["kick"].add(tk, kick(), gain=lv["kick"] * 0.6)
            if lv["hat"]:
                for h in range(2):
                    buses["hat"].add(tk + h * E8 / 2, hat(0.5 if h else 0.22), pan=0.35, gain=lv["hat"] * 0.5)
        b += 1


def cue_sounds(buses):
    for n, ev in enumerate(TL["events"]):
        t, k = ev["t"], ev["sound"]
        ch = CHORDS[int(t // BAR) % len(CHORDS)]
        if k == "pop":
            for i, m in enumerate(ch["tones"][2:]):
                buses["fx"].add(t + i * 0.05, glock(mtof(m + 12), 0.32), pan=-0.3 + 0.3 * i)
            buses["clap"].add(t, clap(), gain=0.3)
        elif k == "chime":
            buses["fx"].add(t, glock(mtof(ch["tones"][2 + n % 3] + 12), 0.3, 1.6), pan=0.15)
        elif k == "click":
            buses["fx"].add(t, tick(), pan=0.1)
            buses["fx"].add(t + BEAT / 4, glock(mtof(ch["tones"][3] + 12), 0.28, 1.4), pan=-0.1)
        elif k == "lock":
            buses["fx"].add(t, lock_click(), gain=0.9)


def ending(buses, t):
    """Land on the tonic chord at the last downbeat that leaves ~2.5 s of ring-out."""
    for i, m in enumerate(TONIC["v"] + [72]):
        buses["keys"].add(t + i * 0.01, stab(mtof(m), 2.6), pan=-0.3 + 0.15 * i, gain=0.2)
    for i, m in enumerate([77, 81, 84, 89]):
        buses["fx"].add(t + i * 0.07, glock(mtof(m), 0.3, 3.4), pan=0.3 - 0.2 * i)
    buses["bass"].add(t, bass(mtof(TONIC["root"] - 12), 3.0), gain=0.5)
    buses["kick"].add(t, kick(), gain=0.5)


def reverb(x, secs=1.6):
    t = tvec(secs)
    out = np.zeros_like(x)
    for c in range(2):
        ir = np.concatenate([np.zeros(int(0.015 * SR)), lowpass(rng.standard_normal(len(t)) * np.exp(-t * 6.9 / secs), 6000, 2)])
        out[c] = fftconvolve(x[c], ir)[:N] / np.sqrt(np.sum(ir ** 2)) * 0.5
    return out


def main():
    mix = np.zeros((2, N))
    if STYLE != "none":
        buses = {k: Bus() for k in ("keys", "mar", "bass", "kick", "clap", "hat", "fx")}
        last = max(BAR, np.floor((DUR - 2.5) / BAR) * BAR)
        bars(buses, last)
        cue_sounds(buses)
        ending(buses, last)
        keys = lowpass(buses["keys"].x, 3800 if STYLE == "chip" else 3500, 2)
        dry = keys + sum(buses[k].x for k in ("mar", "bass", "kick", "clap", "hat", "fx"))
        send = 0.25 * keys + 0.3 * buses["mar"].x + 0.25 * buses["clap"].x + 0.45 * buses["fx"].x
        mix = dry + reverb(send)
        mix = np.tanh(mix * 1.2) / np.tanh(1.2)
        rms = np.sqrt(np.mean(mix ** 2))
        mix *= 10 ** ((-24 if STYLE == "chip" else -19) / 20) / max(rms, 1e-9)
        mix *= min(1.0, 0.89 / max(np.max(np.abs(mix)), 1e-9))
    mix = mix[:, : int(DUR * SR)]
    mix[:, -int(1.5 * SR):] *= np.linspace(1, 0, int(1.5 * SR)) ** 2
    (ROOT / "out").mkdir(exist_ok=True)
    with wave.open(str(ROOT / "out/music.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix.T * 32767).astype("<i2").tobytes())
    print(f"wrote out/music.wav ({DUR:.1f}s, style {STYLE})")


if __name__ == "__main__":
    main()
