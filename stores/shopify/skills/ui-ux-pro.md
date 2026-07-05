# SKILL: ui-ux-pro — build storefronts at a high (agency) design level

Sol reads this BEFORE any visual work and builds/checks against it. Goal: a premium,
conversion-focused storefront that looks like a top DTC brand — not a template.
English-only. Everything is driven by `theme.config.json` where possible.

## 1. Design system (use concrete scales — no arbitrary values)
- **Spacing scale (px):** 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128. Use ONLY these.
  Section vertical padding ≥ 64 desktop / 40 mobile. Content max-width ~1240px, gutters 24–28px.
- **Type scale (rem):** body 1 · small 0.85 · label 0.78 (uppercase, letter-spacing .08em) ·
  h3 1.1 · h2 1.6–1.9 · h1/hero clamp(40px,5vw,72px). Line-height: body 1.55, headings 1.05–1.2.
  Max ~2 font families (one display/serif for headings, one clean sans for body).
- **Color:** 1 ink (near-black text), 1–2 neutrals (soft bg, hairline border), 1 accent used
  sparingly (CTAs/links). Contrast ≥ 4.5:1 for text. Never pure #000 on pure #fff for large areas.
- **Radius/shadow:** consistent radius (0–8px, pick one). Shadows subtle (0 8px 30px rgba(0,0,0,.08))
  — used only for overlays/drawers/cards on hover, never everywhere.
- **Grid:** product grid 4-up desktop / 2-up mobile, uniform card ratio 4:5, gap from the scale.

## 2. Components — specs + ALL states
- **Buttons:** primary = solid accent/ink, ≥48px tall, padding 14–18px×28–34px, uppercase or
  sentence-case consistent, letter-spacing .06–.1em. States: default / hover (lift 2px or darken) /
  active / focus-visible (2px ring) / disabled (muted, no pointer) / loading (spinner or "…").
  One primary CTA per view. Secondary = outline/text link.
- **Product card:** image (4:5, object-fit cover, hover zoom 1.05, lazy) → title (1 line, ellipsis) →
  price → optional swatches. Whole card clickable. "Sold out" badge when unavailable.
- **Nav/header:** sticky, slim (64–72px), logo left, cart/search/account icons right (line icons,
  22px, currentColor). Clear active state. Mobile: hamburger drawer, ≥44px tap targets.
- **Forms/inputs:** labels above, 44px height, visible focus, inline validation + clear errors.
- **Drawers/modals:** overlay dim, slide/scale in ~200ms, focus-trapped, Esc + click-outside close.

## 3. Motion (tasteful, fast, never janky)
- Durations 150–300ms; ease-out for enter, ease-in for exit. Respect `prefers-reduced-motion`.
- Hero crossfade, card hover-zoom + rise-in, smooth transitions. NO layout shift (reserve image
  dimensions). Nothing bounces/flashes. Effects must not hurt mobile performance.

## 4. E-commerce / conversion patterns
- Above-the-fold value prop + primary CTA. Trust bar (free shipping / returns / secure).
- Product page: gallery (multi-image) + title + price + variant selectors + add-to-cart above the
  fold on mobile; scannable bullets; reviews/social proof; sticky add-to-cart on mobile.
- Clear, short path to checkout; minimal friction; real policies + contact in footer.

## 5. Quality bar (reject if any fail)
- Consistent spacing/type/color (from the scales) — no random values, no misalignment.
- Real hierarchy (eye lands on one primary thing per view). Generous whitespace.
- Responsive at 375 / 768 / 1280: no overflow/cut-off; touch targets ≥44px.
- Accessible: alt text, focus states, contrast, semantic HTML, keyboard nav.
- Every interactive element has all its states. Nothing looks "off" or unfinished.

**Method:** design mobile-first → build with tokens from theme.config.json → run the ui-ux-pro skill +
docs/QA.md → fix until it clears this bar → deploy (docs/CI_CD.md) → report to Slack.

## 6. Authoritative references (industry-standard — build to these)
These are the best-known UX sources; the rules above distill them. When unsure, follow them.
- **Refactoring UI** (Wathan & Schoger) — the practical playbook this skill is based on:
  start with too much whitespace then remove; limit choices; establish hierarchy with size/weight/
  color not just position; use a defined spacing + type + color scale; make one thing the emphasis;
  soften large text, don't use pure black; add depth with layered shadows.
- **Baymard Institute** — e-commerce UX research (product listing, product page, cart, checkout).
  Key: clear product images + variants, prominent price + add-to-cart, trust signals, short checkout,
  no forced account, visible shipping/returns. This is the gold standard for store conversion UX.
- **Nielsen Norman Group (NN/g)** — 10 usability heuristics: visibility of system status, match to
  the real world, user control (undo/back), consistency, error prevention, recognition over recall,
  flexibility, minimalist design, help users recover from errors, help/docs.
- **Shopify Polaris** — Shopify's own design system: content/voice, component patterns, accessibility.
- **WCAG 2.1 AA** — accessibility (contrast, focus, keyboard, alt text, semantics).

**How Sol should use this:** before building, restate the relevant rules for the task; after building,
grade the result against §1–§5 and these sources, list what fails, fix, then ship.
