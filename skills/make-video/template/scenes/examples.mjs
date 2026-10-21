// General examples. The content lives in each scene's visual field in video.json.
import { W, H, C, MONO, text, label, box, arrow, wrap, P } from '../lib.mjs';

function heading(ctx, value, t, S) {
  const size = W < 1400 ? 62 : 82;
  const rows = wrap(ctx, value, W - 180, size, 700);
  rows.forEach((row, i) => text(ctx, row, W / 2, 200 + i * (size + 10), size, t, S.tin, S.tout, { align: 'center', weight: 700 }));
}

function steps(ctx, t, S) {
  const { title, items } = S.visual;
  heading(ctx, title, t, S);
  const vertical = W < 1400;
  const width = vertical ? W - 260 : (W - 280) / items.length - 50;
  const height = vertical ? 140 : 220;
  const gap = vertical ? 60 : 75;
  const x0 = (W - (vertical ? width : items.length * width + (items.length - 1) * gap)) / 2;
  const y0 = vertical ? Math.max(360, (H - items.length * (height + gap)) / 2) : H / 2 - 90;
  items.forEach((item, i) => {
    const x = x0 + (vertical ? 0 : i * (width + gap));
    const y = y0 + (vertical ? i * (height + gap) : 0);
    const cue = S.cue(`step-${i + 1}`), active = t >= cue;
    box(ctx, x, y, width, height, t, S.tin + i * 0.1, S.tout, { stroke: active ? C.accent : C.faint, fill: active ? C.accentFill : C.fill });
    label(ctx, String(i + 1).padStart(2, '0'), x + 24, y + 38, 24, active ? C.accent : C.faint, { font: MONO, alpha: P(t, S.tin, 0.5) * (1 - P(t, S.tout, 0.3)) });
    const rows = wrap(ctx, item, width - 80, 38, 700);
    rows.forEach((row, n) => text(ctx, row, x + width / 2, y + height / 2 + 20 + n * 44 - (rows.length - 1) * 22, 38, t, cue - 0.1, S.tout, { align: 'center', weight: 700 }));
    if (i) {
      if (vertical) arrow(ctx, x + width / 2, y - gap + 12, x + width / 2, y - 12, t, cue - 0.2, S.tout, C.accent);
      else arrow(ctx, x - gap + 12, y + height / 2, x - 12, y + height / 2, t, cue - 0.2, S.tout, C.accent);
    }
  });
}

export default {
  lesson: steps,
  diagram: steps,
  event(ctx, t, S) {
    heading(ctx, S.visual.title, t, S);
    const width = W - 200, height = Math.min(H * 0.42, 650), y = (H - height) / 2 + 30;
    box(ctx, 100, y, width, height, t, S.tin, S.tout, { stroke: C.accent, fill: C.accentFill });
    S.visual.items.forEach((item, i) => {
      const rows = wrap(ctx, item, width - 100, 44, i === 0 ? 700 : 400);
      rows.forEach((row, n) => text(ctx, row, W / 2, y + 100 + i * (height - 150) / Math.max(1, S.visual.items.length - 1) + n * 50, 44, t, S.cue(`step-${i + 1}`), S.tout, { align: 'center', weight: i === 0 ? 700 : 400, color: i === 0 ? C.accent : C.fg }));
    });
  },
};
