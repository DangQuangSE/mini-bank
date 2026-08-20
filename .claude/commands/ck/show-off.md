---
description: Generate impressive multi-section HTML presentations with parallax, theme toggle, bilingual VI/EN — then auto-capture as 16:9, 9:16, 1:1 social-ready images
argument-hint: [--auto|--fast|--clone] <topic>
---

# /ck:show-off — HTML Presentation + Social Capture

## Usage

```
/ck:show-off [--auto | --fast | --clone] <topic>
```

- **_(none)_** — Interactive: ask style/content, review gate before capture
- **`--auto`** — Skip all prompts, use defaults (gradient, 16x9+9x16+1x1, dark, en)
- **`--fast`** — Ask style only, skip review gate, capture immediately
- **`--clone`** — Re-capture existing HTML in `tmp/ck:show-off-<slug>/`, skip generation

---

### Step 1 — Parse

Strip flag from `$ARGUMENTS`. Derive `<slug>` (kebab-case) and `<title>`. Fallback: git branch name.

Output dir: `<project-root>/tmp/ck:show-off-<slug>/`

---

### Step 2 — Ask (interactive only)

**Skip if `--auto`, `--fast`, or `--clone`.**

Single message — do not ask one-by-one:

```
🎨 Show-off setup for "<title>"

Visual
  1. Style      gradient · minimal · neon · glass · editorial  [gradient]
  2. Viewports  16x9 · 9x16 · 1x1 · all                       [all]
  3. Theme      dark · light                                    [dark]
  4. Language   en · vi                                         [en]

Content
  5. Key message   One sentence — the headline value prop
  6. Highlights    3 features/points to showcase (comma-separated)
  7. Demo type     code · pipeline · screenshot · table          [code]

Background
  8. Background    folder path · auto                            [auto]

Example: "neon, 1x1, dark, en / Fastest way to ship · /ck:plan, /ck:cook, /ck:fix · pipeline / auto"
```

For any content field left blank — ask a targeted follow-up before generating. Do **not** invent content from the repo without asking.

`auto` background: search for a royalty-free photo via Unsplash API or pick randomly from `tmp/ck:show-off-<slug>/backgrounds/` if it exists.

`--fast`: ask style only (one line), skip the rest.

---

### Step 3 — Generate

**Skip if `--clone`.**

Write `tmp/ck:show-off-<slug>/index.html` — fully self-contained, no build step.

Sections in order: `#hero` (title, tagline, CTA) · `#features` (3 cards) · `#demo` (code/pipeline/detail) · `#cta` (share, install, stats)

#### Style recipes

**`gradient`** — Modern dev-tool / Inter 400/700/900 + JetBrains Mono

```
Dark  --bg:#0a0a0f --bg2:#111118 --bg3:#1a1a24 --fg:#e8e8f0 --fg2:#9999bb
      --accent:#7c6af5 --accent2:#a78bfa --accent3:#34d399
      --border:rgba(124,106,245,0.2) --card:rgba(26,26,36,0.8)
      --glow:rgba(124,106,245,0.15) --code-bg:#0d0d1a
Light --bg:#f5f5ff --bg2:#ebebff --bg3:#ddddf8 --fg:#111128 --fg2:#4444aa
      --accent:#5b47e0 --accent2:#7c5ce8 --accent3:#059669
      --border:rgba(91,71,224,0.25) --card:rgba(255,255,255,0.85)
      --glow:rgba(91,71,224,0.1) --code-bg:#1a1a2e  ← always dark, even in light
```

Techniques: gradient text via `-webkit-background-clip:text` (white→accent dark, `#111`→accent light — separate `[data-theme="light"] h1` rule required) · hero bg `radial-gradient` no `fixed` attachment · card `translateY(-4px)` + accent border + glow shadow on hover · `::before` 2px gradient top-border reveal · glow CTA button

**`minimal`** — Claude Code docs / Inter + JetBrains Mono + Playfair Display (hero)

Light `--bg-base:#faf9f7 --accent:#c15f3c --accent-sub:rgba(193,95,60,0.08) --bg-border:#ddd8d0` / Dark `--bg-base:#0a0a0a --bg-surface:#111111 --bg-border:#2a2a2a`

Techniques: `── LABEL ──` cover rule via flanking `<span class="rule">` · JetBrains Mono eyebrow uppercase · Playfair Display italic hero heading · bordered cards with accent glow on hover · `◈` section kicker

**`neon`** — Cyberpunk / Orbitron + Share Tech Mono · `--bg:#000 --green:#00ff41 --cyan:#00f5ff --magenta:#ff00aa`

Techniques: double `text-shadow` glow · CRT scanlines `body::after repeating-linear-gradient` · rolling scan beam animation · `@keyframes glitch` clip-path on h1 · corner bracket `::before/::after`

**`glass`** — Frosted future / Plus Jakarta Sans · mesh blobs (`#7c3aed #06b6d4 #ec4899`, blur:100px, position:fixed)

Techniques: `backdrop-filter:blur(16px)` glass cards · shimmer box-shadow border on hover · deeper blur on hover · `rgba` CTA button

**`editorial`** — Print magazine / DM Serif Display + Inter · `--bg:#fafaf8 --accent:#d4231a` (dark: `--bg:#111`)

Techniques: `border-top:3px` rule openers · oversized h1 `clamp(3.5rem,10vw,8rem)` · pull-quote `border-left:4px` · magazine dateline badge

#### Universal rules

- z-index: `::before`/`::after` → 0, text content → 1
- Hero: `max-width:720px` container, `font-size:clamp(2rem,6vw,5rem)`
- Sections: `padding:clamp(48px,8vw,96px) clamp(28px,6vw,80px)` — no fixed px
- Capture height: ~600–800px per section, no forced scroll
- Cards: `grid-template-columns:repeat(3,1fr)` with separator lines
- Code: JetBrains Mono, `line-height:1.8`, `padding:20px 24px`
- Theme: all tokens in `:root` (dark), ALL overridden in `[data-theme="light"]`; `--code-bg` always dark; gradient text needs separate light rule; deepen accents for light contrast
- Required: `#theme-toggle` + `#lang-toggle` in `#controls`; `data-en`/`data-vi` on every string; `applyLang(lang)` global; vanilla JS only; no `background-attachment:fixed`; no `min-height:100vh` on sections

---

### Step 4 — Review gate

**Skip if `--auto`, `--fast`, or `--clone`.**

```
📄 Preview ready: tmp/ck:show-off-<slug>/index.html  Style: <style>
Open in browser — "ok" to capture · describe changes to iterate
```

Wait for user. Loop until approved.

---

### Step 5 — Capture + Composite

Spawn the **`playwright-capture`** agent:

```
HTML_PATH   = <project-root>/tmp/ck:show-off-<slug>/index.html
OUTPUT_DIR  = <project-root>/tmp/ck:show-off-<slug>/images
RUNNER      = <project-root>/.claude/skills/playwright-skill/run.js
SECTIONS    = hero, features, demo, cta
VIEWPORTS   = <chosen>  THEME = <chosen>  LANG = <chosen>
BG_SOURCE   = <folder path> | auto
```

**Capture method** — for each section: resize viewport height to the section's exact pixel height, scroll section to `top: 0`, screenshot. Each image contains exactly one section — no bleed from adjacent sections.

**Composite** — for each captured PNG:
1. Resize/crop one background image to the target viewport dimensions (cover)
2. Place the section PNG centered on the background with ~7% padding each side
3. Apply `border-radius: 24px` + `box-shadow: 0 24px 80px rgba(0,0,0,0.35)` to the card
4. Save final composite as `{section}-{viewport}-{theme}-{lang}.png`

**Background source resolution:**
- User path → use JPGs from that folder (rotate per section)
- `auto` → download a suitable photo from Unsplash (`https://source.unsplash.com/1080x1080/?nature,bokeh`) per section

---

### Step 6 — Report

```
✅ Show-off ready: tmp/ck:show-off-<slug>/
   Style: <style> · <viewports> · <theme> · <lang>
   Preview : tmp/ck:show-off-<slug>/index.html
   Images  : tmp/ck:show-off-<slug>/images/  (<N> files)
```

List any failed captures with section/viewport and error.

---

## Agents

| Agent                | Step                          | Modes                     |
| -------------------- | ----------------------------- | ------------------------- |
| `playwright-capture` | 5 — capture + composite       | All (after HTML is ready) |

---

## Integration

- `/ck:show-off --clone` — re-capture after manual HTML edits
- `/ck:show-off --auto <topic>` — zero-prompt batch generation
