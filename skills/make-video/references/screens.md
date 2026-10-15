# Real app screens

A product intro should show the real product: screenshots of the real UI in a browser window, a camera that
pushes in on each control, a cursor that moves and clicks, and red rings on the result. All of it is
drawn in page coordinates from boxes captured with the screenshots, so it stays on the right element.

## 1. Capture

```sh
npm i -D playwright && npx playwright install chromium
cp shots/plan.example.mjs shots/plan.mjs    # then edit it
node shots/capture.mjs                     # or: node shots/capture.mjs 02-dialog
```

Each step in `plan.mjs` runs its `actions(page)` in order on one page. Then it writes
`shots/out/<name>.png` (1600×900 CSS px at 2x) and `shots/out/<name>.json` (the box of every
selector in `boxes`). Capture one screenshot per visible state: before a click, after it, each
typed letter if typing shows on screen (`05a-type1`, `05a-type2`, ...).

Make captures repeatable:
- Run a **local build** of the app. If it needs an API, answer the API with stubs
  (`page.route('**/api/**', ...)`) and fixed data: realistic names, no real customer data, no secrets.
- Fix the clock, random IDs and avatars with `page.addInitScript` when they show on screen.
- Use selectors that survive restyling: roles, labels, `data-testid`.
- Hide the dev overlays, cookie banners and toasts that are not part of the story.

Look at every PNG before you use it. A capture of a loading spinner or an error page is a common failure.

## 2. Show it in a scene

```js
import { appSegment, bb, mid, WIDE } from '../screens.mjs';

// a segment can span several scenes: t is film time, so draw the same segment from each scene
let SEG;
const seg = S => SEG ??= (() => {
  const tClick = S.cue('new'), tSaved = S.cue('save');
  const [nx, ny] = mid('01-home', 'newButton'), [dx, dy] = mid('02-dialog', 'dialog'), [sx, sy] = mid('03-typed', 'save');
  return {
    t0: S.start, t1: S.end, url: 'app.example.com',
    // camera keys: [time the move ENDS, focusX, focusY, zoom, move duration]
    // wide while the window enters, push in on the button, then frame the whole dialog, then wide again
    cam: [[S.start + 1.2, ...WIDE], [tClick - 0.1, nx, ny, 2.2, 0.9], [tClick + 1.0, dx, dy, 1.5, 0.8], [S.end - 0.7, ...WIDE, 0.8]],
    shots: [[S.start, '01-home'], [tClick + 0.1, '02-dialog'], [tClick + 1.2, '03-typed']],
    rings: [{ box: bb('03-typed', 'save'), tin: tSaved - 0.3, tout: S.end - 0.7 }],
    // cursor keys: [arrival time, pageX, pageY, press time]
    cursor: [[S.start + 0.4, 1200, 700], [tClick, nx, ny, tClick], [tSaved, sx, sy, tSaved]],
  };
})();

export default {
  create(ctx, t, S) { appSegment(ctx, t, seg(S)); },
};
```

- **Camera.** Zoom 1.06 (`WIDE`) shows the whole window. Use 1.8–2.6 for one control, and about 1.5
  for a dialog or a panel. A camera key is the time the move **ends**, so start the push before the
  word. Hold wide for about 1 s while the window enters. Frame the whole area that changes, not only the
  control you click, so the change is not cropped. Keep the camera keys in time order: if the first
  click cue falls in the scene's first second, give the scene a longer `lead`. Moves are in log-zoom (this is built in).
- **Cursor.** Each move takes 0.75 s and ends on its arrival time. The first key is where it waits. Put the press on the cue word, and
  change the screenshot 0.1 s after the press, as the real app would.
- **Rings** draw in from the left and draw out at `tout`. Ring the thing that the voice names, and only one at a time.
- The window rises in at `t0` and sinks out at `t1`. Set `enter: false` or `exit: false` for segments
  that run on from one another. Use `dark: true` for a dark browser frame.
- The cue sounds `click` and `pop` fit cursor presses and finished results.

## Recordings instead of screenshots

For something that moves on its own (a player, an animation, a live chart), record frames with
Playwright, `page.screenshot` in a loop, together with the page's own clock (for example,
`audio.currentTime`). Slow the page down while you record (`playbackRate = 0.25`) to capture densely.
In the scene, pick the recorded frame for the film time and load it in `prepare(t)` with a small cache.
This shows a real web page playing, in sync with the film.
