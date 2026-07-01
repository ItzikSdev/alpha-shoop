# CLAUDE.md — How the team builds & runs THIS store (and uses it as a template)

> **עברית (קצר):** התיקייה הזאת היא **מקור-האמת** וגם **התבנית** לבניית חנות.
> לפני שעושים *משהו* בחנות — **קוראים את כל הקבצים כאן** (README, OWNER, CHANGELOG,
> וכל הקבצים ב-`style/`). בונים את החנות שתיראה **בדיוק כמו התבנית** (`design.html` +
> `site.json`/`product.json`). כל שינוי נרשם ב-`CHANGELOG.md`. עונים לאיציק בעברית,
> קצר וישר.

This folder **is** the TIMEFOR BABY storefront *and* the **template** every Shopify
store is built from. The live store is *rendered from* these files — if it isn't
represented here, it isn't real and the next render overwrites it.

**The rule for every agent: READ before you act, BUILD to match the template, LOG every change.**

> **STORE FOLDER:** the ONLY store folder is `stores/shopify/timeforbaby.alpha-tech.live`. NEVER create `stores/<name>/` — a builds theme-install may drop a stray `stores/<slug>/theme/`; ignore/delete it, it is NOT the store.
> **META ADS:** the team has a Meta ad account — `META_ACCESS_TOKEN` + `META_AD_ACCOUNT_ID=act_1587251408528238` in .env. Max can launch Facebook/Instagram ads.

---

## 0. Who reads this — the team (2026-06-29 roster)

The autonomous flow is 5 agents (orchestrated by the CEO). Wherever older docs say
"Linus / Grace", the **current** team is:

| Agent | Role | What they do with THIS folder |
|-------|------|-------------------------------|
| **Ava** | CEO / Orchestrator | Picks the next run; makes sure the store matches the template; HITL on Slack. |
| **Hunter** | Product Hunter | Sources CJ products (rating, shipping, inventory) + net margin; fills the catalog the store renders. |
| **Remy** | UX & Content | **Owns the look + copy.** Edits `style/` JSON to match `design.html`, writes product copy. |
| **Devon** | Shopify Developer | Pushes the validated catalog + applies the design to the live Shopify theme via GraphQL. |
| **Max** | Growth Marketer | Facebook & Instagram / ads — drives traffic once the store looks flawless. |

---

## 1. READ ALL OF THESE FIRST (every time, before any change)

```text
stores/shopify/timeforbaby.alpha-tech.live/
├── CLAUDE.md           ← THIS guide (how to build + the rules)
├── readme/
│   ├── README.md       ← the source-of-truth rules (the only correct way to change the store)
│   └── OWNER.md        ← who Itzik is + how to read his intent (read EVERY time)
├── changelog/CHANGELOG.md  ← every change, newest on top — read the head for recent history
├── finance/LEDGER.md   ← revenue vs cost over time (incl. what the agents cost in tokens)
└── style/              ← THE DESIGN — edit these, never the live .liquid by hand
    ├── design.html     ← the APPROVED visual mockup = the target look to build toward
    ├── site.json       ← homepage spec (design_tokens + 9 sections) — single source of truth for the homepage
    ├── product.json    ← product-page spec (typography tokens, size_chart, badges, css)
    ├── product.liquid  ← product section markup (gallery, Color+Size selectors, add-to-cart)
    └── home.liquid     ← hand-written homepage section (reference/fallback; site.json is primary)
```

Programmatically, load them with **`read_store_docs("timeforbaby")`** (returns
`claude` + `readme` + `owner` + `changelog_recent`) and read each `style/` file
with the design-file read tool. **Do not change the store before you've read them.**

---

## 2. BUILD THE STORE LIKE THE TEMPLATE

The approved look is defined by **`design.html`** + **`site.json` (v3)** + **`product.json`**.
Build/restore the store so the live Shopify theme matches it — don't invent a new look.

**The design system (what "like the template" means):**
- **Premium, clean, baby-clothes brand.** Colors from `site.json → design_tokens.colors`
  (ink `#161616`, soft `#f6f4f1`, line `#eee`, accent, footer tokens). Typography +
  spacing + animation + responsive all come from `design_tokens` — change the look by
  editing **tokens/values**, never by hardcoding in `.liquid`.
- **Homepage sections (from `site.json → sections`, ~9):** dark scrolling **marquee** →
  **7-image hero carousel** (crossfade + slow zoom) → **category tiles** → **product grid**
  (3:4 cards, hover-rise) → **social-proof** popup → story → multi-column footer.
- **Product page (from `product.json`):** gallery, **Color + Size selectors** (each variant
  bound to its exact CJ SKU), size chart, trust badges, add-to-cart. Typography tokens drive
  the live font sizes.
- **PRODUCT IMAGES — vet before listing (owner rule):** every product photo must be a
  clean, *sellable, styled/lifestyle* shot. **Reject** plain white/studio-background-only
  images, ANY image with visible text / watermark / foreign language (e.g. Chinese),
  collages, and low-quality shots. The pipeline vision-vets CJ images automatically
  (`_vet_images` in `ecommerce.py`, Haiku vision); a product with **no** good image is
  **not listed**. Products that are already live with no image or a foreign-language
  (CJK) title get **removed** — run `cleanup_bad_products(dry_run=False)`.
- **FONT RULE (template rule):** minimum font-size is **1.8rem EVERYWHERE** on the
  storefront. EXCEPTIONS: **logo = 2rem**, **buttons (add-to-cart + option buttons) = 1.5rem**,
  and **product-page description = 1.5rem** (`product.json → typography.description_size` /
  `option_button_size`). The homepage floor + logo/button exceptions live in the renderer's
  `_TOB_CSS` (`OWNER FONT RULE` block); product-page sizes in `product.json`. Never set
  any other storefront text below 1.8rem.
- **NO DUPLICATE PRODUCTS:** never list the same item twice. The pipeline skips
  candidates whose image already exists live; run `dedupe_products(dry_run=False)`
  (shopify.py) to remove existing duplicates (same title or same main image).
- **THE HOMEPAGE CSS IS IN THE TEMPLATE:** `site.json → "css"` (array of CSS lines) is
  now the source of truth for the homepage design — layout AND styling. Edit it (or the
  `sections` / `design_tokens`) and run `apply_site_design`; you no longer need to touch
  Python to restyle the store. SAFETY: you may edit/add, but **never delete a section or
  the css wholesale without logging it in CHANGELOG.md first** — every change is recorded
  with a timestamp via `append_changelog`, so nothing is silently lost.
- **NAV RULE (owner):** the ONLY links anywhere on the store — header, category tiles,
  footer — are **Baby Boys** (`/collections/baby-boys`), **Baby Girls** (`/collections/baby-girls`),
  **Unisex** (`/collections/unisex`). "Shop All" = **Unisex**. NO other links in nav/footer
  (no policies/pages/social link lists). Every new product goes into exactly one of these 3.
- **NO DUPLICATE PHOTOS on a product:** never repeat the same image within a product —
  dedup by image CONTENT (not filename; Shopify re-hosts with new names). Keep one per shot.
- **NO $0 PRODUCTS:** every variant must be priced. Run `fix_zero_prices(dry_run=False)`
- **UNIFORM PRODUCT IMAGES:** all product-card images render at ONE fixed ratio (4:5 / 125%, object-fit:cover) so the collection grid is even. Prefer consistent-ratio source photos; the theme CSS enforces it.
  (re-prices $0 variants from the mapped retail; removes ones with no price on file).
- **SEO LIKE A PRO (every product):** a unique, human, keyword-rich **title** (baby + garment
  type + key feature; NO supplier codes/jargon); a unique **meta description** (~150–160 chars,
  benefit-led); **descriptive alt text** on every image; a clean **handle**; **never** reuse
  copy across products (unique descriptions only). Lead with the organic-cotton angle + the
  target audience (new parents / gift-givers).
- **AGENTS RUN OPS FROM CHAT (don't just talk):** `dedupe_products`, `cleanup_bad_products`,
  `fix_zero_prices`, `apply_site_design`/`apply_product_design` — Devon/Remy execute these
  when asked, then log to CHANGELOG.md with a timestamp.
- **Already live — do NOT redo:** Color+Size variants (auto from CJ), editorial split hero
  (`design_handoff_hero`), free shipping, social-proof, real CJ descriptions, JSON-driven
  fonts (min 1.8rem; logo 2rem; buttons 1.5rem), sticky header nav (`site.json → site_header`),
  homepage CSS in `site.json → "css"` (edit there, not Python).

**To build a NEW store from this template** (per the owner: copy this folder under
`stores/shopify/<new-domain>/`): copy the whole structure, then in the new copy adapt
`site.json`/`product.json` (brand name, colors, copy, niche), keep the same section
structure + tokens, and re-point the readme/changelog to the new store. Same look,
new brand.

---

## 3. THE ONLY CORRECT WAY TO CHANGE THE STORE

```text
1. read_store_docs("timeforbaby")  +  read each style/ file       (READ)
2. Edit the JSON value(s) in style/site.json / style/product.json (EDIT — JSON, never live .liquid)
3. Apply it live:
     homepage      → apply_site_design()       (renders site.json)
     product page  → apply_product_design()     (renders product.json)
     (home.liquid fallback only → apply_store_homepage())
4. append_changelog(title, changed, by, context)                 (LOG — always)
```

**Golden rules (full version in `readme/README.md`):**
1. The `style/` JSON files are the **source of truth** — edit them + run the `apply_*`
   tool. **Never** hand-edit the live `.liquid` on Shopify; the next render wipes it.
2. **Read before you write** (Section 1). 3. **Log every change** in `CHANGELOG.md`.
4. **Never revert the approved design** — if the live store drifts from `design.html`/
   `site.json`, **re-apply**, don't redesign from scratch. 5. **Don't redo done work**;
   the real lever to revenue is **traffic (ads)**, not redesign loops.

---

## 4. CHANGELOG entry format (newest on top)

```markdown
## YYYY-MM-DD HH:MM (Asia/Jerusalem) — <short title>
**By:** <Ava | Hunter | Remy | Devon | Max | Itzik | system>
**Context:** <why — one or two lines>
**Changed:** <exactly what: which file/section/field, old → new>
```

Use **`append_changelog(...)`** — it writes this format automatically, timestamped in
Asia/Jerusalem. One entry per change.

---

## 5. Reminders from OWNER.md (read the full file)

Itzik writes **Hebrew, short, direct**, often several requests in one message — **reply
in Hebrew**, address each part, take his concrete examples literally, and give **honest
status** (a real "not done / not connected" beats a fake "✓"). He notices every visual
detail and hates: silently reverted work, anything that looks "off", being kept in the
dark, and redoing finished work. When unsure, **match the approved design** — don't improvise.
