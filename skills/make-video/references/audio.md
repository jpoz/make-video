# Audio: voice, music, mix

## Voice model: download and install

The voice is [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), which runs locally on the CPU.
It needs no API key and no account. It has two parts:

- **Python packages** (`kokoro-onnx==0.4.9`, `numpy`, `soundfile`). The header of `tts.py` lists
  them, and `uv run tts.py` installs them into a cached environment. Kokoro needs Python 3.10–3.12,
  and uv downloads one if necessary. The espeak-ng phonemizer is part of the package, so you do not
  install it on the system.
- **Model files** (about 115 MB in all). `tts.py` downloads them the first time it runs:

  | File | Size | URL |
  |---|---|---|
  | `kokoro-v1.0.int8.onnx` | ~88 MB | `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx` |
  | `voices-v1.0.bin` | ~27 MB | `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin` |

  All the voices are in `voices-v1.0.bin`. There is nothing to install for each voice.

The files go to `~/.cache/make-video/models`. Set `MAKE_VIDEO_MODELS` to use another folder, for
example a shared folder or one that already has the files: `MAKE_VIDEO_MODELS=/path/to/models uv run tts.py`.

**To install by hand** (offline machines, proxies, or a failed download):

```sh
mkdir -p ~/.cache/make-video/models && cd ~/.cache/make-video/models
B=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
curl -fL -O $B/kokoro-v1.0.int8.onnx -O $B/voices-v1.0.bin
```

**If something goes wrong:**
- A stopped download leaves a `.part` file. `tts.py` downloads the file again on the next run. A
  complete file is never replaced.
- If `tts.py` fails while it loads the model, a file may be damaged. Delete the two files and run again.
- If `uv` is missing, install it (`curl -LsSf https://astral.sh/uv/install.sh | sh`). Or make a
  Python 3.10–3.12 virtual environment, run `pip install kokoro-onnx==0.4.9 numpy soundfile`, and
  run `python tts.py` with that environment.
- To check the install: `uv run tts.py --voices` prints the voice names.

## Voice (`tts.py`, Kokoro, local)

Set `voice`, `speed` (0.9–1.1) and `lang` in `video.json`. The default is `af_heart`
at speed 1.0 in `en-us`. Good English voices: `af_heart`, `af_bella`, `af_nicole`, `af_sarah`
(American female); `am_michael`, `am_adam`, `am_eric` (American male); `bf_emma`, `bf_isabella`
(British female, `lang: "en-gb"`); `bm_george`, `bm_fable`, `bm_lewis` (British male). Run
`uv run tts.py --voices` for the full list, which also has French, Spanish, Hindi, Italian,
Japanese, Portuguese and Chinese voices.

To compare voices, voice the first two scenes with each voice you are considering
(`"voice"` in `video.json`, then `./make.sh storyboard`) and let the user choose in the storyboard.
Each voice is cached on its own, so switching back is instant.

`tts.py` trims the silence from each line, so a line's length is its speech. The timing gaps come from `timing`.

## Music (`music.py`)

The score is generated in code, so there are no samples and no licences. The defaults:

- **`pop`**: F major, I–V–vi–IV, 112 BPM. It has off-beat piano stabs, a
  marimba hook, a bouncy bass, kick, clap, hats, and a glockenspiel on cues.
- **`chip`**: pulse-wave arpeggios, a triangle bass, soft hats and a
  small kick. It is quieter (−24 dB RMS against −19 dB for pop) and sits under a long explainer.
- **`none`**: voice only.

**Energy per scene:** `"music": 0..1`. Below 0.3 there are only keys. From 0.3 the bass comes in,
from 0.45 the hats, from 0.5 the marimba, from 0.6 the kick, and from 0.85 the clap. Use high energy
for the intro and the end, about 0.6 under explanations, and 0.4 on chapter cards. Or give the
layers directly: `"music": {"keys": 0.8, "bass": 0.6, "kick": 0, "mar": 0.3, "clap": 0, "hat": 0.4}`.

**Cue sounds** (`"sound"` on a cue): `pop` (a glock chord and a clap, for big arrivals), `chime` (one
glock note, for each item in a list), `click` (a UI click and a note, for cursor presses), `lock`
(a two-part latch), and `none`. Cues snap to the nearest eighth note when `music.snap` is true, so the
picture, the sound and the beat land together.

**The ending:** the music lands on the tonic chord at the last bar line that leaves about 2.5 s,
and then fades out.

`music.py` is meant to be edited for each film. Change `CHORDS` (the key and the progression),
`HOOKS`, the BPM, or add an instrument. Ideas: a tape stop and a lone music box for a
"used to" flashback, or a riser into the new way. Keep the bed under the voice: it is ducked, but a
busy melody still fights the words.

## Mix (`mix.py`)

The voice goes at about −20 dBFS RMS. The music is side-chain ducked under the voice (ratio 5,
release 400 ms). The final mix is loudness-normalized to −16 LUFS, with true peaks at −1.5 dB.
`--audio` writes only `out/audio-mix.mp3` (for the storyboard, with no picture needed). Without it,
the mix is muxed onto `out/video.mp4`.

**Extra audio** (a demo's own sound, real UI sounds, a song the film shows playing): write it as
`out/extra.wav`, placed on the film's timeline, from a small script that reads `timeline.json`.
`mix.py` adds it to the bed, so it ducks under the voice too. When the picture shows something
playing its own sound, lower the music there (energy 0, or a gap) so the two do not clash.
