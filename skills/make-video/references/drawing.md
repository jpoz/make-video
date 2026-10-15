# Drawing scenes

## The scene API

`scenes/*.mjs` files load in name order. Each one exports `default { <sceneId>(ctx, t, S) { ... } }`.
It can also export `async prepare(t)` to load images before a frame is drawn. Split a long film into
one module per chapter (`10-open.mjs`, `20-spec.mjs`, ...). Share helpers with plain `export`.

`t` is the film time in seconds (not the scene time). `S` is the scene:

| | |
|---|---|
| `S.start`, `S.end`, `S.dur` | The scene's limits |
| `S.tin`, `S.tout` | `start + 0.15` and `end − 0.55`: the default times to come in and to go out |
| `S.cue(label)` | The time of a cue from `video.json` (beat-snapped) |
| `S.w('word', nth)` | The estimated time of a word or phrase in the scene's voice |
| `S.line(i)`, `S.lineEnd(i)`, `S.voiceEnd` | The voice line times |
| `S.p(t)` | Progress through the scene, from 0 to 1 |

The frame is 1920×1080. `render.mjs` draws the background, then the scene, then the chapter
bar (y < 80) and the captions (y 990–1046). **Keep content between y 100 and 950.** The frame fades
from black at the start and to black at the end.

## The rules that make it look finished

1. **Every arrival lands on a word or a cue**, a little early (−0.1 to −0.3 s), because the eye
   needs a moment. Use no free-running timers.
2. **Every element leaves.** Give it `tout` (usually `S.tout`) so that the scene clears before the
   next one starts. Do not hard-cut to the next scene with things still on screen, unless a
   carry-over is the point.
3. **Show the structure, then fill it.** Draw outlines or empty slots early, then light each one on
   its cue (see `pipeline` in the sample film). An empty frame for more than about 1 s while the
   voice speaks looks broken.
4. **One thing moves at a time.** Stagger the arrivals by 0.05–0.3 s. Light what the voice names,
   and dim the rest (to about 40%).
5. **Use eases, not linear motion:** `expoOut` and `quartOut` to arrive, `cubicInOut` to move,
   `backOut` (`pop`) for small things that land. Moves take 0.3–0.9 s.
6. **Use large type.** Titles 84–180 px, labels 28–48 px, code 26–36 px, nothing under 20 px.
   Measure before you place: `measure()`, `codeSize()`, `wrap()`. Never guess a width.
7. **Use few colors:** `C.fg`, `C.mute`, `C.faint` and one accent. Each color means one thing
   in the film (for example, red = "look here").
8. **Make it deterministic.** Use `rng(seed)` for any randomness. Every frame must render the same
   alone, because the workers render chunks out of order.

## lib.mjs helpers

Timing: `P(t, t0, d, ease)` (progress from 0 to 1), `vis(t, tin, tout)` (an in/out envelope),
`pop(t, t0)`, `clamp`, `lerp`, eases `cubicInOut quartOut expoOut expoInOut backOut linear`.

Text: `text(ctx, str, x, y, size, t, tin, tout, {align, weight, color, font, whole, stagger})` rises
in letter by letter inside a clip, and returns its width. `label()` is static text. `wrap()` splits a
string into lines that fit a width. `counter()` counts a number up. `font()` and `measure()` are also there.

Shapes: `box(ctx, x, y, w, h, t, tin, tout, {stroke, fill, r, width})` draws its outline in, then
fills. `rrect()` is a static rounded rectangle. `ring()` draws a highlight ring around a rectangle.
`ripple()` is a click or landing pulse. `tick()` is a check mark that pops in. `chip()` is a labelled
pill. `arrow()` and `drawLine(pts, ...)` draw themselves in, with an optional arrowhead. `Path`
and `trim()` let you draw any custom stroke over its length. `withAlpha()` and `rng()` are also there.

Code (`code.mjs`): `snippet(file, [a, b], [c, d, 'nodoc'])` reads the real lines from
`video.json` `source`. `lineOf(file, 'text')` finds a line by its content, so a scene keeps working
when the file changes. `drawCode(ctx, snip, x, y, t, {tin, tout, fs, w, hl: [[time, from, to], ...]})`
draws the panel with a gliding highlight bar, and returns `rowRect(n)` and `colX(col)` for callouts.

App screens (`screens.mjs`): see `screens.md`.

## Scene patterns

- **The title** (wordmark): a big word on its cue, a ripple, and a small line under it on the next cue.
- **Before and after:** show the old way (dim, or a quiet "used to" look), then a clear change, then
  the new way, and land it with a `pop` sound.
- **A diagram that builds:** the boxes draw in, the arrows draw between them, and each box lights when
  the voice names it. At the end, shrink the diagram into a top bar that stays for the rest of the film
  (a "route bar"). The `chapter` field gives a simple form of this for free.
- **A code walk:** one panel, with the highlight gliding from line to line on cues. Dim the rest.
  Put a callout chip next to `rowRect(n)`.
- **A real app walk:** a wide shot of the window, then the camera pushes in on the control, the
  cursor moves to it and clicks, the next screenshot cross-fades in, and a ring marks the result. Pull
  back to wide between steps.
- **Real output:** run the real program in Node (for example, load the real compiled program and call it for every frame)
  or record it, and draw that output.
- **The end:** the call to action and the title, on the final chord of the music.

## Performance

A frame should render in under 30 ms. Cache anything costly, such as text layout, offscreen
canvases, and decoded images, at module level and not per frame. Use `prepare(t)` with a small LRU
cache for large image sequences. Never call `getImageData` in the frame loop: it leaks native
memory in `@napi-rs/canvas`. `render.mjs` uses `canvas.data()`.
