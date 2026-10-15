// Code panels. Every line on screen is read from the real file at render time, by line number,
// so the film cannot misquote the source. Paths are relative to video.json "source"
// (default: this project folder).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { C, MONO, P, lerp, quartOut, expoOut, cubicInOut, font, rrect, label } from './lib.mjs';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const SPEC = JSON.parse(readFileSync(ROOT + 'video.json', 'utf8'));
const SOURCE = resolve(ROOT, (SPEC.source ?? '.').replace(/^~(?=\/)/, process.env.HOME));
const FILES = {};
const src = f => (FILES[f] ??= readFileSync(resolve(SOURCE, f), 'utf8').split('\n'));

// snippet('src/player.rs', [48, 58], [61, 63]) -> lines with their real numbers; a gap between ranges shows as ⋯
// A range [a, b, 'nodoc'] leaves out doc comments (///, #, //) and blank lines; the line numbers show the jump.
export function snippet(file, ...ranges) {
  const L = src(file), out = [];
  ranges.forEach(([a, b, mode], k) => {
    if (k > 0) out.push({ n: null, text: '⋯' });
    for (let n = a; n <= b; n++) {
      if (L[n - 1] === undefined) throw new Error(`${file}:${n} does not exist`);
      if (mode === 'nodoc' && (/^\s*(\/\/\/|#|\/\/)/.test(L[n - 1]) || !L[n - 1].trim())) continue;
      out.push({ n, text: L[n - 1].replace(/\t/g, '    ') });
    }
  });
  const ind = Math.min(...out.filter(l => l.n && l.text.trim()).map(l => l.text.match(/^ */)[0].length));
  for (const l of out) if (l.n) l.text = l.text.slice(ind);
  out.forEach((l, i) => { if (!l.n) { const nx = out[i + 1]; l.text = (nx ? nx.text.match(/^ */)[0] : '') + '⋯'; } });
  return { file, lines: out, first: ranges[0][0], last: ranges.at(-1)[1] };
}
// The line number of the first line in a file that contains str (so scenes survive edits to the file).
export function lineOf(file, str, from = 1) {
  const i = src(file).findIndex((l, k) => k >= from - 1 && l.includes(str));
  if (i < 0) throw new Error(`"${str}" not found in ${file}`);
  return i + 1;
}

const KW = /^(pub|fn|let|mut|if|else|for|in|match|return|const|struct|impl|use|while|unsafe|extern|as|mod|static|async|await|new|class|get|set|import|export|from|def|true|false|True|False|None|Self|self|this|function|of|null|nil|loop|break|continue|type|interface|where|move|ref|crate|super|func|package|var|go|defer|chan|select|case|switch|default|try|catch|throw|with|yield|lambda|enum)$/;
const TOKEN = /(\/\/.*$|#(?!\[).*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`[^`]*`)|(#\[[^\]]*\]?)|(\b0x[0-9A-Fa-f_]+\b|\b\d[\d_]*(?:\.\d+)?\b)|(\b[A-Za-z_][A-Za-z0-9_]*\b)|(\s+)|(.)/g;
export const SYN = { kw: C.amber, str: '#9be29b', num: '#8fd8ff', type: C.violet, com: 'rgba(242,236,223,0.42)', attr: 'rgba(242,236,223,0.45)', fn: '#ffffff', txt: C.fg };
function tokens(line, lang) {
  const out = []; let m; TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(line))) {
    const [s, com, str, attr, num, id] = m;
    let k = 'txt';
    // '#' starts a comment only in languages that use it
    if (com && (com.startsWith('//') || ['py', 'sh', 'rb', 'yaml', 'toml'].includes(lang))) k = 'com';
    else if (com) { out.push([s[0], 'txt']); TOKEN.lastIndex = m.index + 1; continue; }
    else if (str) k = 'str'; else if (attr) k = 'attr'; else if (num) k = 'num';
    else if (id) k = KW.test(id) ? 'kw' : /^[A-Z]/.test(id) ? 'type' : line[m.index + id.length] === '(' ? 'fn' : 'txt';
    out.push([s, k]);
  }
  return out;
}

// Highlight track: keys [time, fromLine, toLine?] in real line numbers; [time, null] turns it off.
function hlAt(snip, keys, t) {
  if (!keys?.length || t < keys[0][0]) return null;
  const row = n => { const i = snip.lines.findIndex(l => l.n === n); if (i < 0) throw new Error(`line ${n} not in snippet ${snip.file}:${snip.first}`); return i; };
  let cur = null, prev = null;
  for (const k of keys) if (t >= k[0]) { prev = cur; cur = k; }
  if (cur[1] == null) return { off: true, t: cur[0] };
  const to = k => [row(k[1]), row(k[2] ?? k[1]) + 1];
  const [b0, b1] = to(cur);
  if (!prev || prev[1] == null) return { y0: b0, y1: b1, a: P(t, cur[0], 0.3) };
  const [a0, a1] = to(prev), p = P(t, cur[0], 0.38, cubicInOut);
  return { y0: lerp(a0, b0, p), y1: lerp(a1, b1, p), a: 1 };
}

// Draw a code panel at x, y. o: fs (font size), tin, tout, hl (highlight keys), w (fixed width: font shrinks to fit),
// title (default "file · lines"), dim (false: don't dim the other lines). Returns geometry for callouts.
export function drawCode(ctx, snip, x, y, t, o = {}) {
  let fs = o.fs ?? 26;
  if (o.w) { const need = codeSize(ctx, snip, fs).w; if (need > o.w) fs = Math.floor(fs * (o.w - 56) / (need - 56) * 10) / 10; }
  const lh = Math.round(fs * 1.55), pad = 28, head = 52, lang = snip.file.split('.').pop();
  const tin = o.tin ?? 0, tout = o.tout ?? Infinity;
  const a = P(t, tin, 0.45, quartOut) * (1 - P(t, tout, 0.35));
  if (a <= 0) return null;
  font(ctx, fs, 400, MONO);
  const cw = ctx.measureText('M').width, gutter = cw * 4.2;
  const w = o.w ?? Math.max(560, pad * 2 + gutter + cw * Math.max(...snip.lines.map(l => l.text.length)) + 10);
  const h = head + pad * 0.6 + lh * snip.lines.length + pad * 0.7;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.translate(0, (1 - P(t, tin, 0.6, expoOut)) * 40);
  rrect(ctx, x, y, w, h, 16, C.panel, 'rgba(242,236,223,0.14)', 2);
  const title = o.title ?? `${snip.file}  ·  ${snip.first === snip.last ? snip.first : snip.first + '–' + snip.last}`;
  label(ctx, title, x + pad, y + 34, 19, C.mute, { font: MONO });
  ctx.fillStyle = 'rgba(242,236,223,0.1)'; ctx.fillRect(x, y + head, w, 1.5);
  const top = y + head + pad * 0.6;
  const hl = hlAt(snip, o.hl, t);
  const lit = hl && !hl.off ? hl : null;
  if (lit) {
    ctx.save(); ctx.globalAlpha *= lit.a;
    ctx.fillStyle = C.accentFill; ctx.fillRect(x + 2, top + lit.y0 * lh, w - 4, (lit.y1 - lit.y0) * lh);
    ctx.fillStyle = C.accent; ctx.fillRect(x + 2, top + lit.y0 * lh, 5, (lit.y1 - lit.y0) * lh);
    ctx.restore();
  }
  snip.lines.forEach((l, i) => {
    const li = P(t, tin + 0.15 + i * 0.035, 0.4, quartOut);
    if (li <= 0) return;
    const by = top + i * lh + lh * 0.72;
    let la = li;
    if (lit && o.dim !== false) la *= i + 0.5 > lit.y0 && i + 0.5 < lit.y1 ? 1 : lerp(1, 0.42, lit.a);
    ctx.save(); ctx.globalAlpha *= la; ctx.translate((1 - li) * 24, 0);
    font(ctx, fs * 0.82, 400, MONO);
    ctx.fillStyle = 'rgba(242,236,223,0.32)'; ctx.textAlign = 'right';
    if (l.n) ctx.fillText(String(l.n), x + pad + gutter - cw * 1.2, by);
    ctx.textAlign = 'left';
    let cx = x + pad + gutter;
    if (!l.n) { font(ctx, fs, 400, MONO); ctx.fillStyle = C.mute; ctx.fillText(l.text, cx, by); }
    else for (const [s, k] of tokens(l.text, lang)) {
      font(ctx, fs, k === 'kw' || k === 'fn' ? 500 : 400, MONO);
      ctx.fillStyle = SYN[k]; ctx.fillText(s, cx, by); cx += ctx.measureText(s).width;
    }
    ctx.restore();
  });
  ctx.restore();
  const rowRect = n => { const i = snip.lines.findIndex(l => l.n === n); return { x, y: top + i * lh, w, h: lh }; };
  return { x, y, w, h, lh, top, cw, gutter, pad, rowRect, colX: col => x + pad + gutter + cw * col };
}
// Measure a panel without drawing it (for layout).
export function codeSize(ctx, snip, fs = 26) {
  font(ctx, fs, 400, MONO);
  const cw = ctx.measureText('M').width, lh = Math.round(fs * 1.55);
  return { w: Math.max(560, 56 + cw * 4.2 + cw * Math.max(...snip.lines.map(l => l.text.length)) + 10), fs, h: 52 + 28 * 0.6 + lh * snip.lines.length + 28 * 0.7 };
}
