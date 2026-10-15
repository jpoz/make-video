// Real app screens in a browser window, moved by a camera, with a cursor and highlight rings.
// The screenshots and element boxes come from shots/capture.mjs (shots/out/<name>.png + <name>.json).
// Everything here works in page coordinates (CSS px of the captured page), so rings and the cursor
// stay on their element at any zoom.
import { loadImage } from '@napi-rs/canvas';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { C, SANS, PI, P, clamp, lerp, cubicInOut, expoInOut, expoOut, halves, trim, ripple } from './lib.mjs';

const DIR = fileURLToPath(new URL('./shots/out/', import.meta.url));
export const IMG = {}, BOX = {};
if (existsSync(DIR)) for (const f of readdirSync(DIR).filter(f => f.endsWith('.png'))) {
  const n = f.slice(0, -4);
  IMG[n] = await loadImage(DIR + f);
  if (existsSync(DIR + n + '.json')) BOX[n] = JSON.parse(readFileSync(DIR + n + '.json', 'utf8'));
}
export const PW = 1600, PH = 900, BAR = 40; // captured page size (CSS px); window title bar height
export const bb = (shot, key) => { const b = BOX[shot]?.[key]; if (!b) throw new Error(`no box ${shot}.${key}`); return b; };
export const mid = (shot, key) => { const b = bb(shot, key); return [b.x + b.width / 2, b.y + b.height / 2]; };

// Camera keys: [time, focusX, focusY, zoom, moveDur?] in page px. The move ENDS at its time.
// Zoom 1.06 shows the whole window; 2 to 3 is a close-up on one control.
export const WIDE = [PW / 2, PH / 2 - 10, 1.06];
export function camAt(keys, t) {
  if (t <= keys[0][0]) return keys[0].slice(1, 4);
  for (let i = 1; i < keys.length; i++) {
    const [t1, ...b] = keys[i];
    if (t < t1) {
      const a = keys[i - 1].slice(1), d = keys[i][4] ?? 0.9;
      const p = cubicInOut(clamp((t - (t1 - d)) / d));
      // zoom moves in log space so it feels even
      return [lerp(a[0], b[0], p), lerp(a[1], b[1], p), Math.exp(lerp(Math.log(a[2]), Math.log(b[2]), p))];
    }
  }
  return keys.at(-1).slice(1, 4);
}
export const toScreen = (cam, x, y) => [960 + (x - cam[0]) * cam[2], 540 + (y - cam[1]) * cam[2]];

// Shot schedule: [[time, shotName], ...]. A new shot cross-fades in over FADE seconds.
const FADE = 0.14;
function shotLayers(sched, t) {
  let i = -1;
  for (let k = 0; k < sched.length; k++) if (t >= sched[k][0]) i = k;
  if (i < 0) return [];
  const a = clamp((t - sched[i][0]) / FADE);
  return a < 1 && i > 0 ? [[sched[i - 1][1], 1], [sched[i][1], a]] : [[sched[i][1], 1]];
}

// The browser window, drawn in page space (the camera transform is already applied).
function browserWindow(ctx, cam, layers, url, dark) {
  const chrome = dark ? '#2a2a33' : '#e9e6df', field = dark ? '#1b1b22' : '#fbfaf7', ink = dark ? '#9a9aa8' : '#6b6f78';
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 60 * cam[2]; ctx.shadowOffsetY = 18 * cam[2];
  ctx.fillStyle = chrome; ctx.beginPath(); ctx.roundRect(0, -BAR, PW, PH + BAR, 14); ctx.fill();
  ctx.restore();
  ctx.save();
  ctx.beginPath(); ctx.roundRect(0, -BAR, PW, PH + BAR, 14); ctx.clip();
  ['#ff5f57', '#febc2e', '#28c840'].forEach((c, i) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(22 + i * 22, -BAR / 2, 6.5, 0, 2 * PI); ctx.fill(); });
  ctx.fillStyle = field; ctx.beginPath(); ctx.roundRect(PW / 2 - 260, -BAR + 8, 520, BAR - 16, 7); ctx.fill();
  ctx.fillStyle = ink; ctx.font = `500 14px ${SANS}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(url, PW / 2, -BAR / 2 + 1);
  const base = ctx.globalAlpha;
  for (const [name, a] of layers) {
    if (!IMG[name]) throw new Error(`no screenshot shots/out/${name}.png`);
    ctx.globalAlpha = base * a; ctx.drawImage(IMG[name], 0, 0, PW, PH);
  }
  ctx.restore();
}

// A ring around an element box (page space) that draws in from the left, and draws out.
function hiRing(ctx, cam, b, t, tin, tout, pad = 6, color = C.accent) {
  const pin = P(t, tin, 0.45, expoOut), pout = P(t, tout, 0.35);
  if (pin <= 0 || pout >= 1) return;
  const x = b.x - pad, y = b.y - pad, w = b.width + 2 * pad, h = b.height + 2 * pad, r = Math.min(10, h / 2);
  const width = 6 / cam[2] * 1.06, f = pout > 0 ? 1 - pout : pin;
  for (const hv of halves(x, y, w, h, r)) trim(ctx, hv, 0, hv.len * f, width, color, 'round');
}

export function cursor(ctx, x, y, press = 0) {
  ctx.save(); ctx.translate(x, y); const s = 1.6 * (1 - 0.12 * press); ctx.scale(s, s);
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 22); ctx.lineTo(6, 16.5); ctx.lineTo(10.5, 26); ctx.lineTo(14, 24.4); ctx.lineTo(9.6, 15.2); ctx.lineTo(17.5, 15.2); ctx.closePath();
  ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 1.6; ctx.strokeStyle = '#111'; ctx.lineJoin = 'round'; ctx.stroke(); ctx.restore();
}
// Cursor keys: [arrivalTime, pageX, pageY, pressTime?]. Each move takes MOVE seconds and ends on arrival.
const MOVE = 0.75;
function cursorAt(keys, t) {
  if (!keys.length || t < keys[0][0] - MOVE) return null;
  let pos = [keys[0][1], keys[0][2]];
  for (let i = 1; i < keys.length; i++) {
    const [t1, x, y] = keys[i], p = expoInOut(clamp((t - (t1 - MOVE)) / MOVE));
    pos = [lerp(pos[0], x, p), lerp(pos[1], y, p)];
  }
  let press = 0;
  for (const k of keys) if (k[3] != null) press = Math.max(press, 1 - Math.abs(t - k[3]) / 0.12);
  return { pos, press: clamp(press) };
}

// One app segment: the window on screen with its camera, shots, rings and cursor.
// seg: { t0, t1, url: string | t => string, dark?, enter?, exit?, cam: [...], shots: [...],
//        rings: [{ box, tin, tout, pad? }], cursor: [...], cursorGone? }
export function appSegment(ctx, t, seg) {
  if (t < seg.t0 || t > seg.t1) return;
  const cam = camAt(seg.cam, t);
  const enter = seg.enter === false ? 1 : P(t, seg.t0, 0.8, expoOut);
  const exit = seg.exit === false ? 0 : P(t, seg.t1 - 0.6, 0.6, cubicInOut);
  const dy = (1 - enter) * 700 + exit * 80, s = lerp(0.92, 1, enter) * lerp(1, 0.94, exit);
  ctx.save();
  ctx.globalAlpha *= clamp(enter * 1.5) * (1 - exit);
  ctx.translate(960, 540 + dy); ctx.scale(s, s); ctx.translate(-960, -540);
  ctx.save();
  ctx.translate(960, 540); ctx.scale(cam[2], cam[2]); ctx.translate(-cam[0], -cam[1]);
  browserWindow(ctx, cam, shotLayers(seg.shots, t), typeof seg.url === 'function' ? seg.url(t) : seg.url ?? '', seg.dark);
  for (const r of seg.rings ?? []) hiRing(ctx, cam, r.box, t, r.tin, r.tout, r.pad);
  ctx.restore();
  const cur = cursorAt(seg.cursor ?? [], t);
  if (cur && t < (seg.cursorGone ?? Infinity)) {
    for (const k of seg.cursor) if (k[3] != null) ripple(ctx, ...toScreen(cam, k[1], k[2]), t, k[3], 8, 46);
    cursor(ctx, ...toScreen(cam, ...cur.pos), cur.press);
  }
  ctx.restore();
}
