# CLAUDE.md — How the team builds & runs THIS store (and uses it as a template)

> **עברית (קצר):** התיקייה הזאת היא **מקור-האמת** וגם **התבנית** לבניית חנות.
> לפני שעושים *משהו* בחנות — **קוראים את כל הקבצים כאן** (README, OWNER, CHANGELOG,
> וכל הקבצים ב-`style/`). בונים את החנות שתיראה **בדיוק כמו התבנית** (`design.html` +
> `site.json`/`product.json`). כל שינוי נרשם ב-`CHANGELOG.md`. עונים לאיציק בעברית,
> קצר וישר.

This folder **is** the TIMEOF BABY storefront *and* the **template** every Shopify
store is built from. The live store is *rendered from* these files — if it isn't
represented here, it isn't real and the next render overwrites it.

**The rule for every agent: READ before you act, BUILD to match the template, LOG every change.**

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
stores/shopify/timeofbaby.alpha-tech.live/
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

Programmatically, load them with **`read_store_docs("timeofbaby")`** (returns
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
- **Already live — do NOT redo:** Color+Size variants (auto from CJ), 7-image hero, free
  shipping, social-proof, real CJ descriptions, JSON-driven font sizes.

**To build a NEW store from this template** (per the owner: copy this folder under
`stores/shopify/<new-domain>/`): copy the whole structure, then in the new copy adapt
`site.json`/`product.json` (brand name, colors, copy, niche), keep the same section
structure + tokens, and re-point the readme/changelog to the new store. Same look,
new brand.

---

## 3. THE ONLY CORRECT WAY TO CHANGE THE STORE

```text
1. read_store_docs("timeofbaby")  +  read each style/ file       (READ)
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
