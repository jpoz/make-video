# Audio: voice, music, mix

## Choose the narration mode

Set `narration.mode` in `video.json` to `tts` (the default), `recorded`, or `none`.
For `tts`, the commands select `narrate` when `GEMINI_API_KEY` is nonempty, and local Kokoro when
it is absent or empty. Recorded and silent builds do not use either speech provider. Narrate,
recorded, and silent builds use system Python for the narration step; they do not load Kokoro.
Music and mixing still use uv for their Python dependencies.

## Gemini speech through `narrate`

Install the `narrate` command on PATH and export `GEMINI_API_KEY` in the shell that runs the
project. Then use the normal `./make.sh voice`, `storyboard`, or `film` commands. The skill uses
the installed command; it does not bundle a platform-specific binary or read shell startup files.
Keep the key in the environment, not in `video.json`.

The command sends each line's `say` value (or `text` when `say` is absent) to Gemini. Captions
keep the original `text`. Gemini requires network access for new speech and uses your API account.
The skill caches each line separately and measures its WAV duration for the timeline.

Optional project settings:

```json
{
  "narration": {
    "mode": "tts",
    "narrate": {
      "voice": "Kore",
      "style": "Warm, clear, unhurried explanation."
    }
  }
}
```

This is a partial configuration. `narration.narrate` supports `voice`, `style`, and `model`.
Omitted values use `NARRATE_VOICE`, `NARRATE_STYLE`, and `NARRATE_MODEL`, then the command's defaults.
Use `narrate -voices` to list voices. Use `style` for delivery and pace. The top-level `voice`,
`speed`, and `lang` settings apply only to Kokoro and are not passed to `narrate`.

Changing providers, voice, model, or style invalidates the affected speech and timing cache.
The API key itself is never stored in cache metadata. If a key is set but `narrate` is missing,
or the command fails, the build stops with an error. To select local voices for one build:

```sh
env -u GEMINI_API_KEY ./make.sh storyboard
```

`GOOGLE_API_KEY` alone does not select Gemini in this skill. The selector uses `GEMINI_API_KEY`.

## Supplied recordings and no narration

For recorded speech, add an audio path to every line:

```json
{
  "narration": { "mode": "recorded" },
  "scenes": [{
    "id": "intro",
    "lines": [
      { "text": "Welcome to the workshop.", "audio": "audio/narration.wav", "from": 0, "to": 2.4 },
      { "text": "We will start with a simple drawing.", "audio": "audio/narration.wav", "from": 2.4, "to": 6 }
    ]
  }]
}
```

This is a partial configuration. Keep the project's other settings and its draw function for
`intro`. Paths are relative to the project. Omit `from` and `to` to use a complete file for one
line. ffmpeg converts each selected range to a cached mono WAV. The original file is preserved.
The normal scene lead, line gaps, and tail still apply; set gaps to zero for adjoining ranges.
The text is the supplied transcript. Word cues are estimates, including for recordings.

For no narration, use `{"narration": {"mode": "none"}}`. Lines become timed captions; use
`{"text": "Doors open at ten.", "duration": 3}` to set the display time. A scene can also have
no lines, a `min` duration, and cues with explicit scene-relative `time` values.

## Local voice model: download and install

The local voice model is [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), which runs on the CPU.
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
(`"voice"` in `video.json`, then `env -u GEMINI_API_KEY ./make.sh storyboard`) and let the user choose in the storyboard.
Each voice is cached on its own, so switching back is instant.

`tts.py` trims the silence from each line, so a line's length is its speech. The timing gaps come from `timing`.

## Music (`music.py`)

Music is synthesized locally and needs no external audio samples. The available styles:

- **`pop`**: piano, electric keys, or plucked chords; a marimba, bell, or plucked melody;
  bass, kick, clap, hats, and glockenspiel cue sounds.
- **`chip`**: pulse-wave arpeggios, a triangle bass, soft hats and a
  small kick. It is quieter (−24 dB RMS against −19 dB for pop) and sits under a long explainer.
- **`none`**: voice only.

These controls apply to projects made with the current template. Existing projects keep copies
of their generator files; updating the installed skill does not update those copies. When
upgrading a project, compare `score.py`, `music.py`, `make.sh`, and `validate.py` with the current
template and preserve any project-specific edits.

Each new project saves a random `music.seed` in `video.json`. If a manually created project has
no seed, its first audio build saves one. The seed selects a key, chord sequence, melody, rhythm,
and instrument colors. A normal rebuild keeps the seed, including after deleting `out/`.
It also keeps the chosen style, tempo (`music.bpm`, default 112), and scene energy settings.

To request a different track in the current project:

```sh
./make.sh music --new    # save a new seed and rebuild the music and audio mix
./make.sh storyboard    # update the review page with the new mix
```

Run `./make.sh film` to put the new mix in the MP4. `music --new` alone does not replace an
existing MP4 or the audio embedded in `storyboard.html`. Use it when copying a project for a
new video, too. A plain `./make.sh music` rebuilds the selected track and reuses cached speech.

To reproduce a track, retain its `music.seed` (an integer from 0 to 9007199254740991), music
settings, timing, and generator files. `out/music.json` records the selected composition for
inspection. Do not edit this generated file. New seeds vary the composition within the selected
style; they do not select arbitrary genres. Edit `score.py` or the instruments in `music.py` when
the brief calls for a different musical style.

**Energy per scene:** `"music": 0..1`. Below 0.3 there are only keys. From 0.3 the bass comes in,
from 0.45 the hats, from 0.5 the melody (`mar` layer), from 0.6 the kick, and from 0.85 the clap. Use high energy
for the intro and the end, about 0.6 under explanations, and 0.4 on chapter cards. Or give the
layers directly: `"music": {"keys": 0.8, "bass": 0.6, "kick": 0, "mar": 0.3, "clap": 0, "hat": 0.4}`.

**Cue sounds** (`"sound"` on a cue): `pop` (a glock chord and a clap, for big arrivals), `chime` (one
glock note, for each item in a list), `click` (a UI click and a note, for cursor presses), `lock`
(a two-part latch), and `none`. Cues snap to the nearest eighth note when `music.snap` is true, so the
picture, the sound and the beat land together.

**The ending:** the music lands on the tonic chord at the last bar line that leaves about 2.5 s,
and then fades out.

For custom scoring, `score.py` contains the composition choices; `music.py` contains synthesis
and arrangement. Keep the bed under the voice: it is ducked, but a busy melody still fights the words.

## Mix (`mix.py`)

The voice goes at about −20 dBFS RMS. The music is side-chain ducked under the voice (ratio 5,
release 400 ms). The final mix is loudness-normalized to −16 LUFS, with true peaks at −1.5 dB.
`--audio` writes only `out/audio-mix.mp3` (for the storyboard, with no picture needed). Without it,
the mix is muxed onto `out/video.mp4`.

**Extra audio** (a demo's own sound, real UI sounds, a song the film shows playing): write it as
`out/extra.wav`, placed on the film's timeline, from a small script that reads `timeline.json`.
`mix.py` adds it to the bed, so it ducks under the voice too. When the picture shows something
playing its own sound, lower the music there (energy 0, or a gap) so the two do not clash.
