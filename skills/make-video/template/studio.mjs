// Live preview: plays the film in a browser with its real audio mix, without encoding a video.
//
//   node studio.mjs [--port 4321]      (or ./make.sh studio)
//
// The server listens on 127.0.0.1 only. A renderer child process draws each frame with frame.mjs,
// the same code that render.mjs encodes, so the preview shows the real frames. When a scene file
// or another .mjs file changes, the renderer restarts and the page draws the new frames at the same time.
// When video.json changes, the server runs ./make.sh prepare (voice, word timing, timeline, audio)
// first. Errors show in the page and in this terminal.
import { createCanvas } from '@napi-rs/canvas';
import { fork, spawn } from 'node:child_process';
import { createReadStream, existsSync, readFileSync, statSync, watch } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const SELF = fileURLToPath(import.meta.url);
const args = process.argv.slice(2);

// ---------- the renderer child: draws frames on request ----------
if (args.includes('--renderer')) {
  try {
    const { TL, render, prepare } = await import('./frame.mjs');
    const { W, H } = await import('./config.mjs');
    if (TL.missing) throw new Error('missing timeline.json; run ./make.sh voice');
    const canvases = new Map();
    let queue = Promise.resolve();
    process.on('message', ({ id, t, width }) => {
      // one frame at a time: scenes may keep state in prepare() for the frame being drawn
      queue = queue.then(async () => {
        try {
          const w = Math.max(160, Math.min(W, Math.round(width || W)));
          let entry = canvases.get(w);
          if (!entry) {
            const cv = createCanvas(w, Math.round(w * H / W)), ctx = cv.getContext('2d');
            ctx.scale(w / W, w / W);
            canvases.set(w, entry = { cv, ctx });
          }
          await prepare(t);
          render(entry.ctx, t);
          process.send({ id, jpeg: await entry.cv.encode('jpeg', 82) });
        } catch (error) {
          process.send({ id, error: error.stack ?? String(error) });
        }
      });
    });
    process.send({ ready: true, width: W, height: H });
  } catch (error) {
    process.send({ fatal: error.stack ?? String(error) });
  }
} else {
  await server();
}

async function server() {
  const option = (key, fallback) => { const i = args.indexOf(key); return i < 0 ? fallback : args[i + 1]; };
  const firstPort = Number(option('--port', process.env.PORT ?? 4321));
  if (!Number.isInteger(firstPort) || firstPort < 1 || firstPort > 65535) throw new Error('--port must be from 1 to 65535');

  const state = { ready: false, error: null, building: false, version: 0, width: 1920, height: 1080, audio: 0 };
  const clients = new Set(), pending = new Map();
  let child = null, nextId = 0;

  const broadcast = () => {
    const data = `data: ${JSON.stringify(state)}\n\n`;
    for (const res of clients) res.write(data);
  };
  const audioStamp = () => existsSync(ROOT + 'out/audio-mix.mp3') ? statSync(ROOT + 'out/audio-mix.mp3').mtimeMs : 0;

  function startRenderer() {
    if (child) { child.removeAllListeners(); child.kill(); }
    for (const [, p] of pending) p.reject(new Error('renderer restarted'));
    pending.clear();
    state.ready = false;
    let stderr = '';
    const c = child = fork(SELF, ['--renderer'], { serialization: 'advanced', stdio: ['ignore', 'inherit', 'pipe', 'ipc'] });
    c.stderr.on('data', d => { stderr += d; process.stderr.write(d); });
    c.on('message', msg => {
      if (msg.ready) {
        Object.assign(state, { ready: true, error: null, width: msg.width, height: msg.height, version: state.version + 1, audio: audioStamp() });
        console.log(`renderer ready (version ${state.version})`);
        broadcast();
      } else if (msg.fatal) {
        state.error = msg.fatal;
        console.error(msg.fatal);
        broadcast();
      } else if (pending.has(msg.id)) {
        const p = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? p.reject(new Error(msg.error)) : p.resolve(msg.jpeg);
      }
    });
    c.on('exit', code => {
      if (c !== child) return;
      child = null;
      state.ready = false;
      state.error ??= `renderer exited (${code})\n${stderr.slice(-4000)}`;
      for (const [, p] of pending) p.reject(new Error(state.error));
      pending.clear();
      broadcast();
    });
  }

  function frame(t, width) {
    if (!child || !state.ready) return Promise.reject(new Error(state.error ?? 'renderer is starting'));
    const id = nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error('frame took longer than 20 s')); }, 20000);
      pending.set(id, { resolve: v => { clearTimeout(timer); resolve(v); }, reject: e => { clearTimeout(timer); reject(e); } });
      child.send({ id, t, width });
    });
  }

  // video.json changed: build voice, word timing, timeline, and audio again, then restart the renderer
  let buildAgain = false;
  function rebuild() {
    if (state.building) { buildAgain = true; return; }
    state.building = true; state.error = null; broadcast();
    console.log('video.json changed: ./make.sh prepare');
    let output = '';
    const p = spawn('sh', [ROOT + 'make.sh', 'prepare'], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
    p.stdout.on('data', d => { output += d; process.stdout.write(d); });
    p.stderr.on('data', d => { output += d; process.stderr.write(d); });
    p.on('close', code => {
      state.building = false;
      if (buildAgain) { buildAgain = false; return rebuild(); }
      if (code === 0) startRenderer();
      else { state.error = `./make.sh prepare failed (${code})\n${output.slice(-4000)}`; broadcast(); }
    });
  }

  // watch the project; ignore what the build itself writes
  let timer = null, reason = null;
  const IGNORE = /^(out|node_modules|shots[\\/]out|\.git)([\\/]|$)|(^|[\\/])\.|\.part|storyboard\.html$|__pycache__/;
  watch(ROOT, { recursive: true }, (_, file) => {
    if (!file || IGNORE.test(file)) return;
    let kind = null;
    if (file === 'video.json') kind = 'build';
    else if (/\.(mjs|json|png|jpe?g|webp|svg|ttf|otf)$/i.test(file) && !/^package(-lock)?\.json$/.test(file)) kind = 'reload';
    if (!kind || (state.building && kind === 'reload')) return;
    reason = reason === 'build' ? 'build' : kind;
    clearTimeout(timer);
    timer = setTimeout(() => { const r = reason; reason = null; r === 'build' ? rebuild() : startRenderer(); }, 200);
  });

  const page = fileURLToPath(new URL('./studio.html', import.meta.url));
  const http = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const send = (code, type, body) => { res.writeHead(code, { 'content-type': type, 'cache-control': 'no-store' }); res.end(body); };
    try {
      if (url.pathname === '/') return send(200, 'text/html; charset=utf-8', readFileSync(page));
      if (url.pathname === '/state') return send(200, 'application/json', JSON.stringify(state));
      if (url.pathname === '/timeline.json') {
        if (!existsSync(ROOT + 'timeline.json')) return send(404, 'text/plain', 'missing timeline.json');
        return send(200, 'application/json', readFileSync(ROOT + 'timeline.json'));
      }
      if (url.pathname === '/events') {
        res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-store', connection: 'keep-alive' });
        res.write(`data: ${JSON.stringify(state)}\n\n`);
        clients.add(res);
        req.on('close', () => clients.delete(res));
        return;
      }
      if (url.pathname === '/frame') {
        const t = Number(url.searchParams.get('t')), width = Number(url.searchParams.get('w') ?? 960);
        if (!Number.isFinite(t) || !Number.isFinite(width)) return send(400, 'text/plain', 'frame needs t and w');
        try { return send(200, 'image/jpeg', await frame(t, width)); }
        catch (error) { return send(503, 'text/plain', error.message); }
      }
      if (url.pathname === '/audio') {
        const file = ROOT + 'out/audio-mix.mp3';
        if (!existsSync(file)) return send(404, 'text/plain', 'no audio mix; run ./make.sh prepare');
        // byte ranges let the browser seek in the audio
        const size = statSync(file).size, range = /bytes=(\d*)-(\d*)/.exec(req.headers.range ?? '');
        if (!range) {
          res.writeHead(200, { 'content-type': 'audio/mpeg', 'content-length': size, 'accept-ranges': 'bytes', 'cache-control': 'no-store' });
          return createReadStream(file).pipe(res);
        }
        let a = range[1] === '' ? size - Number(range[2]) : Number(range[1]);
        let b = range[1] !== '' && range[2] !== '' ? Number(range[2]) : size - 1;
        a = Math.max(0, a); b = Math.min(size - 1, b);
        if (a > b) { res.writeHead(416, { 'content-range': `bytes */${size}` }); return res.end(); }
        res.writeHead(206, { 'content-type': 'audio/mpeg', 'content-length': b - a + 1, 'content-range': `bytes ${a}-${b}/${size}`, 'accept-ranges': 'bytes', 'cache-control': 'no-store' });
        return createReadStream(file, { start: a, end: b }).pipe(res);
      }
      send(404, 'text/plain', 'not found');
    } catch (error) {
      send(500, 'text/plain', error.stack ?? String(error));
    }
  });

  // use the first free port from --port up
  let port = firstPort;
  await new Promise((resolve, reject) => {
    http.on('error', error => {
      if (error.code === 'EADDRINUSE' && port < firstPort + 20) http.listen(++port, '127.0.0.1');
      else reject(error);
    });
    http.on('listening', resolve);
    http.listen(port, '127.0.0.1');
  });
  // keep the event streams alive through proxies and sleeping tabs
  setInterval(() => { for (const res of clients) res.write(': ping\n\n'); }, 15000).unref();
  startRenderer();
  console.log(`studio: http://127.0.0.1:${port}/  (Ctrl-C to stop)`);
  const stop = () => { child?.kill(); process.exit(0); };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
}
