---
name: make-video
description: >-
  Make a short narrated film (an explainer, a product intro, a feature announcement, a walkthrough
  of code or a design) from a prompt. Every frame is drawn in code on a canvas, with a local AI voice
  (Kokoro), a score made in code, word-timed cues, burned-in captions, and .srt/.vtt files. The flow:
  prompt, then a storyboard page with the real voice and music that the user iterates on, then the
  full 1080p render. Real frames are sampled and checked at every step. Use when the user asks
  to "make a video", "make an intro/explainer/announcement video", "a narrated walkthrough of this
  PR/feature/repo", "turn this into a video", or wants to change the storyboard, script, voice,
  music or look of a film made this way.
---

# make-video

Make a narrated film from a prompt. Every frame is a pure function of time `t`, drawn on a canvas
(`@napi-rs/canvas`) and encoded with ffmpeg. The voice is generated locally with Kokoro. The music
is synthesized in Python. Every picture is timed to the word in the voice that names it.

**The flow is fixed:** prompt → **storyboard** (real voice, real music, one real frame per scene) →
the user iterates on the storyboard → **full render**. Do not render the full film before the user
approves the storyboard. Sample real frames at every step and fix what you see before you show it.

`<skill>` below means the folder that holds this SKILL.md.

## Requirements

`node` 20+, `ffmpeg`, `uv` (it runs the Python scripts and installs their dependencies), and `python3`.
`./make.sh setup` checks for them. The Kokoro model (~115 MB) downloads once, on the first voice
run, to `~/.cache/make-video/models`. Fonts are not shipped: see `references/fonts.md`.

## 1. Understand the film (from the prompt)

Read what the film is about before you write a line: the PR, the repo, the docs, the app, the
announcement. Find the real things the film can show: real screens, real code, real output.
Decide these, and ask the user only about what you cannot find out yourself:

- **Kind and length.** Feature intro or announcement: 30–75 s, 6–10 scenes, real app screens.
  Explainer: 2–6 min, chapters with title cards, diagrams and code. Rule of thumb: 2.5 words of voice per second.
- **Audience and the one thing** they must know or do at the end.
- **Look.** The `ink` palette (near-black, red accent) or `navy` (deep blue, sky and amber) in
  `theme.mjs`, or the product's own colors and fonts.
- **Music style.** `pop` (bright, upbeat) or `chip` (quiet chiptune), or `none`.

## 2. Make the project

```sh
<skill>/scripts/new-project.sh ~/Developer/<topic>-video <topic>-video
```

This copies `<skill>/template` (a working 30 s sample film) and runs `npm install`. Get the fonts
(`references/fonts.md`). The project is self-contained. Edit these files:

| File | What it is |
|---|---|
| `video.json` | The script: scenes, voice lines, cues, timing, music, the brief for the storyboard |
| `scenes/*.mjs` | One draw function per scene id |
| `theme.mjs` | Palette, fonts, background |
| `music.py` | The score (chords, hooks, instruments), when the defaults do not fit |
| `shots/plan.mjs` | Real app screenshots to capture, when the film shows an app |

Do not edit `timeline.json`. `timeline.py` generates it.

## 3. Write the script (`video.json`)

Read `references/script.md` first. In short: one idea per scene, short plain sentences, open with a
hook, and end with what to do next. A line is a string, or `{"text", "say"}` when the caption and the
spoken form differ (`"video.json"` is said `"video dot jason"`). A **cue** names the word that a
picture lands on: `{"label": "badge", "at": "badge", "sound": "chime"}`. Put a cue on every
important arrival. Fill in `brief` (lede, approach, open questions); the storyboard shows it.

## 4. Draw the scenes (`scenes/*.mjs`)

Read `references/drawing.md` (the scene API, helpers, layout and motion rules). Each scene gets
`(ctx, t, S)`. Put each arrival on `S.cue(label)` or `S.w('word')`, and make each element leave by
`S.tout`. Use real material:
- **App screens:** capture the real UI with `shots/capture.mjs` and show it with `screens.mjs`
  (camera, cursor, rings). See `references/screens.md`.
- **Code:** `code.mjs` reads the real file by line number, so a quote cannot be wrong.
- **Program output:** run the real program and draw its real output. Do not draw output you have not seen.

**Sample while you draw.** After each scene, run `./make.sh scene <id>` and look at `out/sheet.jpg`
before you go to the next scene. For each tricky move or transition, run `./make.sh clip A B` and
watch `out/clip.mp4`. `references/review.md` has the checklist.

## 5. The storyboard: the user iterates here

```sh
./make.sh storyboard
```

This runs voice → timeline → music → audio mix → one frame per scene → `storyboard.html`: a
self-contained page with the real voice-and-music mix, a frame of every scene, the script with each
cue word marked, the timecodes, and the brief. Playing it highlights the current scene and line.

Before you show it, look at every frame in `out/board/` and fix what is wrong. Then give the
user the page. If your harness can publish an HTML page or an artifact, publish
`storyboard.html` and share the link. If not, give the file path to open in a browser.

Then iterate with the user. Each change is small and fast: edit a line in `video.json` (only the
changed lines are voiced again), move a cue, change a scene's energy, restyle, redraw a scene. Then
run `./make.sh storyboard` again. Keep the brief's open questions up to date. Stay in this loop
until the user approves the storyboard.

## 6. The full render

Only after the user approves:

```sh
./make.sh film            # or: ./make.sh film --blur 4   (motion blur, ~4x slower)
```

This writes `out/<name>.mp4` (1920×1080, 60 fps, AAC, loudness −16 LUFS), `out/<name>.srt`, and
`out/<name>.vtt`. Then check the real output, not the code (see `references/review.md`, "Final check"):
pull frames from the encoded MP4, confirm the duration and the streams, and listen to the mix at
the points that changed. Run `python3 storyboard.py --final` to make the storyboard page hold the
finished film. Deliver the MP4, the captions, and the storyboard. If the film is an announcement,
offer a short post to go with it, written from the same script.

## Commands

| Command | Does |
|---|---|
| `./make.sh storyboard` | Voice, timeline, music, mix, board frames, storyboard.html |
| `./make.sh scene ID [0.3,0.6,0.9]` | Stills at fractions of one scene, plus `out/sheet.jpg` |
| `./make.sh samples [24]` | Stills spread over the whole film, plus `out/sheet.jpg` |
| `./make.sh stills 3,20.5` | Stills at exact seconds, plus `out/sheet.jpg` |
| `./make.sh clip A B` | `out/clip.mp4`: seconds A to B of the real film, with sound |
| `./make.sh voice` / `music` / `timeline` | One step only |
| `./make.sh film [--blur N]` | The full render and mix |
| `uv run tts.py --voices` | List the Kokoro voices |

## References

- `references/script.md`: how to write the voice-over, and all of `video.json`
- `references/drawing.md`: the scene API, the `lib.mjs` helpers, layout, motion, scene patterns
- `references/screens.md`: capturing real app screens and moving a camera over them
- `references/audio.md`: voices, music styles, cue sounds, the mix, extra audio
- `references/review.md`: how to sample, the polish checklist, the final check
- `references/fonts.md`: where to get fonts
