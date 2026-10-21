// Logical scene coordinates stay stable when preview output is scaled down.
import { readFileSync } from 'node:fs';

export const SPEC = JSON.parse(readFileSync(new URL('./video.json', import.meta.url), 'utf8'));
export const FORMAT = SPEC.output?.format ?? 'landscape';
const sizes = { landscape: [1920, 1080], portrait: [1080, 1920], square: [1080, 1080] };
if (!Object.hasOwn(sizes, FORMAT)) throw new Error(`unknown output.format: ${FORMAT}`);
export const [W, H] = sizes[FORMAT];
export const SAFE = { x: 80, y: 100, w: W - 160, h: H - 280 };

export function outputSettings(args = []) {
  const option = (key, fallback) => {
    const i = args.indexOf(key);
    if (i < 0) return fallback;
    if (args[i + 1] == null || args[i + 1].startsWith('--')) throw new Error(`${key} needs a value`);
    return args[i + 1];
  };
  const quality = option('--quality', SPEC.output?.quality ?? 'final');
  if (!['preview', 'final'].includes(quality)) throw new Error('quality must be preview or final');
  const fps = Number(option('--fps', quality === 'preview' ? Math.min(SPEC.fps ?? 60, 30) : SPEC.fps ?? 60));
  const workers = Number(option('--workers', SPEC.output?.workers ?? 2));
  const blur = Number(option('--blur', 1));
  for (const [label, value, max] of [['fps', fps, 120], ['workers', workers, 32], ['blur', blur, 16]]) {
    if (!Number.isInteger(value) || value < 1 || value > max) throw new Error(`${label} must be an integer from 1 to ${max}`);
  }
  const scale = quality === 'preview' ? 0.5 : 1;
  return { quality, fps, workers, blur, width: W * scale, height: H * scale, scale };
}
