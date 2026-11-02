# General examples

Each example uses the same scene API and build commands. Start with:

```sh
"<skill>/scripts/new-project.sh" ./my-video --example lesson
cd ./my-video
./make.sh storyboard
./make.sh preview
```

Use `lesson`, `event`, or `diagram` as the example name. The example configuration is copied to
`video.json`. Its scene code is in `scenes/examples.mjs`. Edit the content and cues together.

| Example | Example request | Included output |
|---|---|---|
| `lesson` | “Explain the water cycle to a class. Show each step as it is named.” | Landscape, generated narration, three steps |
| `event` | “Make a short portrait announcement for an art workshop. Use music and text, with no speech.” | Portrait, no narration, scene-relative cues |
| `diagram` | “Explain our community garden plan with a square video and a simple diagram.” | Square, generated narration, three connected steps |

The event details are fictional. Replace the time and place before use. Match the audience's
reading speed, and leave enough time to read each completed diagram.

To use recorded narration, set `narration.mode` to `recorded`, copy the recording into the project,
and give each line an `audio` path. Use `from` and `to` to select sections from one recording.
See [audio.md](audio.md) for an example. No speech model is downloaded in this mode.
