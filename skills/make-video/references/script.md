# Writing the script (`video.json`)

## How the voice-over should sound

- **One idea per scene.** A scene is 1–3 lines and 4–12 seconds. If a scene needs a list, the
  picture carries the list and the voice names it once.
- **Short, plain sentences**, as you would say them out loud: "Now it takes one click. Pick a template."
  Use no jargon that the picture does not explain. Use contractions only where they sound natural.
- **Open with a hook:** the change, the problem, or the surprise. "Sharing a report used to take
  four steps." Then **why**, then **how**, then **what to do now**. End on a short call to
  action: "So open a report, and try it!"
- **Every line earns a picture.** If nothing on screen changes during a line, cut the line or add a cue.
- **Name things as the product names them**, and use the exact words of the real UI, so the cursor
  and the rings land on the same words the voice says.
- **Do not claim what you have not checked.** Check each number, name and behavior against the
  code, the docs or the running app. The storyboard brief is a good place to list these checks.
- **Lines of 5 words or more.** Kokoro sounds clipped on very short lines. Join "Pick a template." to the
  line before it, or keep it on its own only for effect.
- **Explainers:** use chapters with title cards (`card` scenes). Recap at the end. Speak code names
  in their written form in the caption (`text`) and their spoken form in `say`.

## Caption form and spoken form

```json
{ "text": "Call render_frame() once per tick.", "say": "Call render frame once per tick." }
```

`text` is the caption, and the cue words match against it. `say` is what Kokoro reads. Spell out
acronyms letter by letter ("A P I"), file names ("config dot Y A M L"), and symbols ("hex three F").
Listen to the storyboard. If a word sounds wrong, change `say`, never `text`.

## `video.json` reference

```jsonc
{
  "name": "reports-intro",         // output file name: out/reports-intro.mp4
  "title": "Shared reports",       // storyboard title
  "fps": 60,
  "voice": "af_heart", "speed": 1.0, "lang": "en-us",   // see audio.md for voices
  "captions": true,                // burned-in captions (the .srt/.vtt files are always written)
  "source": "~/Developer/myrepo",  // root for code.mjs snippet() paths (default: the project)
  "music": { "style": "pop", "bpm": 112, "snap": true }, // snap: cues move to the nearest eighth note
  "timing": { "gap": 0.35, "lead": 0.5, "tail": 0.8, "min": 4.0 },
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

- **Scene length** = the largest of `min`, or `lead` + the voice + the gaps + `tail`.
- **Cue time** is an estimate from the word's position in its line (characters / line length × line
  length in seconds). It is usually within 0.1 s. When a cue must hit the exact syllable, use `offset`.
- **`card` scenes** without a draw function use the built-in chapter card. Give the scene a draw
  function of the same id to replace it.
- **Changing one line** voices only that line again (the cache key is the voice, speed, language and `say`).

## The brief

`brief.lede` is one or two sentences about what the film is and who it is for. `brief.approach` is
the 2–5 choices that shape the film ("Show the real screens, say it plainly", "Every claim checked
against the code"). `brief.questions` holds what the user must decide. Remove each answered question.
