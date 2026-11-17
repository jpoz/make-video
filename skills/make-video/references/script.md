# Writing the script (`video.json`)

## How the voice-over should sound

- **One idea per scene.** A scene is 1–3 lines and 4–12 seconds. If a scene needs a list, the
  picture carries the list and the voice names it once.
- **Short, plain sentences**, as you would say them out loud: "Now it takes one click. Pick a template."
  Use no jargon that the picture does not explain. Use contractions only where they sound natural.
- **Start with the purpose:** a question for a lesson, the main change for an announcement,
  or the result for a demonstration. End with the key point or an appropriate next step.
- **Every line earns a picture.** If nothing on screen changes during a line, cut the line or add a cue.
- **Name things as the product names them**, and use the exact words of the real UI, so the cursor
  and the rings land on the same words the voice says.
- **Do not claim what you have not checked.** Check each number, name and behavior against the
  code, the docs or the running app. The storyboard brief is a good place to list these checks.
- **For Kokoro, prefer lines of 5 words or more.** Short lines can sound clipped. Join "Pick a template." to the
  line before it, or keep it on its own only for effect.
- **Explainers:** use chapters with title cards (`card` scenes). Recap at the end. Speak code names
  in their written form in the caption (`text`) and their spoken form in `say`.

## Caption form and spoken form

```json
{ "text": "Call render_frame() once per tick.", "say": "Call render frame once per tick." }
```

`text` is the caption, and the cue words match against it. `say` is what the speech provider reads. Spell out
acronyms letter by letter ("A P I"), file names ("config dot Y A M L"), and symbols ("hex three F").
Listen to the storyboard. If a word sounds wrong, change `say`, never `text`.

## `video.json` reference

```jsonc
{
  "name": "reports-intro",         // output file name: out/reports-intro.mp4
  "title": "Shared reports",       // storyboard title
  "fps": 60,
  "output": { "format": "landscape", "quality": "final" },
  "narration": { "mode": "tts" },   // GEMINI_API_KEY: narrate; otherwise Kokoro. Also recorded or none.
  "voice": "af_heart", "speed": 1.0, "lang": "en-us",   // Kokoro only; see audio.md for Gemini settings
  "captions": true,                // burned-in captions (the .srt/.vtt files are always written)
  "source": "../myrepo",          // root for code.mjs snippet() paths (default: the project)
  "music": { "style": "pop", "bpm": 112, "snap": true }, // snap: cues move to the nearest eighth note
  "timing": { "gap": 0.35, "lead": 0.5, "tail": 0.8, "min": 4.0 }, // "align": false turns off word timing
  "brief": { "lede": "...", "approach": ["..."], "questions": ["..."] },
  "scenes": [
    {
      "id": "share",               // the draw function's name in scenes/*.mjs
      "chapter": "Sharing",        // optional: shows the chapter bar at the top
      "music": 0.7,                // energy 0..1, or a layer dict (audio.md)
      "lead": 0.5,                 // silence before the first line
      "tail": 0.8,                 // time after the last line, for the picture to finish
      "min": 6.0,                  // the shortest the scene may be
      "lines": [
        "Every report now has a share button: one link for the team.",
        { "text": "The link opens in read-only mode.", "say": "The link opens in read only mode." }
      ],
      "cues": [
        { "label": "button", "at": "share button", "sound": "chime" },
        { "label": "lock", "at": "read-only", "sound": "lock", "offset": 0.1, "snap": false },
        { "label": "link", "at": "link", "nth": 1 }
      ]
    },
    { "id": "card-2", "card": { "kicker": "Chapter 2", "title": "How links work" }, "min": 3.2, "music": 0.4 }
  ]
}
```

Project creation adds `music.seed` automatically. Keep it during edits so the music stays the
same. Use `./make.sh music --new` for a new composition; see [audio.md](audio.md).

- **Scene length** = the largest of `min`, or `lead` + the voice + the gaps + `tail`.
- **Cue time** is the measured start of the word. `align.py` listens to each voice line with a small
  Whisper model and writes `out/words.json`. `timeline.py` gives each word of `text` a `[start, end]`
  mark in `timeline.json`. When `say` differs from `text` ("video.json" said "video dot jason"), the
  text word takes the times of the spoken words in its place. A line where fewer than half of the
  words match, or that could not be measured, uses an estimate from the word's position in the text.
  `timeline.py` prints how many lines were measured. Measured times can still be off by about 0.1 s:
  listen at critical cues, and use `offset` for a deliberate lead or delay.
- **Captions** start when their first word is spoken and stay until the next caption starts.
- **Explicit cues** use `{"label": "reveal", "time": 2.5}`: seconds from the scene start. They work
  without narration and do not snap to the music unless `snap: true` is set on that cue. Use either
  `at` or `time`, not both. Every cue must remain within its scene after offset and beat snapping.
- **Formats:** `landscape` = 1920×1080, `portrait` = 1080×1920, `square` = 1080×1080.
  `preview` quality halves each dimension and caps the frame rate at 30. `final` uses full size.
  The renderer accepts `--quality`, `--workers`, `--fps`, and `--blur` overrides, and `--fresh` to
  encode every chunk again. `output.workers` is optional; the default is half of the CPU threads, at most 8.
- **Names and IDs:** use letters, digits, hyphens, and underscores, starting with a letter or digit.
  Scene IDs and cue labels must be unique in their scope. Output names `video`, `clip`, and
  `clip-silent` are reserved for intermediate files.
- **No narration:** set `narration.mode` to `none`. A text line can specify `duration` in seconds.
  Otherwise its display time is estimated at 2.5 words per second, with a one-second minimum.
  Scenes without lines use `min` for their duration. Captions still come from script lines.
- **Recorded narration:** set `narration.mode` to `recorded`; every line needs an `audio` path.
  See [audio.md](audio.md) for recording ranges. `voice`, `speed`, and `say` do not change recordings.
- **`card` scenes** without a draw function use the built-in chapter card. Give the scene a draw
  function of the same id to replace it.
- **Changing one line** voices only that line again. The cache includes the provider, its voice
  settings, and `say`. Changes to Gemini voice, model, and style also invalidate speech timing.

## The brief

`brief.lede` is one or two sentences about what the film is and who it is for. `brief.approach` is
the 2–5 choices that shape the film ("Show the real screens, say it plainly", "Every claim checked
against the code"). `brief.questions` holds what the user must decide. Remove each answered question.
