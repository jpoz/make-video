// Draws every frame on a canvas and encodes with ffmpeg. Reads timeline.json and scenes/*.mjs.
//
// Sampling (use these all the time while you build; each run also writes out/sheet.jpg):
//   node render.mjs --stills 3,20.5            stills at those seconds          -> out/stills/
//   node render.mjs --scene intro,code 0.3,0.9  stills at fractions of scenes   -> out/stills/
//   node render.mjs --samples 24               24 stills spread over the film   -> out/stills/
//   node render.mjs --board                    one still per scene (storyboard) -> out/board/
//   node render.mjs --clip 12.5 16             a short MP4 with the mixed audio -> out/clip.mp4
// Full film:
//   node render.mjs [--blur 4]                 out/video.mp4 (parallel workers; --blur = motion-blur subframes)
import { createCanvas } from '@napi-rs/canvas';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { cpus } from 'node:os';
import { fileURLToPath } from 'node:url';
import { background } from './theme.mjs';
import { W, H, C, SANS, MONO, P, clamp, lerp, expoOut, font, text, rrect } from './lib.mjs';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
export const TL = JSON.parse(readFileSync(ROOT + 'timeline.json', 'utf8'));
const args = process.argv.slice(2);
const flag = (name, dflt) => { const i = args.indexOf(name); return i < 0 ? dflt : args[i + 1]; };
const FPS = Number(flag('--fps', TL.fps ?? 60));
const DUR = TL.duration;

// ---------- the scene context (S) every draw function gets ----------
export function ctxFor(sc) {
  const S = { ...sc, tin: sc.start + 0.15, tout: sc.end - 0.55, dur: sc.end - sc.start };
  // estimated start time of the nth match of a word (or phrase) in this scene's voice
  S.w = (word, nth = 0) => {
    for (const ln of sc.lines) {
      let i = -1;
      while ((i = ln.text.indexOf(word, i + 1)) >= 0) { if (nth-- === 0) return ln.start + ln.dur * i / ln.text.length; }
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
const SCENES = TL.scenes.map(ctxFor);

// ---------- scene modules: scenes/*.mjs export default { sceneId(ctx, t, S) {...} } and maybe prepare(t) ----------
const DRAW = {}, PREP = [];
for (const f of readdirSync(ROOT + 'scenes').filter(f => f.endsWith('.mjs')).sort()) {
  const mod = await import(ROOT + 'scenes/' + f);
  Object.assign(DRAW, mod.default);
  if (mod.prepare) PREP.push(mod.prepare);
}
for (const s of SCENES) if (!s.card && !DRAW[s.id]) console.warn(`no draw function for scene "${s.id}"`);
// load anything a frame needs asynchronously (recorded frames, big images) before drawing it
const prepare = async t => { for (const f of PREP) await f(t); };

// ---------- chapter HUD: shown when scenes have a "chapter" name ----------
const CHAPTERS = [...new Set(TL.scenes.map(s => s.chapter).filter(Boolean))];
const HUD_ON = SCENES.find(s => s.chapter)?.start ?? 0;
function hud(ctx, t, sc) {
  const on = CHAPTERS.indexOf(sc.chapter);
  const a = P(t, HUD_ON, 0.6);
  if (on < 0 || sc.card || a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  font(ctx, 21, 500, MONO);
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
const CAPTION_Y = 1029;
function captions(ctx, t) {
  const c = TL.captions.find(c => t >= c.a && t < c.b);
  if (!c) return;
  const a = clamp((t - c.a) / 0.12) * clamp((c.b - t) / 0.12);
  font(ctx, 34, 400, SANS);
  const w = ctx.measureText(c.text).width;
  ctx.save(); ctx.globalAlpha *= a;
  rrect(ctx, W / 2 - w / 2 - 22, CAPTION_Y - 39, w + 44, 56, 10, 'rgba(4,4,16,0.72)');
  ctx.fillStyle = C.fg; ctx.textAlign = 'center'; ctx.fillText(c.text, W / 2, CAPTION_Y);
  ctx.restore();
}

// ---------- chapter cards: scenes with "card": {kicker, title} and no draw function of their own ----------
function card(ctx, t, S) {
  const out = S.end - 0.5, t0 = S.start + 0.3;
  if (S.card.kicker) text(ctx, S.card.kicker.toUpperCase(), W / 2, 430, 30, t, S.start + 0.15, out, { align: 'center', font: MONO, weight: 500, color: C.accent });
  text(ctx, S.card.title, W / 2, 580, 110, t, t0, out, { align: 'center', weight: 700, stagger: 0.03 });
  const u = P(t, t0 + 0.6, 0.6, expoOut) * (1 - P(t, out, 0.45));
  if (u > 0) { ctx.fillStyle = C.accent; const w = 420 * u; ctx.fillRect(W / 2 - w / 2, 640, w, 6); }
}

// ---------- one frame ----------
function sceneAt(t) {
  for (const s of SCENES) if (t >= s.start && t < s.end) return s;
  return SCENES.at(-1);
}
export function render(ctx, t) {
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

// ---------- drivers ----------
const cv = createCanvas(W, H), ctx = cv.getContext('2d');
const SUB = Number(flag('--blur', 1)), SHUTTER = 0.5;

async function encode(from, to, file) {
  const ff = spawn('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${W}x${H}`, '-r', `${FPS}`, '-i', '-',
    '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-g', `${FPS * 2}`, file], { stdio: ['pipe', 'inherit', 'inherit'] });
  const acc = SUB > 1 ? new Uint32Array(W * H * 4) : null, out = SUB > 1 ? Buffer.alloc(W * H * 4) : null;
  for (let f = from; f < to; f++) {
    // canvas images live in native memory the JS heap can't see; collect often so they're freed
    if (globalThis.gc && f % 30 === 0) globalThis.gc();
    let frame;
    if (SUB > 1) {
      acc.fill(0);
      for (let k = 0; k < SUB; k++) {
        const t = (f + (k / SUB - 0.5) * SHUTTER) / FPS;
        await prepare(t); render(ctx, t);
        const d = cv.data();
        for (let i = 0; i < d.length; i++) acc[i] += d[i];
      }
      for (let i = 0; i < out.length; i++) out[i] = (acc[i] + SUB / 2) / SUB;
      frame = out;
    } else {
      await prepare(f / FPS); render(ctx, f / FPS);
      frame = cv.data(); // not getImageData: in @napi-rs/canvas getImageData leaks native memory every frame
    }
    if (!ff.stdin.write(frame)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  const code = await new Promise(r => ff.on('close', r));
  if (code !== 0) throw new Error(`ffmpeg exited ${code}`);
}
async function still(t, dir, name, scale = 1) {
  await prepare(t); render(ctx, t);
  if (scale === 1) return writeFileSync(`${dir}/${name}.png`, cv.toBuffer('image/png'));
  const sm = createCanvas(W * scale, H * scale), s = sm.getContext('2d');
  s.drawImage(cv, 0, 0, W * scale, H * scale);
  writeFileSync(`${dir}/${name}.jpg`, sm.toBuffer('image/jpeg', 86));
}
// a contact sheet of every image in dir, 3 across, each labelled with its file name (= its time)
function sheet(dir, file) {
  const files = readdirSync(dir).filter(f => /\.(png|jpg)$/.test(f)).sort();
  if (!files.length) return;
  const rows = Math.ceil(files.length / 3);
  spawnSync('ffmpeg', ['-loglevel', 'error', '-y', '-pattern_type', 'glob', '-i', `${dir}/*.${files[0].split('.').pop()}`,
    '-vf', `scale=640:360,drawbox=0:0:640:360:color=0x444a5a:t=1,tile=3x${rows}`, '-frames:v', '1', '-q:v', '3', file], { stdio: 'inherit' });
  console.log(`wrote ${file.replace(ROOT, '')} (${files.length} frames)`);
}
const stamp = t => t.toFixed(2).padStart(7, '0');
const fresh = dir => { rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true }); return dir; };

// A worker renders its frames and exits. This check comes first and finds --worker anywhere in the
// arguments, so a worker can never reach the full-render branch below and spawn workers of its own.
const WORKER = args.indexOf('--worker');
if (WORKER >= 0 || process.env.MAKE_VIDEO_WORKER) {
  if (WORKER < 0) throw new Error('MAKE_VIDEO_WORKER is set but --worker is missing');
  await encode(Number(args[WORKER + 1]), Number(args[WORKER + 2]), args[WORKER + 3]);
} else if (args[0] === '--stills' || args[0] === '--scene' || args[0] === '--samples') {
  const dir = fresh(ROOT + 'out/stills');
  if (args[0] === '--stills') for (const s of args[1].split(',').map(Number)) await still(s, dir, stamp(s));
  else if (args[0] === '--samples') {
    const n = Number(args[1] ?? 24);
    for (let i = 0; i < n; i++) { const s = (i + 0.5) * DUR / n; await still(s, dir, stamp(s)); }
  } else for (const id of args[1].split(',')) {
    const sc = SCENES.find(s => s.id === id);
    if (!sc) throw new Error(`no scene ${id}`);
    for (const f of (args[2] ?? '0.3,0.6,0.9').split(',').map(Number)) { const s = lerp(sc.start, sc.end, f); await still(s, dir, `${stamp(s)}-${id}`); }
  }
  sheet(dir, ROOT + 'out/sheet.jpg');
} else if (args[0] === '--board') {
  // one frame per scene, at the moment most of it is on screen: just before it starts to leave
  const dir = fresh(ROOT + 'out/board');
  for (const s of SCENES) await still(s.card ? lerp(s.start, s.end, 0.6) : Math.max(s.start + 0.5, Math.min(s.end - 0.75, s.voiceEnd + 0.3)), dir, s.id, 0.5);
  console.log(`wrote out/board/ (${SCENES.length} frames)`);
} else if (args[0] === '--clip') {
  // a short piece of the real film, with sound, to check motion and timing
  const a = Number(args[1]), b = Number(args[2] ?? a + 4), f0 = Math.round(a * FPS), f1 = Math.round(Math.min(DUR, b) * FPS);
  mkdirSync(ROOT + 'out', { recursive: true });
  await encode(f0, f1, ROOT + 'out/clip-silent.mp4');
  const mix = ROOT + 'out/audio-mix.mp3';
  const audio = existsSync(mix) ? ['-ss', `${a}`, '-t', `${b - a}`, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:a', 'aac'] : [];
  spawnSync('ffmpeg', ['-loglevel', 'error', '-y', '-i', ROOT + 'out/clip-silent.mp4', ...audio, '-c:v', 'copy', '-shortest', ROOT + 'out/clip.mp4'], { stdio: 'inherit' });
  rmSync(ROOT + 'out/clip-silent.mp4');
  console.log(`wrote out/clip.mp4 (${a}s to ${b}s)`);
} else {
  // The film in ~10 s chunks, several workers at once. Each chunk is a fresh process, so memory is freed.
  const total = Math.round(DUR * FPS), CHUNK = 10 * FPS, n = Math.max(1, Math.min(6, cpus().length - 2));
  const dir = fresh(ROOT + 'out/seg'), t0 = Date.now(), jobs = [];
  for (let a = 0, i = 0; a < total; a += CHUNK, i++) jobs.push([a, Math.min(total, a + CHUNK), `${dir}/${String(i).padStart(3, '0')}.mp4`]);
  let next = 0, done = 0;
  const pass = ['--expose-gc', fileURLToPath(import.meta.url), ...(SUB > 1 ? ['--blur', SUB] : []), '--fps', FPS];
  async function worker() {
    while (next < jobs.length) {
      const [a, b, file] = jobs[next++];
      await new Promise((res, rej) => {
        // the child takes the worker branch (it finds --worker anywhere); MAKE_VIDEO_WORKER also marks it as a worker
        const p = spawn(process.execPath, [...pass.slice(0, 2), '--worker', a, b, file + '.part.mp4', ...pass.slice(2)],
          { stdio: 'inherit', env: { ...process.env, MAKE_VIDEO_WORKER: '1' } });
        p.on('close', c => (c === 0 ? res() : rej(new Error(`frames ${a}-${b} exited ${c}`))));
      });
      renameSync(file + '.part.mp4', file);
      console.log(`chunk ${++done}/${jobs.length}, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
  }
  await Promise.all(Array.from({ length: n }, worker));
  writeFileSync(dir + '/list.txt', jobs.map(j => `file '${j[2]}'`).join('\n'));
  spawnSync('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', dir + '/list.txt', '-c', 'copy', ROOT + 'out/video.mp4'], { stdio: 'inherit' });
  console.log(`wrote out/video.mp4: ${total} frames at ${FPS} fps, ${n} workers, ${((Date.now() - t0) / 60000).toFixed(1)} min`);
}
