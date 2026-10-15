// Drawing helpers. Every helper is a pure function of time t: it takes the times an element
// arrives (tin) and leaves (tout), so any frame can be drawn on its own, in any order.
import { C, SANS, MONO } from './theme.mjs';
export { W, H, C, SANS, MONO, DISPLAY } from './theme.mjs';
export const PI = Math.PI;

// ---------- timing ----------
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, x) => a + (b - a) * x;
export const linear = x => x;
export const cubicInOut = x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
export const quartOut = x => 1 - Math.pow(1 - x, 4);
export const expoOut = x => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
export const expoInOut = x => (x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2);
export const backOut = x => { const c1 = 1.4, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
// progress 0..1 of a move that starts at t0 and takes d seconds
export const P = (t, t0, d, e = cubicInOut) => e(clamp((t - t0) / d));
// in/out envelope: 0 before tin, 1 while shown, 0 after tout + d
export const vis = (t, tin, tout = Infinity, d = 0.4) => P(t, tin, d, quartOut) * (1 - P(t, tout, d * 0.8));
// a scale that overshoots a little as a thing lands
export const pop = (t, t0, d = 0.45) => P(t, t0, d, backOut);

// ---------- text ----------
export function font(ctx, size, weight = 400, family = SANS, style = '') { ctx.font = `${style} ${weight} ${size}px ${family}`.trim(); }
export function measure(ctx, str, size, weight = 400, family = SANS) { font(ctx, size, weight, family); return ctx.measureText(str).width; }

// Text that rises into place inside a clip (letters staggered), and rises out.
// o: weight, color, font, align ('left'|'center'|'right'), alpha, whole (no per-letter stagger), stagger
export function text(ctx, str, x, y, size, t, tin, tout = Infinity, o = {}) {
  const weight = o.weight ?? 400, color = o.color ?? C.fg, family = o.font ?? SANS;
  const stagger = o.stagger ?? Math.min(0.018, 0.5 / Math.max(1, str.length));
  const rise = size * 1.15;
  if (t < tin || t > tout + 0.4 + str.length * 0.01) return 0;
  ctx.save();
  font(ctx, size, weight, family, o.style ?? '');
  const width = ctx.measureText(str).width;
  if (o.align === 'center') x -= width / 2;
  if (o.align === 'right') x -= width;
  if (o.alpha != null) ctx.globalAlpha *= o.alpha;
  ctx.beginPath(); ctx.rect(x - 8, y - size * 1.1, width + 16, size * 1.5); ctx.clip();
  ctx.fillStyle = color; ctx.textBaseline = 'alphabetic';
  if (o.whole) {
    const pin = P(t, tin, 0.45, quartOut), pout = P(t, tout, 0.32);
    ctx.fillText(str, x, y + (1 - pin) * rise - pout * rise);
  } else {
    let cx = x;
    for (let i = 0; i < str.length; i++) {
      const pin = P(t, tin + i * stagger, 0.42, quartOut), pout = P(t, tout + i * 0.008, 0.3);
      if (pin > 0 && pout < 1) ctx.fillText(str[i], cx, y + (1 - pin) * rise - pout * rise);
      cx += ctx.measureText(str[i]).width;
    }
  }
  ctx.restore();
  return width;
}
// Plain text, no animation. o: weight, font, align, base (textBaseline), alpha
export function label(ctx, str, x, y, size, color = C.fg, o = {}) {
  ctx.save();
  font(ctx, size, o.weight ?? 400, o.font ?? SANS, o.style ?? '');
  ctx.fillStyle = color; ctx.textAlign = o.align ?? 'left'; ctx.textBaseline = o.base ?? 'alphabetic';
  if (o.alpha != null) ctx.globalAlpha *= o.alpha;
  ctx.fillText(str, x, y);
  ctx.restore();
}
// Word-wrap str to maxW; returns the lines (draw them with text() or label()).
export function wrap(ctx, str, maxW, size, weight = 400, family = SANS) {
  font(ctx, size, weight, family);
  const out = []; let cur = '';
  for (const w of str.split(' ')) {
    const next = cur ? cur + ' ' + w : w;
    if (cur && ctx.measureText(next).width > maxW) { out.push(cur); cur = w; } else cur = next;
  }
  if (cur) out.push(cur);
  return out;
}
// A number that counts from a to b between t0 and t0 + d. o: prefix, suffix, color, ease, + label options
export function counter(ctx, a, b, x, y, size, t, t0, d, o = {}) {
  const v = Math.round(lerp(a, b, P(t, t0, d, o.ease ?? cubicInOut)));
  label(ctx, (o.prefix ?? '') + v.toLocaleString('en-US') + (o.suffix ?? ''), x, y, size, o.color ?? C.fg, o);
}

// ---------- paths: lines that draw themselves ----------
export class Path {
  constructor() { this.p = []; }
  move(x, y) { this.p.push([x, y]); return this; }
  line(x, y) {
    const [x0, y0] = this.p.at(-1), n = Math.max(1, Math.ceil(Math.hypot(x - x0, y - y0) / 4));
    for (let i = 1; i <= n; i++) this.p.push([x0 + (x - x0) * i / n, y0 + (y - y0) * i / n]);
    return this;
  }
  arc(cx, cy, r, a0, a1) {
    const n = Math.max(2, Math.ceil(Math.abs(a1 - a0) * r / 4));
    for (let i = this.p.length ? 1 : 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; this.p.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
    return this;
  }
  cubic(c1x, c1y, c2x, c2y, x, y) {
    const [x0, y0] = this.p.at(-1);
    for (let i = 1; i <= 80; i++) {
      const t = i / 80, u = 1 - t;
      this.p.push([u * u * u * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x, u * u * u * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y]);
    }
    return this;
  }
  done() {
    this.L = [0];
    for (let i = 1; i < this.p.length; i++) this.L.push(this.L[i - 1] + Math.hypot(this.p[i][0] - this.p[i - 1][0], this.p[i][1] - this.p[i - 1][1]));
    this.len = this.L.at(-1);
    return this;
  }
  // point at arc length s: [[x, y], indexBefore, indexAfter]
  at(s) {
    s = clamp(s, 0, this.len);
    let lo = 0, hi = this.L.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (this.L[m] <= s) lo = m; else hi = m; }
    const f = (s - this.L[lo]) / ((this.L[hi] - this.L[lo]) || 1), [a, b] = this.p[lo], [c, d] = this.p[hi];
    return [[a + (c - a) * f, b + (d - b) * f], lo, hi];
  }
}
// Stroke the part of a path between arc lengths s0 and s1.
export function trim(ctx, path, s0, s1, width, color, cap = 'round') {
  s0 = clamp(s0, 0, path.len); s1 = clamp(s1, 0, path.len);
  if (s1 - s0 < 0.5) return;
  const [p0, , i0] = path.at(s0), [p1, j1] = path.at(s1);
  ctx.beginPath(); ctx.moveTo(p0[0], p0[1]);
  for (let i = i0; i <= j1; i++) ctx.lineTo(path.p[i][0], path.p[i][1]);
  ctx.lineTo(p1[0], p1[1]);
  ctx.lineWidth = width; ctx.strokeStyle = color; ctx.lineCap = cap; ctx.lineJoin = 'round'; ctx.stroke();
}
// A polyline that draws in from its first point, and un-draws from its start at tout. head: arrowhead.
export function drawLine(ctx, pts, t, tin, tout = Infinity, width = 4, color = C.mute, d = 0.5, head = false) {
  const p = new Path().move(...pts[0]); for (const q of pts.slice(1)) p.line(...q); p.done();
  const pin = P(t, tin, d, expoOut), pout = P(t, tout, 0.35);
  if (pin <= 0 || pout >= 1) return;
  trim(ctx, p, p.len * pout, p.len * pin, width, color);
  if (head && pin > 0.6 && pout === 0) {
    const [[x, y]] = p.at(p.len * pin), [[x0, y0]] = p.at(Math.max(0, p.len * pin - 6));
    const a = Math.atan2(y - y0, x - x0), k = width * 3.2;
    ctx.save(); ctx.globalAlpha *= clamp((pin - 0.6) / 0.2);
    ctx.beginPath(); ctx.moveTo(x - k * Math.cos(a - 0.55), y - k * Math.sin(a - 0.55)); ctx.lineTo(x, y); ctx.lineTo(x - k * Math.cos(a + 0.55), y - k * Math.sin(a + 0.55));
    ctx.lineWidth = width; ctx.strokeStyle = color; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke(); ctx.restore();
  }
}
export const arrow = (ctx, x1, y1, x2, y2, t, tin, tout = Infinity, color = C.mute, width = 4) =>
  drawLine(ctx, [[x1, y1], [x2, y2]], t, tin, tout, width, color, 0.45, true);

// ---------- boxes ----------
// A rounded box outline as two halves from the middle of its left side.
export function halves(x, y, w, h, r) {
  const m = y + h / 2;
  return [
    new Path().move(x, m).line(x, y + r).arc(x + r, y + r, r, PI, 1.5 * PI).line(x + w - r, y).arc(x + w - r, y + r, r, -PI / 2, 0).line(x + w, m).done(),
    new Path().move(x, m).line(x, y + h - r).arc(x + r, y + h - r, r, PI, PI / 2).line(x + w - r, y + h).arc(x + w - r, y + h - r, r, PI / 2, 0).line(x + w, m).done(),
  ];
}
// A box that draws its outline in at tin (then fills), and draws out at tout.
// o: stroke, fill, width, r (radius), d (draw time). Returns its visibility 0..1.
export function box(ctx, x, y, w, h, t, tin, tout = Infinity, o = {}) {
  const r = Math.min(o.r ?? 14, h / 2, w / 2), width = o.width ?? 3.5, stroke = o.stroke ?? C.faint, fill = o.fill === undefined ? C.fill : o.fill;
  const f = P(t, tin, o.d ?? 0.55, expoOut) * (1 - P(t, tout, 0.35));
  if (f <= 0) return 0;
  if (fill && f > 0.6) { ctx.save(); ctx.globalAlpha *= (f - 0.6) / 0.4; ctx.fillStyle = fill; ctx.beginPath(); ctx.roundRect(x, y, w, h, r); ctx.fill(); ctx.restore(); }
  if (!stroke) return f;
  if (f >= 0.999) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); ctx.lineWidth = width; ctx.strokeStyle = stroke; ctx.stroke(); return f; }
  for (const hv of halves(x, y, w, h, r)) trim(ctx, hv, 0, hv.len * f, width, stroke, 'butt');
  return f;
}
// A plain rounded rectangle (no animation).
export function rrect(ctx, x, y, w, h, r, fill, stroke = null, width = 3, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.beginPath(); ctx.roundRect(x, y, w, h, r);
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.lineWidth = width; ctx.strokeStyle = stroke; ctx.stroke(); }
  ctx.restore();
}
// A highlight ring that draws around a rect, then draws out.
export function ring(ctx, x, y, w, h, t, tin, tout, color = C.accent, pad = 8, width = 4) {
  box(ctx, x - pad, y - pad, w + 2 * pad, h + 2 * pad, t, tin, tout, { stroke: color, fill: null, width, r: 10, d: 0.45 });
}
// An expanding, fading circle (a click, a landing).
export function ripple(ctx, x, y, t, t0, r0 = 10, r1 = 60, color = C.fg) {
  const p = P(t, t0, 0.55, quartOut);
  if (t < t0 || p >= 1) return;
  ctx.save(); ctx.globalAlpha *= 1 - p; ctx.strokeStyle = color; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(x, y, lerp(r0, r1, p), 0, 2 * PI); ctx.stroke(); ctx.restore();
}
// A tick mark in a circle that pops in at t0.
export function tick(ctx, cx, cy, r, t, t0, tout = Infinity, color = C.green) {
  const s = pop(t, t0) * (1 - P(t, tout, 0.3));
  if (s <= 0) return;
  ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s);
  ctx.fillStyle = color; ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * PI); ctx.fill();
  const p = new Path().move(-r * 0.42, 0).line(-r * 0.1, r * 0.32).line(r * 0.45, -r * 0.3).done();
  trim(ctx, p, 0, p.len * P(t, t0 + 0.1, 0.3, expoOut), r * 0.2, C.bg, 'round');
  ctx.restore();
}
// A chip: a small labelled pill.
export function chip(ctx, str, x, y, t, tin, tout = Infinity, o = {}) {
  const size = o.size ?? 26, w = measure(ctx, str, size, o.weight ?? 500, o.font ?? MONO) + size * 1.2, h = size * 1.7;
  const a = vis(t, tin, tout);
  if (a <= 0) return w;
  const s = pop(t, tin);
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x + w / 2, y + h / 2); ctx.scale(s, s); ctx.translate(-w / 2, -h / 2);
  rrect(ctx, 0, 0, w, h, h / 2, o.fill ?? C.ghost, o.stroke ?? null, 2);
  label(ctx, str, w / 2, h / 2 + 1, size, o.color ?? C.fg, { align: 'center', base: 'middle', font: o.font ?? MONO, weight: o.weight ?? 500 });
  ctx.restore();
  return w;
}

export function withAlpha(ctx, a, fn) { if (a <= 0.001) return; ctx.save(); ctx.globalAlpha *= a; fn(); ctx.restore(); }
// seeded random numbers, so every render of a frame is the same
export function rng(seed) { seed = seed % 2147483647 || 1; return () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }; }
