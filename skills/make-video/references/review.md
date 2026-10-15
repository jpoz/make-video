# Sampling and review

You cannot see a film by reading its code. Render real frames and **look at them** (open the
image files). Do this at every step, and fix problems before the user sees them.

## When to sample

| When | Command | Look for |
|---|---|---|
| After you draw or change a scene | `./make.sh scene <id> 0.2,0.5,0.8,0.95` | The layout, overlaps, text size, an empty frame |
| At each transition, each camera move or cursor click, each cue-heavy moment | `./make.sh clip A B` (2–5 s) | Motion: easing, timing against the voice, jumps, flicker |
| Before every storyboard | `./make.sh storyboard`, then look at `out/board/*.jpg` | Each scene at its fullest |
| Before you ask for approval | `./make.sh samples 24` | The whole film at a glance: rhythm, empty stretches, consistency |
| After the full render | "Final check" below | The real encoded output |

`out/sheet.jpg` is a contact sheet of the last stills run. Each still is named by its time, so a
problem points straight to `--stills <t>` for a full-size look.

## The polish checklist

Layout
- No text overflows its box, and no text touches the frame edge (keep a 100 px margin).
- Content stays above the caption band (y < 950) and below the chapter bar (y > 100).
- Things that should line up do: centers, baselines, equal gaps. The layout is measured, not guessed.
- Text is large enough to read in a small player: labels 28 px or more, code 26 px or more.
- Nothing overlaps unless it is meant to, and the cursor does not hide the thing it points at.

Timing
- Each picture lands on (or just before) its word. Check this in a clip with sound, not in stills.
- No empty frame while the voice speaks, and no frame where the last scene's leftovers sit under the next.
- Each scene's main state holds long enough to read: at least 1.5 s after the last arrival.
- The cue sounds land with their pictures. If a sound lands without a picture, remove the cue's sound.

Look
- One accent color, used with one meaning. No stray default colors (pure #fff or #000 from a helper).
- The fonts are the real ones. If the type looks like Helvetica or Arial, the fonts did not load (`fonts.md`).
- Screenshots are sharp (captured at 2x) and show no loading states or errors.
- Motion is smooth and eased. Nothing pops in on a linear ramp, and nothing jitters (round
  positions for text at rest, if needed).

Voice and words
- The words that sound wrong are fixed in `say`. Numbers and names are checked against the source.
- The captions break in sensible places and match the voice.

## Final check (after `./make.sh film`)

```sh
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of compact out/<name>.mp4
# a frame sheet from the encoded film itself (here: 12 frames, evenly spaced)
ffmpeg -loglevel error -y -i out/<name>.mp4 -vf "fps=12/$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/<name>.mp4),scale=640:360,tile=3x4" -frames:v 1 out/final-sheet.jpg
```

Confirm that the duration matches `timeline.json`, that the video is 1920×1080 h264, and that the
audio is AAC. Look at `out/final-sheet.jpg`. Watch at least the opening, one transition, and the
ending of the MP4 with sound. Report any step that you skipped.
