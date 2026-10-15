// The film's look: fonts, palette, background. Change this file to restyle the whole film.
// Two starting palettes: 'ink' (near-black, red accent) and
// 'navy' (deep blue, sky-blue and amber accents). Or make your own.
import { GlobalFonts, createCanvas } from '@napi-rs/canvas';
import { existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// Fonts are not shipped with the skill. Put .ttf/.otf files in ./fonts (see the skill's
// references/fonts.md for where to get them); every file there is registered by its own family name.
const FONTS = fileURLToPath(new URL('./fonts/', import.meta.url));
const files = existsSync(FONTS) ? readdirSync(FONTS).filter(f => /\.(ttf|otf)$/i.test(f)) : [];
for (const f of files) GlobalFonts.registerFromPath(FONTS + f);
if (!files.length) console.warn('theme.mjs: no fonts in ./fonts, using system fonts (see references/fonts.md)');

export const W = 1920, H = 1080;
// JetBrains Mono is the fallback for arrows and symbols Atkinson lacks (→ ↔ ✓ ⋯); system fonts come last
export const SANS = '"Atkinson Hyperlegible", "JetBrains Mono", "Helvetica Neue", Arial, sans-serif';
export const MONO = '"JetBrains Mono", Menlo, Consolas, monospace';
export const DISPLAY = SANS;

const fg = '#f2ecdf', a = x => `rgba(242,236,223,${x})`;
const PALETTES = {
  ink: {
    bg: '#0c111e', bg2: '#070a13', accent: '#ea0c00', accentFill: 'rgba(234,12,0,0.16)',
    blue: '#33bbff', blueFill: 'rgba(51,187,255,0.16)', amber: '#ff9922', amberFill: 'rgba(255,153,34,0.15)',
  },
  navy: {
    bg: '#111144', bg2: '#0a0a2e', accent: '#33bbff', accentFill: 'rgba(51,187,255,0.16)',
    blue: '#33bbff', blueFill: 'rgba(51,187,255,0.16)', amber: '#ff9922', amberFill: 'rgba(255,153,34,0.15)',
  },
};
export const THEME = 'ink';
export const C = {
  ...PALETTES[THEME],
  fg, mute: a(0.6), faint: a(0.3), ghost: a(0.12), fill: a(0.06), panel: 'rgba(5,5,20,0.55)',
  red: '#ff4a3d', redFill: 'rgba(255,74,61,0.16)', green: '#2fbf86', greenFill: 'rgba(47,191,134,0.16)', violet: '#b48cff',
};

// Drawn once, then blitted every frame: a soft radial gradient and a faint grid.
export const background = (() => {
  const cv = createCanvas(W, H), b = cv.getContext('2d');
  const g = b.createRadialGradient(W / 2, H * 0.45, 100, W / 2, H / 2, W * 0.75);
  g.addColorStop(0, C.bg); g.addColorStop(1, C.bg2);
  b.fillStyle = g; b.fillRect(0, 0, W, H);
  b.strokeStyle = 'rgba(242,236,223,0.03)'; b.lineWidth = 1;
  for (let x = 0; x <= W; x += 48) { b.beginPath(); b.moveTo(x + 0.5, 0); b.lineTo(x + 0.5, H); b.stroke(); }
  for (let y = 0; y <= H; y += 48) { b.beginPath(); b.moveTo(0, y + 0.5); b.lineTo(W, y + 0.5); b.stroke(); }
  return cv;
})();
