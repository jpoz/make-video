// The sample film's scenes. One function per scene id in video.json: draw(ctx, t, S).
// t is the film time in seconds; S is the scene (S.start, S.end, S.tin, S.tout, S.cue(label), S.w(word), S.line(i)).
// Put every arrival on a cue or a word, and give every element a way out before S.end.
import { W, H, C, MONO, P, lerp, expoOut, text, label, measure, box, arrow, chip, tick, ripple, withAlpha } from '../lib.mjs';
import { snippet, lineOf, drawCode, codeSize } from '../code.mjs';

export default {
  intro(ctx, t, S) {
    const k = S.cue('title');
    // a film strip slides in under the title
    withAlpha(ctx, P(t, S.start, 0.6) * (1 - P(t, S.tout, 0.4)), () => {
      const x0 = lerp(-400, 0, P(t, S.start, 1.4, expoOut));
      for (let i = 0; i < Math.ceil(W / 120); i++) box(ctx, x0 + 160 + i * 120, H * 0.61, 96, 64, t, S.start + 0.1 + i * 0.05, S.tout, { stroke: C.ghost, fill: C.fill, r: 8 });
    });
    text(ctx, 'make-video', W / 2, H * 0.48, W < 1400 ? 130 : 180, t, k - 0.1, S.tout, { align: 'center', weight: 700, stagger: 0.05 });
    ripple(ctx, W / 2, H * 0.44, t, k, 40, Math.min(W * 0.4, 520), C.accent);
    text(ctx, 'a script in, a narrated film out', W / 2, H * 0.76, W < 1400 ? 36 : 44, t, S.cue('film') - 0.1, S.tout, { align: 'center', color: C.mute });
  },

  pipeline(ctx, t, S) {
    const steps = ['script', 'voice', 'timeline', 'music', 'mix'];
    const vertical = W < 1400;
    const bw = vertical ? 520 : 270, bh = vertical ? 100 : 150, gap = vertical ? 32 : 70;
    const x0 = W / 2 - (vertical ? bw : 5 * bw + 4 * gap) / 2;
    const y0 = vertical ? (H - (5 * bh + 4 * gap)) / 2 - 30 : 420;
    steps.forEach((s, i) => {
      // all five outlines draw in at the start, so the shape is there before the voice names each part
      const tin = S.tin + i * 0.1, k = S.cue(s), next = steps[i + 1] ? S.cue(steps[i + 1]) : S.tout;
      const lit = P(t, k, 0.25) * (1 - P(t, next, 0.3));
      const x = x0 + (vertical ? 0 : i * (bw + gap)), y = y0 + (vertical ? i * (bh + gap) : 0);
      box(ctx, x, y, bw, bh, t, tin, S.tout, { stroke: lit > 0.5 ? C.accent : C.faint, fill: lit > 0.5 ? C.accentFill : C.fill, r: 18 });
      text(ctx, s[0].toUpperCase() + s.slice(1), x + bw / 2, y + bh / 2 + 14, 40, t, k - 0.1, S.tout, { align: 'center', weight: 700 });
      label(ctx, String(i + 1), x + 20, y + 36, 22, C.faint, { font: MONO, alpha: P(t, tin + 0.3, 0.3) * (1 - P(t, S.tout, 0.3)) });
      if (i > 0) {
        if (vertical) arrow(ctx, x + bw / 2, y - gap + 5, x + bw / 2, y - 5, t, tin + 0.2, S.tout);
        else arrow(ctx, x - gap + 12, y + bh / 2, x - 12, y + bh / 2, t, tin + 0.2, S.tout);
      }
    });
    // the timeline step names its job underneath
    text(ctx, 'pictures follow the narration', W / 2, vertical ? y0 + 5 * bh + 4 * gap + 65 : y0 + bh + 80, 32, t, S.cue('timeline') + 0.4, S.tout, { align: 'center', color: C.mute });
  },

  code(ctx, t, S) {
    // read the real lines of this scene from video.json, so the panel can't drift from the file;
    // two ranges: the scene's settings, then (after a ⋯ gap) its cues
    const first = lineOf('video.json', '"id": "code"') - 1, cues = lineOf('video.json', '"cues"', first);
    const snip = snippet('video.json', [first, first + 3], [cues, cues + 2]);
    const cueLine = cues + 1;
    let fs = 36, size = codeSize(ctx, snip, fs);
    while (size.w > W - 160 && fs > 20) { fs -= 1; size = codeSize(ctx, snip, fs); }
    const g = drawCode(ctx, snip, (W - size.w) / 2, (H - size.h) / 2 - 60, t, { tin: S.tin, tout: S.tout, fs,
      hl: [[S.line(0) + 0.2, first + 1], [S.cue('cue'), cueLine]] });
    const note = 'cue → one word of the voice', nw = measure(ctx, note, 26, 500, MONO) + 26 * 1.2;
    if (g) chip(ctx, note, g.x + g.w - nw, g.y + g.h + 36, t, S.cue('cue') + 0.2, S.tout, { fill: C.accent, color: '#fff' });
  },

  outro(ctx, t, S) {
    const k = S.cue('end');
    const rows = [['Storyboard first.', S.tin, H / 2 - 70, C.fg], ['Then the full film.', k - 0.2, H / 2 + 70, C.accent]];
    const fs = W < 1400 ? 64 : 84;
    for (const [str, tin, y, color] of rows) {
      text(ctx, str, W / 2 - 30, y, fs, t, tin, S.tout, { align: 'center', weight: 700, color });
      tick(ctx, W / 2 + measure(ctx, str, fs, 700) / 2 + 30, y - 25, 26, t, tin + 0.6, S.tout);
    }
  },
};
