<!-- Level 11 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 8, 9. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 8. DESIGN SYSTEM / TOKENS

Follow the same premium-DTC structural conventions already standard for
Itzik's builds (CSS custom properties, clamped typography, sharp-ish
buttons, sticky header) — but the PALETTE must be chosen deliberately per
8.A, not defaulted to a muted neutral scheme. The v1.0 reference build
("Nimbly / CloudNest Wrap," dusty-rose-on-cream) was rejected as boring
precisely because it treated color as decoration instead of as a
conversion tool — don't repeat that.

## 8.A — Color must be bold and eye-catching, not muted-safe by default

A soft/pastel/earth-tone "premium minimalist" palette is the WRONG
default for an impulse-buy trending product — it reads as boring and
doesn't push a buying decision. Before picking `--color-accent`:

1. **Consult the `ui-ux-pro` skill's color-palette database** (161
   palettes) — query it for the product's niche/style and pick one
   flagged for e-commerce/landing-page conversion energy, not a generic
   "minimal" or "corporate" pick.
2. **Default to a bold, highly saturated accent** — think saturated
   coral, red, orange, electric blue, hot pink, or a similarly energetic
   hue — unless the product's own category genuinely calls for restraint
   (e.g. fine jewelry, luxury skincare). Trending impulse categories
   (toys, gadgets, seasonal novelty, pet gear, gift items) should feel
   energetic, not tasteful-and-quiet.
3. **Pop test**: if you can imagine the primary CTA button blending into
   the page, the accent is too muted — start over. Meet WCAG AA contrast
   (4.5:1 text, 3:1 for large UI) AND make the CTA the single brightest,
   boldest element on the page, not just a compliant one.

**v1.32 — alphaforbaby's current accent (bronze `#b68235` on white) has
been flagged repeatedly as failing this pop test against littlesnugg's
own bold pink.** Itzik's call: pick a genuinely bold/saturated accent
per the rule above (doesn't have to copy littlesnugg's exact pink — any
color that actually passes the pop test is fine), not the current
bronze. This was a real, repeatedly-raised blocker with no answer;
treat this as the go-ahead to change it rather than re-asking each
build.
4. **Repeat the accent on purpose**: the countdown timer, the "SAVE X%"
   badge, star-rating fill, and the Add-to-Cart button should all pull
   from the same bold accent, so the eye keeps landing on the same "buy
   now" signal as it scrolls — color repetition is doing real work here,
   not just branding.
5. **Don't go all-neutral.** Reference stores use color throughout
   (badge fills, rating stars, section background tints, sale
   typography) — not cream/gray/beige everywhere with the accent
   confined to one button.

Boring is a real failure mode here, not a subjective nitpick: a page
that doesn't visually grab attention in the first second fails the "best
product a person can buy" impression even if every section below is
present and correct.

## 8.B — Tokens

```css
:root {
  --color-bg: #ffffff;
  --color-bg-soft: /* a light tint of --color-accent, not a generic beige */;
  --color-text: #1a1a1a;
  --color-text-muted: #6b6b6b;
  --color-accent: /* bold, saturated — chosen per 8.A, not muted */;
  --color-accent-contrast-text: #ffffff;
  --color-success: #1f8a4c;      /* for "SAVE %" / in-stock */
  --color-sale-strike: #9a9a9a;

  --radius-button: 4px;          /* sharp-ish, not fully rounded pill */
  --radius-card: 8px;

  --font-heading: system sans-serif stack or one licensed webfont, weight 700;
  --font-body: system sans-serif stack, weight 400-500;
  --step-h1: clamp(1.75rem, 1.4rem + 1.5vw, 2.75rem);
  --step-h2: clamp(1.35rem, 1.15rem + 1vw, 2rem);
  --step-body: clamp(0.95rem, 0.9rem + 0.2vw, 1.05rem);

  --space-section: clamp(2.5rem, 4vw, 5rem);
  --touch-target-min: 44px;
}
```

Buttons: sharp-ish corners (4px, not full pill), high-contrast bold fill
in `--color-accent`, a hover animation with actual presence (`transform:
scale(1.03-1.05)` + a visible shadow/glow lift — bigger than a subtle
1.02, per 8.A.3), minimum 44px height for tap targets. Header becomes
sticky on scroll with a compressed height variant.

## 8.C — Background and motion effects (concrete, not vague "make it pop")

A page that's structurally complete but visually flat is still a
failure (see 8.A) — these are the specific, checkable effects that
close that gap, each tied to something actually confirmed on a
reference store rather than a generic suggestion:

1. **Gallery/slider arrows in `--color-accent`**, filled circle or
   outlined, not neutral black/gray (Section 5, item 3) — a deliberate
   deviation from the reference set (their arrows are neutral),
   done because a colored arrow both matches the brand and draws the
   eye toward "there's more to see here."
2. **SVG wave/curve section dividers** between at least two adjacent
   section backgrounds (confirmed on starnestshop, Section 5 item 19 as
   of v1.30, was item 14)
   instead of a hard flat edge everywhere. A single inline `<svg>` with
   a `viewBox` and one curved `<path>`, colored to bridge the two
   section backgrounds, negative-margined to overlap the seam — cheap,
   no video/animation library needed.
3. **Soft blurred color-blob or gradient shapes** behind the hero and
   at 1-2 other section backgrounds — large, low-opacity, blurred
   circles/blobs in `--color-accent` or a tint of it, `position:
   absolute`, `filter: blur(...)`, sitting behind the real content.
   Optional: a slow drift/float animation (translate a few px over
   6-10s, ease-in-out, infinite) for a subtle sense of motion without
   being distracting.
4. **Hero background video** (Section 7.B, Slot 1) is itself a
   background effect, not just a content asset — treat the two
   (blob/gradient shapes elsewhere, video specifically behind the hero)
   as the same category of work: the page should never feel like it's
   sitting on a flat, static white background for more than one section
   in a row.
5. **Button hover** — restated here so it isn't missed while focused on
   backgrounds: `transform: scale(1.03-1.05)` plus a visible shadow/glow
   lift on every primary and secondary CTA, not just the main
   Add-to-Cart button (8.B already specifies this; the miss to avoid is
   applying it to one button and forgetting the rest — bundle-tier
   selectors, the sticky-bar Add-to-Cart, and the secondary CTA in
   Section 5 item 16 as of v1.30 (was item 11) all need the same hover
   treatment).

---

# 9. RESPONSIVE / MOBILE REQUIREMENTS (mandatory, not optional)

Design mobile-first; desktop is the expanded layout, not the other way
around — most traffic and the majority of the 5 reference stores' own
layouts are mobile-optimized first.

- Breakpoints to explicitly design and test at: 375px (small phone),
  414px (large phone), 768px (tablet), 1024px, 1440px+ (desktop).
- Gallery: horizontal swipeable carousel on mobile (not a grid); becomes
  thumbnail-strip + main image on desktop.
- Buy box: stacks directly under the gallery on mobile, sits beside it
  on desktop (≥1024px).
- **Sticky mobile add-to-cart bar**: appears once the user scrolls past
  the main buy box; shows product thumbnail + price + one-tap Add to
  Cart button; must not overlap page content or platform UI; disappears
  when the main buy box is back in view or at checkout.
- All tap targets ≥44x44px, spaced to avoid mis-taps.
- Images use responsive `srcset`/lazy-loading; hero image/video loads
  eagerly, everything below the fold lazy-loads.
- Typography uses `clamp()` fluid sizing (Section 8 tokens) — no fixed
  px headings that overflow small screens.
- FAQ and benefit sections collapse to single-column stacks on mobile;
  never force horizontal scroll on body content.
- Test checklist before shipping: page loads and is fully usable at
  375px width with no horizontal scrollbar, no overlapping text, no
  buttons cut off, sticky elements don't obscure the CTA.
