# make-video

Create short videos with Claude Code, Codex, or another agent that reads `SKILL.md` files.
Use it for lessons, event announcements, diagrams, product introductions, and code walkthroughs.

The agent writes the script, draws scenes, and builds a storyboard with the real audio. You can
review it before the final render, or ask the agent to complete the video automatically.
Rendering is local. With `GEMINI_API_KEY` set, generated speech uses the `narrate` command and
Gemini. Without it, speech uses local Kokoro voices and needs no API key. You can also supply a
recording or omit narration. Music is optional.

Output includes an MP4, SRT and VTT captions, and an HTML storyboard. Choose landscape
(1920×1080), portrait (1080×1920), or square (1080×1080). Preview output uses half the dimensions
and at most 30 fps. The final frame rate is configurable, with 60 fps as the default.

## Install the skill

For Claude Code as a plugin:

```text
/plugin marketplace add jpoz/make-video
/plugin install make-video@make-video
```

From a clone:

```sh
git clone https://github.com/jpoz/make-video.git
cd make-video
./install.sh          # Claude Code and Codex
./install.sh codex    # Codex only
./install.sh claude   # Claude Code only
```

The installer creates links in `~/.agents/skills` for Codex and `~/.claude/skills` for Claude Code
(or `$CLAUDE_CONFIG_DIR/skills`). `git pull` then updates the skill. Use `--copy` to copy files or
`--force` to replace an existing installation. Other agents can use a copy of `skills/make-video`.

## Requirements

- Node.js 20 or later, with npm.
- ffmpeg and ffprobe, with the libx264 encoder.
- Python 3.10 or later.
- [uv](https://docs.astral.sh/uv/). It installs the Python dependencies and a compatible Python
  version for Kokoro (3.10–3.12).
- `narrate` on PATH when `GEMINI_API_KEY` is set. It is an optional external command.

The shell commands target macOS and Linux. Native Windows is not supported; use WSL. CI is
configured for macOS and Ubuntu. Local verification details are in [the checks guide](tests/README.md).

Setup downloads Node packages and the default fonts with their license files. The first audio
build downloads Python packages. The first local-speech build also downloads about 115 MB
of model files to `~/.cache/make-video/models`. Gemini, recorded, and silent videos do not need the model.
The first narrated build downloads about 150 MB for word timing (faster-whisper). Without it, cues
use estimated word times.
After these downloads, local speech and cached projects can build offline. New Gemini speech
needs network access and uses your API account. Optional browser captures need Playwright
and Chromium; see [screens.md](skills/make-video/references/screens.md).

## Run an example

This example needs no speech model:

```sh
skills/make-video/scripts/new-project.sh ./art-video --example event
cd ./art-video
./make.sh storyboard
./make.sh preview
```

Open `storyboard.html` to inspect the scenes. The preview is `out/art-video.mp4`.

To watch the film while you edit it, run `./make.sh studio` and open the URL it prints. It plays the
real frames with the audio mix, highlights each word of the script as it is spoken, and reloads when
you save a scene file or `video.json`. Nothing is encoded.

```sh
./make.sh film --quality final
python3 storyboard.py --final
```

The final render replaces the preview at the same path. SRT and VTT files are always written;
a video with no script lines has empty captions.

Other examples:

| Example | Use | Format | Finished preview |
|---|---|---|---|
| `lesson` | A short water-cycle lesson | Landscape | [MP4](docs/examples/lesson.mp4) · [Frame](docs/examples/lesson.jpg) |
| `event` | A fictional art-workshop announcement | Portrait | [MP4](docs/examples/event.mp4) · [Frame](docs/examples/event.jpg) |
| `diagram` | A community-garden planning diagram | Square | [MP4](docs/examples/diagram.mp4) · [Frame](docs/examples/diagram.jpg) |

Omit `--example` for the original sample with code and pipeline scenes.
See [example prompts](skills/make-video/references/examples.md).

## Configure a video

Set options in the generated project's `video.json`:

```json
{
  "output": { "format": "portrait", "quality": "final" },
  "fps": 30,
  "narration": { "mode": "none" },
  "music": { "style": "pop" }
}
```

This is a partial configuration. Keep the project's `name` and `scenes` fields.
Narration modes are `tts`, `recorded`, and `none`. Music styles are `pop`, `chip`, and `none`.
The `tts` mode selects Gemini through `narrate` when `GEMINI_API_KEY` is set, and Kokoro otherwise.
Use `narration.narrate` to set Gemini `voice`, `model`, and `style`. Top-level `voice`, `speed`,
and `lang` control Kokoro. `./make.sh doctor` reports the selected provider.
Each new project gets a saved music seed that varies the key, chords, melody, rhythm, and sounds.
Edits keep that seed. Run `./make.sh music --new` for a different track, then rebuild the storyboard
or film to include it. The built-in generator varies music within the selected style.
See [script settings](skills/make-video/references/script.md) and
[audio settings](skills/make-video/references/audio.md).

Scene code uses the selected frame dimensions. The supplied examples adapt to all three formats.
Custom scenes must arrange their content for the selected format. Word-based cue times are
estimates; use explicit time cues or adjust offsets after listening when exact timing matters.

## Check and repair setup

Inside a generated project:

```sh
./make.sh doctor       # check versions, encoders, packages, and fonts
./make.sh setup        # install project dependencies and default fonts
./make.sh validate     # check the script and scene functions
```

A failed setup leaves the project files in place. Fix the reported problem, then run
`./make.sh setup` in that folder. Do not run `new-project.sh` again in a nonempty folder.
For manual fonts or offline models, see [fonts.md](skills/make-video/references/fonts.md) and
[audio.md](skills/make-video/references/audio.md).

Render time depends on the number of frames, scene complexity, CPU, and worker count. Use
`./make.sh studio` or `./make.sh preview` for iteration. The default worker count is half of the CPU
threads, at most 8; lower it with `--workers N` if memory is limited. Renders keep each scene's
encoded chunk in `out/cache/` and encode again only the scenes whose frames changed. In one check,
an 11-minute 1080p/60 fps film took 58 seconds to render the first time on an 18-core M5 Max, 22
seconds with no change, and 28 seconds after a change to one scene.
Motion blur with `--blur 4` draws four subframes for each output frame.

In one local check on arm64 macOS 26.5.2, project setup took 2.7 seconds with cached npm packages
and fresh font downloads. Encoding the 30-second sample at 1080p/30 fps took about 7 seconds with
two workers. That encoding time excludes speech, music, and mixing. A first run on a new machine
also needs package and model downloads; network speed can dominate setup time.

## Development

Run `python3 -m unittest discover -s tests`. Run `python3 tests/smoke_music.py` for music generation
and `python3 tests/smoke.py` for complete builds with recorded and silent audio.
See [tests/README.md](tests/README.md) for coverage and prerequisites.

## License

MIT. Setup downloads Atkinson Hyperlegible and JetBrains Mono under the SIL Open Font License,
including their license files. Keep those files when sharing the fonts. The Kokoro model uses
Apache 2.0. Supplied recordings and other assets keep their own license terms.
