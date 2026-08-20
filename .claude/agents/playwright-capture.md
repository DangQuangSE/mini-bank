---
name: playwright-capture
description: General-purpose Playwright screenshot agent. Auto-detects capture mode from inputs — section-centered viewport (show-off), element clip, or full page. Optional BG_SOURCE triggers composite step (background photo + card overlay). Spawned by /show-off and any task needing screenshots.
tools: ["Write", "Bash"]
model: haiku
---

Screenshot pages or elements using Playwright. Auto-detect the capture mode from what's provided.

## Input

All fields optional — agent infers mode from what's present:

| Field        | Description                                                                |
| ------------ | -------------------------------------------------------------------------- |
| `HTML_PATH`  | Absolute path to an HTML file (or URL)                                     |
| `OUTPUT_DIR` | Absolute path for PNG output                                               |
| `RUNNER`     | Absolute path to `playwright-skill/run.js`                                 |
| `SECTIONS`   | CSS IDs to capture (e.g. `hero,features,demo,cta`) — triggers section mode |
| `SELECTOR`   | Single CSS selector — triggers element clip mode                           |
| `VIEWPORTS`  | `16x9`, `9x16`, `1x1` (comma-separated, default: `16x9`)                   |
| `THEME`      | `dark`, `light`, or `both` (sets `data-theme` on `<html>`)                 |
| `LANG`       | `en`, `vi`, or `both` (calls `window.applyLang(lang)` if available)        |
| `BG_SOURCE`  | Folder path or `auto` — enables composite step                             |
| `SCALE`      | Device scale factor (default: `2`)                                         |

## Auto-detect Mode

| Condition           | Mode                                                                               |
| ------------------- | ---------------------------------------------------------------------------------- |
| `SECTIONS` provided | **Section** — resize viewport to section height, scroll section to top, screenshot |
| `SELECTOR` provided | **Element** — clip to element bounding box                                         |
| Neither             | **Page** — full-page screenshot                                                    |

## Steps

### 1. Resolve inputs + create output dir

```bash
mkdir -p "<OUTPUT_DIR>"
```

Expand `both` values: `THEME=both` → `['dark','light']` · `LANG=both` → `['en','vi']`

If `BG_SOURCE=auto`: set `BG_DIR = OUTPUT_DIR + '/backgrounds'`, `mkdir -p` it, then download one JPG per section:

```bash
curl -L -o "<BG_DIR>/bg-<N>.jpg" "https://source.unsplash.com/1080x1080/?nature,bokeh&sig=<N>"
```

If `BG_SOURCE` is a folder path: set `BG_DIR = BG_SOURCE`.

### 2. Write capture script

Write `<OUTPUT_DIR>/../capture.js` — substitute all `<PLACEHOLDERS>` before writing. Substitution rules:

- `<HTML_PATH>` → actual path value, forward slashes
- `<OUTPUT_DIR>` → actual output dir, forward slashes
- `<SECTIONS_ARRAY>` → JS string literals e.g. `'hero','features'` or empty
- `<SELECTOR>` → CSS selector string, or `''` if not provided
- `<THEMES_ARRAY>` → e.g. `'dark','light'`
- `<LANGS_ARRAY>` → e.g. `'en','vi'`
- `<VIEWPORTS_ARRAY>` → e.g. `'1x1'`
- `<BG_DIR>` → absolute path to backgrounds folder, or `''` if no composite
- `<SCALE>` → numeric value e.g. `2`

```javascript
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');

const SRC      = '<HTML_PATH>';
const TARGET   = SRC.startsWith('http') ? SRC : 'file:///' + SRC.replace(/\\/g, '/');
const OUT      = '<OUTPUT_DIR>';
const SECTIONS = [<SECTIONS_ARRAY>];
const SELECTOR = '<SELECTOR>';
const THEMES   = [<THEMES_ARRAY>];
const LANGS    = [<LANGS_ARRAY>];
const BG_DIR   = '<BG_DIR>';
const SCALE    = <SCALE>;

const VIEWPORT_MAP = {
  '16x9': { width: 1920, height: 1080 },
  '9x16': { width: 1080, height: 1920 },
  '1x1':  { width: 1080, height: 1080 },
};
const VIEWPORTS = [<VIEWPORTS_ARRAY>].map(n => ({ name: n, ...VIEWPORT_MAP[n] }));

const bgFiles = BG_DIR && fs.existsSync(BG_DIR)
  ? fs.readdirSync(BG_DIR).filter(f => /\.(jpg|jpeg|png)$/i.test(f)).map(f => path.join(BG_DIR, f))
  : [];

async function applyState(page, theme, lang) {
  if (theme) await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
  if (lang)  await page.evaluate(l => { if (typeof window.applyLang === 'function') window.applyLang(l); }, lang);
  await page.waitForTimeout(300);
}

async function composite(compositePage, cardPath, bgPath, outPath, vp) {
  await compositePage.setViewportSize({ width: vp.width, height: vp.height });
  // base64 data URIs required — setContent() runs at about:blank which blocks file:// loads
  const bg   = 'data:image/jpeg;base64,' + fs.readFileSync(bgPath).toString('base64');
  const card = 'data:image/png;base64,'  + fs.readFileSync(cardPath).toString('base64');
  await compositePage.setContent(`<!DOCTYPE html><html><head><style>
    *    { margin:0; padding:0; box-sizing:border-box; }
    body { width:${vp.width}px; height:${vp.height}px; overflow:hidden;
           background:url('${bg}') center/cover no-repeat; }
    img  { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
           width:86%; max-height:86%; object-fit:contain;
           border-radius:24px;
           box-shadow:0 24px 80px rgba(0,0,0,0.45),0 0 0 1px rgba(255,255,255,0.08); }
  </style></head><body><img src="${card}"></body></html>`,
  { waitUntil: 'domcontentloaded' });
  await compositePage.waitForTimeout(200);
  await compositePage.screenshot({ path: outPath });
}

async function captureSection(page, compositePage, sectionId, vp, theme, lang, bgFile) {
  // Get document-absolute position using getBoundingClientRect + scrollY (reliable across all layouts)
  const metrics = await page.evaluate(id => {
    const el = document.getElementById(id);
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return { top: Math.round(rect.top + window.scrollY), height: Math.ceil(rect.height) };
  }, sectionId);

  if (!metrics) { console.warn(`#${sectionId} not found`); return; }

  // Resize viewport to exact section height — eliminates adjacent-section bleed
  await page.setViewportSize({ width: vp.width, height: metrics.height });
  await page.evaluate(y => window.scrollTo({ top: y, behavior: 'instant' }), metrics.top);
  await page.waitForTimeout(200);

  const suffix = [sectionId, vp.name, theme, lang].filter(Boolean).join('-');
  const finalPath = `${OUT}/${suffix}.png`;
  const capturePath = bgFile ? `${OUT}/${suffix}-raw.png` : finalPath;
  await page.screenshot({ path: capturePath });

  // Restore nominal viewport width so next section's layout is computed at full width
  await page.setViewportSize({ width: vp.width, height: vp.height });

  if (bgFile) {
    await composite(compositePage, capturePath, bgFile, finalPath, vp);
    fs.unlinkSync(capturePath);
  }
  console.log(`✓ ${suffix}${bgFile ? ' (composited)' : ''}`);
}

async function captureElement(page, selector, vp, theme, lang) {
  const el = await page.$(selector);
  if (!el) { console.warn(`selector "${selector}" not found`); return; }
  const suffix = [selector.replace(/[^a-z0-9]/gi, '_'), vp.name, theme, lang].filter(Boolean).join('-');
  await el.screenshot({ path: `${OUT}/${suffix}.png` });
  console.log(`✓ ${suffix}`);
}

async function capturePage(page, vp, theme, lang) {
  const suffix = [vp.name, theme, lang].filter(Boolean).join('-');
  await page.screenshot({ path: `${OUT}/${suffix}.png`, fullPage: true });
  console.log(`✓ page ${suffix}`);
}

if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });

  const compositeCtx = bgFiles.length
    ? await browser.newContext({ viewport: { width: 1080, height: 1080 }, deviceScaleFactor: SCALE })
    : null;
  const compositePage = compositeCtx ? await compositeCtx.newPage() : null;

  const combos = VIEWPORTS.flatMap(vp =>
    THEMES.flatMap(theme => LANGS.map(lang => ({ vp, theme, lang })))
  );

  for (const { vp, theme, lang } of combos) {
    const ctx  = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: SCALE });
    const page = await ctx.newPage();
    // 'load' avoids blocking on external fonts (Google Fonts etc.) in headless
    await page.goto(TARGET, { waitUntil: 'load' });
    await page.waitForTimeout(1500);
    await applyState(page, theme, lang);

    if (SECTIONS.length > 0) {
      for (let i = 0; i < SECTIONS.length; i++) {
        const bg = bgFiles.length ? bgFiles[0] : null;
        await captureSection(page, compositePage, SECTIONS[i], vp, theme, lang, bg);
      }
    } else if (SELECTOR) {
      await captureElement(page, SELECTOR, vp, theme, lang);
    } else {
      await capturePage(page, vp, theme, lang);
    }

    await ctx.close();
  }

  if (compositeCtx) await compositeCtx.close();
  await browser.close();
  console.log('\nDone.');
})();
```

### 3. Execute

```bash
node "<RUNNER>" "<OUTPUT_DIR>/../capture.js"
```

### 4. Report

```
## Capture Results

Mode: section | element | page
Images: <OUTPUT_DIR>
Composite: yes (bg from <BG_SOURCE>) | no

✓ hero-1x1-dark-en.png
✓ hero-1x1-dark-vi.png
...

Total: <N>/<expected>  Failed: <list with error>
```
