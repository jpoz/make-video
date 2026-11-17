# Checks

`python3 -m unittest discover -s tests -v` uses only the Python standard library. It checks input
validation, missing and stale speech data, cue boundaries, caption generation, HTML escaping,
composition variation, and saved music seeds.
It checks word-timing matches, gaps, rejected lines, and measured cue and caption times.
It also uses local command fixtures to check Gemini selection, spoken text, line caching,
provider and voice changes, and failed or silent narration. These checks make no API requests.

`python3 tests/smoke_music.py` renders and mixes actual pop, chip, and silent tracks. It checks
that new seeds change the audio, repeated builds reproduce it, deleting output preserves the
track, and composition changes invalidate cached audio. It needs uv and ffmpeg, with initial
network access for audio packages. It does not need Node packages, fonts, or a speech model.

`python3 tests/smoke.py` creates a temporary project and runs complete builds. It installs the
locked Node packages and fonts, then uses uv for audio dependencies. It needs the same tools and
initial network access as project setup. It does not download the speech model.

The smoke check renders silent and recorded audio in landscape, portrait, and square formats.
It checks dimensions, frame rate, duration, H.264/AAC streams, captions, and full-file decoding.
It starts the studio and checks its page, frames, audio byte ranges, and reload after a scene edit.
It also checks direct scene sampling from a fresh project, missing draw functions, bad flags,
ffmpeg failures during encoding, contact sheets, and concatenation, and failed audio stages.
Temporary paths include spaces and an apostrophe to check path handling.

To reuse a prepared project's packages and fonts:

```sh
python3 tests/smoke.py --prepared /path/to/project
```

The GitHub Actions workflow runs these checks on Ubuntu and macOS. Native Windows is not part of
the test matrix. WSL uses the Linux path.

Local verification used arm64 macOS 26.5.2, Node.js 26.4.0, ffmpeg 8.1.1, and uv 0.11.17.
The full 30-second sample was also rendered at 1920×1080 and 30 fps with local Kokoro speech.
Its 908 encoded frames were counted, and a frame from the encoded code scene was inspected.
The three example videos in `docs/examples/` were rendered with preview quality.
