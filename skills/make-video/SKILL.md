---
name: make-video
description: >-
  Create or revise short videos from a prompt, source material, or an existing make-video
  project. Use for explainers, lessons, announcements, narrated diagrams, and app or code
  walkthroughs. Produces a review storyboard, an MP4, and caption files with local rendering.
---

# make-video

Create a video with scenes drawn on a canvas and encoded by ffmpeg. Use generated speech,
a supplied recording, or no narration. Music is optional. Projects contain their own source files.

For generated speech, use `narrate` when `GEMINI_API_KEY` is set; otherwise use local Kokoro voices.
The commands select the provider automatically. Gemini receives the spoken text through `narrate`.
Read [references/audio.md](references/audio.md) for voice and delivery controls.

Use a storyboard for review by default. If the user has already approved the content, or asks
for automatic completion, continue through the final render without another approval step.
Keep the user's requested subject, style, length, and output format.

`<skill>` means the folder that contains this file. Quote paths that contain spaces.

## 1. Establish the brief

Read the supplied material before writing the script. Find real screens, code, images, or output
that can support the video. Ask only for information that materially affects the result and is
not available from the source material.

Choose reasonable defaults for missing preferences:

- Audience, purpose, and the main point to remember.
- Length: 30–75 seconds for an announcement; 2–6 minutes for a longer explanation.
- Format: landscape, portrait, or square. Use landscape if no destination is given.
- Narration: generated speech (`tts`), supplied audio (`recorded`), or `none`.
- Look: the supplied brand, or a palette from `theme.mjs`.
- Music: `pop`, `chip`, or `none`.

New projects save a random `music.seed` and use it to compose their music. Keep that seed during
revisions. For a different track, or a new video copied from an existing project, run
`./make.sh music --new`. Choose the style and tempo for the subject; see
[references/audio.md](references/audio.md) for music controls.

These are starting points. Lessons do not need a sales message, and announcements do not need
chapters. See [references/examples.md](references/examples.md) for examples outside software.

## 2. Create or open the project

For a new project, choose a folder in the user's workspace:

```sh
"<skill>/scripts/new-project.sh" ./my-video
cd ./my-video
```

This copies the template, checks tools, installs the locked Node packages, and downloads the
default fonts with their license files. Requirements: Node.js 20+, npm, ffmpeg with ffprobe,
Python 3.10+, and uv. Gemini speech also needs `narrate` on PATH. Local speech uses Python
3.10–3.12 through uv and downloads its model on the first local TTS run.
See [references/audio.md](references/audio.md) for offline setup.

Use `./make.sh doctor` for setup problems. Reuse an existing project when revising a video.
Do not replace its scenes or configuration with the sample template.

Edit `video.json` for the script, format, narration, and music. Edit `scenes/*.mjs` for pictures,
and `theme.mjs` for colors and fonts. Do not edit generated `timeline.json`.

## 3. Build the script and scenes

Read [references/script.md](references/script.md) for the configuration and cue format.
Read [references/drawing.md](references/drawing.md) when drawing scenes.

Each scene receives `(ctx, t, S)`. Draw deterministically: workers can render frames out of order.
Use `W`, `H`, and `SAFE` for layout. Portrait and square frames need their own arrangement;
changing output dimensions does not reflow custom scene code automatically.

Use cues to place important changes near the words that describe them. Word-based cues are
estimates from text positions, not measured speech timestamps. Check critical timing with sound.
For exact placement, use a scene-relative `time` cue or adjust `offset` after listening.

Read conditional references only when needed:

- Characters, hands with props, springs and follow-through: [references/animation.md](references/animation.md).
- Real app screens: [references/screens.md](references/screens.md).
- Voices, recordings, and music: [references/audio.md](references/audio.md).
- Custom fonts: [references/fonts.md](references/fonts.md).

Use real source material when the video makes claims about it. `code.mjs` reads file contents;
check that the chosen lines support the explanation. Run a program before showing its output.

Run `./make.sh validate` before a long build. During drawing, use `./make.sh scene ID` and inspect
`out/sheet.jpg`. These commands build missing or stale audio and timing data. Use `./make.sh clip A B`
for transitions and precise timing. See [references/review.md](references/review.md).

## 4. Review the storyboard

```sh
./make.sh storyboard
```

This creates `storyboard.html` with the real audio mix, one frame per scene, the script, cue
markers, and the brief. Inspect every frame in `out/board/` before sharing the page.
Share a local file or a private artifact supported by the environment. Publish externally only
when the user requests it.

When review is requested, apply feedback and rebuild. Only changed speech lines are generated
again. Keep `brief.questions` limited to unanswered questions. If the user has authorized automatic
completion, use the storyboard for your own checks and continue.

## 5. Render and deliver

```sh
./make.sh preview                  # half-size output, at most 30 fps
./make.sh film --quality final     # full size at the configured fps
```

Both commands write `out/<name>.mp4`, `.srt`, and `.vtt`; the later render replaces the earlier one.
`out/render.json` records the actual dimensions, frame rate, and duration. Use `--workers N` to
limit parallel work. Optional `--blur N` adds motion blur and increases render time.

Check the encoded video: streams, duration, sample frames, and audio at important transitions.
Then run `python3 storyboard.py --final` to embed the film in the review page. Deliver the MP4,
caption files, and storyboard. State any checks that the available tools could not perform.

## Commands

| Command | Result |
|---|---|
| `./make.sh setup` / `doctor` / `fonts` | Install dependencies, check setup, or fetch fonts |
| `./make.sh validate` | Check script inputs and scene functions |
| `./make.sh storyboard` | Audio, timeline, board frames, and storyboard page |
| `./make.sh scene ID [0.3,0.6,0.9]` | Scene stills and a contact sheet |
| `./make.sh samples [24]` / `stills 3,20.5` | Sample frames and a contact sheet |
| `./make.sh clip A B` | A short video with audio |
| `./make.sh voice` / `timeline` | Rebuild voice timing or the timeline |
| `./make.sh music` | Rebuild the selected music and audio mix |
| `./make.sh music --new` | Save a new music seed and rebuild the audio |
| `./make.sh preview` / `film` | Render the video and mix its audio |
| `uv run tts.py --voices` | List local speech voices |
| `narrate -voices` | List Gemini speech voices |
