# make-video

Create short videos with Claude Code, Codex, or another agent that reads `SKILL.md` files.
Use it for lessons, event announcements, diagrams, product introductions, and code walkthroughs.

The agent writes the script, draws scenes, and builds a storyboard with the real audio. You can
review it before the final render, or ask the agent to complete the video automatically.
Rendering is local. Speech can come from Kokoro, your own recording, or be omitted. Music is optional.
No API key is needed.

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

The shell commands target macOS and Linux. Native Windows is not supported; use WSL. CI is
configured for macOS and Ubuntu. Local verification details are in [the checks guide](tests/README.md).

Setup downloads Node packages and the default fonts with their license files. The first audio
build downloads Python packages. The first generated-speech build also downloads about 115 MB
of model files to `~/.cache/make-video/models`. Recorded and silent videos do not need the model.
After these downloads, cached projects can build offline. Optional browser captures need Playwright
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
  "output": { "format": "portrait", "quality": "final", "workers": 2 },
  "fps": 30,
  "narration": { "mode": "none" },
  "music": { "style": "pop" }
}
```

This is a partial configuration. Keep the project's `name` and `scenes` fields.
Narration modes are `tts`, `recorded`, and `none`. Music styles are `pop`, `chip`, and `none`.
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
`./make.sh preview` for iteration. Start with two workers; lower the count if memory is limited.
Motion blur with `--blur 4` draws four subframes for each output frame.

In one local check on arm64 macOS 26.5.2, project setup took 2.7 seconds with cached npm packages
and fresh font downloads. Encoding the 30-second sample at 1080p/30 fps took about 7 seconds with
two workers. That encoding time excludes speech, music, and mixing. A first run on a new machine
also needs package and model downloads; network speed can dominate setup time.

## Development

Run `python3 -m unittest discover -s tests`. Run `python3 tests/smoke.py` for a complete build with
recorded and silent audio. See [tests/README.md](tests/README.md) for coverage and prerequisites.

## License

MIT. Setup downloads Atkinson Hyperlegible and JetBrains Mono under the SIL Open Font License,
including their license files. Keep those files when sharing the fonts. The Kokoro model uses
Apache 2.0. Supplied recordings and other assets keep their own license terms.
