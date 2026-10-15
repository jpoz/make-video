// Screenshots of the real app, for screens.mjs. For each step in shots/plan.mjs it runs the
// actions in a real Chromium page, then writes shots/out/<name>.png (2x) and shots/out/<name>.json:
// the bounding box (CSS px) of every selector in the step's "boxes", so rings and the cursor
// can land on real elements.
//
// Setup once:   npm i -D playwright && npx playwright install chromium
// Run:          node shots/capture.mjs            (only one step: node shots/capture.mjs <name>)
//
// plan.mjs exports { url, viewport?, dark?, setup?(page), steps: [{ name, go?, actions?(page), boxes: {key: selector} }] }.
// Steps run in order on one page, so each step starts where the last one ended.
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const { chromium } = await import('playwright').catch(() => {
  console.error('playwright is not installed: npm i -D playwright && npx playwright install chromium');
  process.exit(1);
});
const plan = (await import(HERE + 'plan.mjs')).default;
const only = process.argv[2];
const OUT = HERE + 'out/';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const vp = plan.viewport ?? { width: 1600, height: 900 };
const page = await (await browser.newContext({ viewport: vp, deviceScaleFactor: 2, colorScheme: plan.dark ? 'dark' : 'light' })).newPage();
page.on('pageerror', e => console.log('page error:', e.message));
await page.goto(plan.url);
if (plan.setup) await plan.setup(page);

for (const step of plan.steps) {
  if (step.go) await page.goto(new URL(step.go, plan.url).href);
  if (step.actions) await step.actions(page);
  await page.waitForTimeout(step.settle ?? 400);
  if (only && step.name !== only) continue;
  const boxes = {};
  for (const [key, sel] of Object.entries(step.boxes ?? {})) {
    const b = await page.locator(sel).first().boundingBox().catch(() => null);
    if (!b) { console.warn(`  ${step.name}: no box for ${key} (${sel})`); continue; }
    boxes[key] = { x: Math.round(b.x), y: Math.round(b.y), width: Math.round(b.width), height: Math.round(b.height) };
  }
  await page.screenshot({ path: `${OUT}${step.name}.png` });
  writeFileSync(`${OUT}${step.name}.json`, JSON.stringify(boxes, null, 1));
  console.log(`${step.name}: ${Object.keys(boxes).length} boxes`);
}
await browser.close();
