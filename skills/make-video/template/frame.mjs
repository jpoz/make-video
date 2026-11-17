// The picture: draws any moment of the film from timeline.json and scenes/*.mjs.
// render(ctx, t) is a pure function of t, so render.mjs (files) and studio.mjs (live preview)
// draw exactly the same frames.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { SPEC } from './config.mjs';
import { background } from './theme.mjs';
import { W, H, C, MONO, P, clamp, expoOut, font, text, rrect, wrap, measure } from './lib.mjs';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
// timeline.json is missing only before the first ./make.sh voice; render.mjs --check works without it
export const TL = existsSync(ROOT + 'timeline.json')
  ? JSON.parse(readFileSync(ROOT + 'timeline.json', 'utf8'))
  : { scenes: [], captions: [], duration: 0, missing: true };
export const DUR = TL.duration;

// ---------- word times: the same rule as char_time in timeline.py ----------
export function charTime(line, i) {
  if (!line.marks) return line.start + line.dur * i / Math.max(1, line.text.length);
  let k = 0;
  for (const m of line.text.matchAll(/\S+/g)) {
    const s = m.index, e = s + m[0].length, [a, b] = line.marks[k++] ?? [line.start, line.start];
    if (i < e) return a + (b - a) * Math.max(0, i - s) / Math.max(1, e - s);
  }
  return line.start + line.dur;
}

// ---------- the scene context (S) every draw function gets ----------
export function ctxFor(sc) {
  const S = { ...sc, tin: sc.start + 0.15, tout: sc.end - 0.55, dur: sc.end - sc.start };
  // start time of the nth match of a word (or phrase) in this scene's voice: measured by align.py
  // when out/words.json has the line, otherwise estimated from the text (see timeline.py)
  S.w = (word, nth = 0) => {
    for (const ln of sc.lines) {
      let i = -1;
      while ((i = ln.text.indexOf(word, i + 1)) >= 0) { if (nth-- === 0) return charTime(ln, i); }
    }
    throw new Error(`no word "${word}" in scene ${sc.id}`);
  };
  // time of a cue from video.json (beat-snapped when music.snap is on)
  S.cue = label => { const v = sc.cues?.[label]; if (v == null) throw new Error(`no cue "${label}" in scene ${sc.id}`); return v; };
  S.line = i => sc.lines[i].start;
  S.lineEnd = i => sc.lines[i].start + sc.lines[i].dur;
  S.voiceEnd = sc.lines.length ? S.lineEnd(sc.lines.length - 1) : sc.end;
  S.p = t => clamp((t - sc.start) / (sc.end - sc.start));
  return S;
}
export const SCENES = TL.scenes.map(ctxFor);

// ---------- scene modules: scenes/*.mjs export default { sceneId(ctx, t, S) {...} } and maybe prepare(t) ----------
const DRAW = Object.create(null), PREP = [];
for (const f of readdirSync(ROOT + 'scenes').filter(f => f.endsWith('.mjs')).sort()) {
  const mod = await import(ROOT + 'scenes/' + f);
  for (const [id, draw] of Object.entries(mod.default ?? {})) {
    if (Object.hasOwn(DRAW, id)) throw new Error(`duplicate draw function: ${id}`);
    if (typeof draw !== 'function') throw new Error(`scene ${id}: draw must be a function`);
    DRAW[id] = draw;
  }
  if (mod.prepare) PREP.push(mod.prepare);
}
for (const s of SPEC.scenes) if (!s.card && !DRAW[s.id]) throw new Error(`no draw function for scene "${s.id}"`);
// load anything a frame needs asynchronously (recorded frames, big images) before drawing it
export const prepare = async t => { for (const f of PREP) await f(t); };

// ---------- chapter HUD: shown when scenes have a "chapter" name ----------
const CHAPTERS = [...new Set(TL.scenes.map(s => s.chapter).filter(Boolean))];
const HUD_ON = SCENES.find(s => s.chapter)?.start ?? 0;
function hud(ctx, t, sc) {
  const on = CHAPTERS.indexOf(sc.chapter);
  const a = P(t, HUD_ON, 0.6);
  if (on < 0 || sc.card || a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  const full = CHAPTERS.join('  ›  ');
  const size = Math.min(21, 21 * (W - 160) / Math.max(1, measure(ctx, full, 21, 500, MONO)));
  if (size < 16) {
    font(ctx, 24, 500, MONO); ctx.fillStyle = C.accent; ctx.textAlign = 'center';
    ctx.fillText(`${on + 1} / ${CHAPTERS.length}  ${sc.chapter}`, W / 2, 62, W - 160);
    ctx.restore(); return;
  }
  font(ctx, size, 500, MONO);
  const widths = CHAPTERS.map(s => ctx.measureText(s).width), sep = 46;
  let x = W / 2 - (widths.reduce((p, q) => p + q, 0) + sep * (CHAPTERS.length - 1)) / 2;
  CHAPTERS.forEach((s, i) => {
    ctx.fillStyle = i === on ? C.accent : i < on ? C.mute : C.faint;
    ctx.fillText(s, x, 62);
    if (i === on) ctx.fillRect(x, 74, widths[i], 3);
    if (i < CHAPTERS.length - 1) { ctx.fillStyle = C.faint; ctx.fillText('›', x + widths[i] + sep / 2 - 6, 62); }
    x += widths[i] + sep;
  });
  ctx.restore();
}

// ---------- captions (cut by timeline.py) ----------
const CAPTION_Y = H - 52;
function captions(ctx, t) {
  if (TL.burn_captions === false) return;
  const c = TL.captions.find(c => t >= c.a && t < c.b);
  if (!c) return;
  const a = clamp((t - c.a) / 0.12) * clamp((c.b - t) / 0.12);
  const rows = wrap(ctx, c.text, W - 180, 34);
  const w = Math.min(W - 160, Math.max(...rows.map(row => measure(ctx, row, 34))));
  const height = rows.length * 44 + 16;
  ctx.save(); ctx.globalAlpha *= a;
  rrect(ctx, W / 2 - w / 2 - 22, CAPTION_Y - height + 17, w + 44, height, 10, 'rgba(4,4,16,0.72)');
  ctx.fillStyle = C.fg; ctx.textAlign = 'center';
  rows.forEach((row, i) => ctx.fillText(row, W / 2, CAPTION_Y - (rows.length - 1 - i) * 44, W - 180));
  ctx.restore();
}

// ---------- chapter cards: scenes with "card": {kicker, title} and no draw function of their own ----------
function card(ctx, t, S) {
  const out = S.end - 0.5, t0 = S.start + 0.3;
  const rows = wrap(ctx, S.card.title, W - 200, 90, 700);
  const top = H / 2 - (rows.length - 1) * 54;
  if (S.card.kicker) text(ctx, S.card.kicker.toUpperCase(), W / 2, top - 110, 30, t, S.start + 0.15, out, { align: 'center', font: MONO, weight: 500, color: C.accent });
  rows.forEach((row, i) => text(ctx, row, W / 2, top + i * 108, 90, t, t0 + i * 0.08, out, { align: 'center', weight: 700, stagger: 0.03 }));
  const u = P(t, t0 + 0.6, 0.6, expoOut) * (1 - P(t, out, 0.45));
  if (u > 0) { ctx.fillStyle = C.accent; const w = Math.min(420, W - 200) * u; ctx.fillRect(W / 2 - w / 2, top + (rows.length - 1) * 108 + 60, w, 6); }
}

// ---------- one frame ----------
export function sceneAt(t) {
  for (const s of SCENES) if (t >= s.start && t < s.end) return s;
  return SCENES.at(-1);
}
export function render(ctx, t) {
  t = clamp(t, 0, Math.max(0, DUR - 0.000001));
  ctx.drawImage(background, 0, 0);
  const sc = sceneAt(t);
  ctx.save();
  if (DRAW[sc.id]) DRAW[sc.id](ctx, t, sc);
  else if (sc.card) card(ctx, t, sc);
  ctx.restore();
  hud(ctx, t, sc);
  captions(ctx, t);
  // fade from and to black at the very ends
  const k = Math.max(1 - P(t, 0, 0.6), P(t, DUR - 1.2, 1.1));
  if (k > 0) { ctx.fillStyle = `rgba(0,0,0,${k})`; ctx.fillRect(0, 0, W, H); }
}
