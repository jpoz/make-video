// Draws every frame on a canvas and encodes with ffmpeg. Reads timeline.json and scenes/*.mjs.
//
// Sampling (use these all the time while you build; each run also writes out/sheet.jpg):
//   node render.mjs --stills 3,20.5            stills at those seconds          -> out/stills/
//   node render.mjs --scene intro,code 0.3,0.9  stills at fractions of scenes   -> out/stills/
//   node render.mjs --samples 24               24 stills spread over the film   -> out/stills/
//   node render.mjs --board                    one still per scene (storyboard) -> out/board/
//   node render.mjs --clip 12.5 16             a short MP4 with the mixed audio -> out/clip.mp4
// Full film:
//   node render.mjs [--blur 4] [--fresh]       out/video.mp4 (parallel workers; --blur = motion-blur subframes)
// The film is encoded in chunks that start at scene boundaries. Each chunk is kept in out/cache/
// with a checksum of every frame. The next render draws each chunk again (drawing is cheap) and
// uses the kept MP4 when every frame is the same, so only the scenes that changed are encoded.
// --fresh encodes every chunk again.
// The pictures come from frame.mjs; this file only samples and encodes them.
import { createCanvas } from '@napi-rs/canvas';
import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';
import { outputSettings } from './config.mjs';
import { W, H, clamp, lerp } from './lib.mjs';
import { TL, DUR, SCENES, render, prepare } from './frame.mjs';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--check') { console.log('scene functions are valid'); process.exit(0); }
if (TL.missing) throw new Error('missing timeline.json; run ./make.sh voice');
const OUTPUT = outputSettings(args), FPS = OUTPUT.fps;
function ffmpeg(options) {
  const result = spawnSync('ffmpeg', options, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`ffmpeg failed (status ${result.status}, signal ${result.signal ?? 'none'})`);
}


// ---------- drivers ----------
const cv = createCanvas(OUTPUT.width, OUTPUT.height), ctx = cv.getContext('2d');
ctx.scale(OUTPUT.scale, OUTPUT.scale);
const SUB = OUTPUT.blur, SHUTTER = 0.5;

// x264 "veryfast" at CRF 16 is as small as "medium" at CRF 18 on flat motion graphics, with no
// visible loss (PSNR 54 dB against 56 dB), and needs much less CPU. Changing these settings
// changes SETTINGS below, so cached chunks are encoded again.
const ENCODER = OUTPUT.quality === 'preview'
  ? ['-c:v', 'libx264', '-threads', '2', '-crf', '23', '-preset', 'veryfast']
  : ['-c:v', 'libx264', '-threads', '2', '-crf', '16', '-preset', 'veryfast'];
// a fast checksum of a frame's pixels (zlib.crc32 is in Node 20.15+ and 22.2+)
const crc = zlib.crc32 ? px => zlib.crc32(px) : px => createHash('sha1').update(px).digest('hex');

// The RGBA bytes of frame f, with motion blur when --blur is above 1.
const pixels = OUTPUT.width * OUTPUT.height * 4;
const acc = SUB > 1 ? new Uint32Array(pixels) : null, blurred = SUB > 1 ? Buffer.alloc(pixels) : null;
async function frameAt(f) {
  // canvas images live in native memory the JS heap can't see; collect often so they're freed
  if (globalThis.gc && f % 30 === 0) globalThis.gc();
  if (SUB <= 1) {
    await prepare(f / FPS); render(ctx, f / FPS);
    return cv.data(); // not getImageData: in @napi-rs/canvas getImageData leaks native memory every frame
  }
  acc.fill(0);
  for (let k = 0; k < SUB; k++) {
    const t = (f + (k / SUB - 0.5) * SHUTTER) / FPS;
    await prepare(t); render(ctx, t);
    const d = cv.data();
    for (let i = 0; i < d.length; i++) acc[i] += d[i];
  }
  for (let i = 0; i < blurred.length; i++) blurred[i] = (acc[i] + SUB / 2) / SUB;
  return blurred;
}

// Encode frames from..to-1 into file. When sums is an array, each frame's checksum is added to it.
async function encode(from, to, file, sums = null) {
  const ff = spawn('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${OUTPUT.width}x${OUTPUT.height}`, '-r', `${FPS}`, '-i', '-',
    ...ENCODER, '-pix_fmt', 'yuv420p', '-g', `${FPS * 2}`, file], { stdio: ['pipe', 'inherit', 'inherit'] });
  let failure;
  const closed = new Promise(resolve => {
    ff.once('error', error => { failure = error; ff.stdin.destroy(error); resolve(null); });
    ff.once('close', resolve);
  });
  ff.stdin.on('error', error => { failure = error; });
  try {
  for (let f = from; f < to; f++) {
    const frame = await frameAt(f);
    if (sums) sums.push(crc(frame));
    if (failure) throw failure;
    await new Promise((resolve, reject) => ff.stdin.write(frame, error => error ? reject(error) : resolve()));
  }
  ff.stdin.end();
  const code = await closed;
  if (failure) throw failure;
  if (code !== 0) throw new Error(`ffmpeg exited ${code}`);
  } finally {
    if (ff.exitCode === null) ff.kill();
  }
}

// One chunk of the film, kept as file (an MP4) and file.json (the checksum of each frame).
// Returns 'cached' when the kept MP4 has exactly these frames, else encodes it and returns 'encoded'.
async function chunk(from, to, file, fresh) {
  const meta = file.replace(/\.mp4$/, '.json');
  if (!fresh && existsSync(file) && existsSync(meta)) {
    let kept = null;
    try { kept = JSON.parse(readFileSync(meta, 'utf8')).sums; } catch { kept = null; }
    if (Array.isArray(kept) && kept.length === to - from) {
      let same = true;
      for (let f = from; f < to && same; f++) same = crc(await frameAt(f)) === kept[f - from];
      if (same) return 'cached';
    }
  }
  const sums = [];
  await encode(from, to, file + '.part.mp4', sums);
  // remove the old checksums first, so a stopped run can never pair them with a new MP4
  rmSync(meta, { force: true });
  renameSync(file + '.part.mp4', file);
  writeFileSync(meta + '.part', JSON.stringify({ from, to, sums }));
  renameSync(meta + '.part', meta);
  return 'encoded';
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
  const sh = Math.round(640 * H / W);
  ffmpeg(['-loglevel', 'error', '-y', '-pattern_type', 'glob', '-i', `${dir}/*.${files[0].split('.').pop()}`,
    '-vf', `scale=640:${sh},drawbox=0:0:640:${sh}:color=0x444a5a:t=1,tile=3x${rows}`, '-frames:v', '1', '-q:v', '3', file]);
  console.log(`wrote ${file.replace(ROOT, '')} (${files.length} frames)`);
}
const stamp = t => t.toFixed(2).padStart(7, '0');
const fresh = dir => { rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true }); return dir; };

// A worker renders its frames and exits. This check comes first and finds --worker anywhere in the
// arguments, so a worker can never reach the full-render branch below and spawn workers of its own.
const WORKER = args.indexOf('--worker');
if (WORKER >= 0 || process.env.MAKE_VIDEO_WORKER) {
  if (WORKER < 0) throw new Error('MAKE_VIDEO_WORKER is set but --worker is missing');
  const result = await chunk(Number(args[WORKER + 1]), Number(args[WORKER + 2]), args[WORKER + 3], args.includes('--fresh'));
  if (process.send) process.send(result);
} else if (args[0] === '--stills' || args[0] === '--scene' || args[0] === '--samples') {
  const dir = fresh(ROOT + 'out/stills');
  if (args[0] === '--stills') for (const s of args[1].split(',').map(Number)) {
    if (!Number.isFinite(s) || s < 0 || s >= DUR) throw new Error(`still time must be in 0..${DUR}`);
    await still(s, dir, stamp(s));
  }
  else if (args[0] === '--samples') {
    const n = Number(args[1] ?? 24);
    if (!Number.isInteger(n) || n < 1 || n > 300) throw new Error('samples must be an integer from 1 to 300');
    for (let i = 0; i < n; i++) { const s = (i + 0.5) * DUR / n; await still(s, dir, stamp(s)); }
  } else for (const id of args[1].split(',')) {
    const sc = SCENES.find(s => s.id === id);
    if (!sc) throw new Error(`no scene ${id}`);
    for (const f of (args[2] ?? '0.3,0.6,0.9').split(',').map(Number)) {
      if (!Number.isFinite(f) || f < 0 || f >= 1) throw new Error('scene fractions must be in 0..1 (excluding 1)');
      const s = lerp(sc.start, sc.end, f); await still(s, dir, `${stamp(s)}-${id}`);
    }
  }
  sheet(dir, ROOT + 'out/sheet.jpg');
} else if (args[0] === '--board') {
  // one frame per scene, at the moment most of it is on screen: just before it starts to leave
  const dir = fresh(ROOT + 'out/board');
  for (const s of SCENES) {
    const fullest = s.card ? lerp(s.start, s.end, 0.6) : Math.min(s.end - 0.75, s.voiceEnd + 0.3);
    const moment = clamp(Math.min(fullest, DUR - 1.3), s.start + Math.min(0.5, s.dur / 2), s.end - 0.001);
    await still(moment, dir, s.id, 0.5);
  }
  console.log(`wrote out/board/ (${SCENES.length} frames)`);
} else if (args[0] === '--clip') {
  // a short piece of the real film, with sound, to check motion and timing
  const a = Number(args[1]), b = Number(args[2] ?? a + 4), f0 = Math.round(a * FPS), f1 = Math.round(Math.min(DUR, b) * FPS);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b <= a || a >= DUR || f1 <= f0) throw new Error(`clip needs 0 <= A < B, with A below ${DUR}`);
  mkdirSync(ROOT + 'out', { recursive: true });
  await encode(f0, f1, ROOT + 'out/clip-silent.mp4');
  const mix = ROOT + 'out/audio-mix.mp3';
  const audio = existsSync(mix) ? ['-ss', `${a}`, '-t', `${b - a}`, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:a', 'aac'] : [];
  ffmpeg(['-loglevel', 'error', '-y', '-i', ROOT + 'out/clip-silent.mp4', ...audio, '-c:v', 'copy', '-shortest', ROOT + 'out/clip.mp4']);
  rmSync(ROOT + 'out/clip-silent.mp4');
  console.log(`wrote out/clip.mp4 (${a}s to ${b}s)`);
} else {
  const FRESH = args.includes('--fresh');
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === '--fresh') continue;
    if (!['--quality', '--workers', '--blur', '--fps'].includes(args[i])) throw new Error(`unknown render option: ${args[i]}`);
    i += 1;
  }
  // Chunks start at scene boundaries, so an edit to one scene changes only its own chunks.
  // A scene longer than 10 s is cut into equal parts, so the workers share the work.
  const total = Math.max(1, Math.round(DUR * FPS)), CHUNK = 10 * FPS, n = OUTPUT.workers;
  const cuts = new Set([0, total]);
  for (const s of SCENES) {
    const a = Math.min(total, Math.round(s.start * FPS)), b = Math.min(total, Math.round(s.end * FPS));
    cuts.add(a);
    const parts = Math.ceil((b - a) / CHUNK);
    for (let i = 1; i < parts; i++) cuts.add(a + Math.round(i * (b - a) / parts));
  }
  const bounds = [...cuts].sort((x, y) => x - y);
  // the encoder settings name the chunk files, so preview and final chunks are kept apart
  const SETTINGS = createHash('sha1').update(JSON.stringify({ v: 1, w: OUTPUT.width, h: OUTPUT.height, fps: FPS, blur: SUB, ENCODER })).digest('hex').slice(0, 10);
  const cache = ROOT + 'out/cache/';
  mkdirSync(cache, { recursive: true });
  const jobs = [];
  for (let i = 0; i + 1 < bounds.length; i++) {
    const [a, b] = [bounds[i], bounds[i + 1]];
    if (b > a) jobs.push({ a, b, name: `${SETTINGS}-${a}-${b}.mp4` });
  }
  const t0 = Date.now(), queue = [...jobs].sort((x, y) => (y.b - y.a) - (x.b - x.a)); // longest first
  let done = 0, cached = 0, failed = false;
  const pass = ['--expose-gc', fileURLToPath(import.meta.url), '--blur', SUB, '--fps', FPS, '--quality', OUTPUT.quality, ...(FRESH ? ['--fresh'] : [])];
  const children = new Set();
  async function worker() {
    while (!failed && queue.length) {
      const { a, b, name } = queue.shift();
      let result = 'encoded';
      await new Promise((res, rej) => {
        // the child takes the worker branch (it finds --worker anywhere); MAKE_VIDEO_WORKER also marks it as a worker
        const p = spawn(process.execPath, [...pass.slice(0, 2), '--worker', a, b, cache + name, ...pass.slice(2)],
          { stdio: ['inherit', 'inherit', 'inherit', 'ipc'], env: { ...process.env, MAKE_VIDEO_WORKER: '1' } });
        children.add(p);
        p.on('message', m => { result = m; });
        p.once('error', rej);
        p.once('close', c => { children.delete(p); c === 0 ? res() : rej(new Error(`frames ${a}-${b} exited ${c}`)); });
      });
      if (result === 'cached') cached++;
      console.log(`chunk ${++done}/${jobs.length}${result === 'cached' ? ' (unchanged)' : ''}, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
  }
  try { await Promise.all(Array.from({ length: Math.min(n, jobs.length) }, worker)); }
  catch (error) { failed = true; for (const p of children) p.kill(); throw error; }
  writeFileSync(cache + 'list.txt', jobs.map(j => `file '${j.name}'`).join('\n'));
  ffmpeg(['-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', cache + 'list.txt', '-c', 'copy', ROOT + 'out/video.mp4']);
  // keep the chunks of the latest preview and final renders; remove everything else
  writeFileSync(cache + `last-${OUTPUT.quality}.json`, JSON.stringify({ settings: SETTINGS, chunks: jobs.map(j => j.name) }));
  const keep = new Set(['list.txt']);
  for (const q of ['preview', 'final']) {
    const f = cache + `last-${q}.json`;
    if (!existsSync(f)) continue;
    keep.add(`last-${q}.json`);
    try { for (const c of JSON.parse(readFileSync(f, 'utf8')).chunks) { keep.add(c); keep.add(c.replace(/\.mp4$/, '.json')); } } catch {}
  }
  for (const f of readdirSync(cache)) if (!keep.has(f)) rmSync(cache + f, { force: true });
  rmSync(ROOT + 'out/seg', { recursive: true, force: true }); // chunks from before the cache
  writeFileSync(ROOT + 'out/render.json', JSON.stringify({ ...OUTPUT, duration: total / FPS, chunks: jobs.length, unchanged: cached }, null, 2));
  const kept = cached ? `, ${cached}/${jobs.length} chunks unchanged` : '';
  console.log(`wrote out/video.mp4: ${total} frames at ${FPS} fps, ${n} workers${kept}, ${((Date.now() - t0) / 60000).toFixed(1)} min`);
}
