<!-- Level 12 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 10. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 10. TECHNICAL IMPLEMENTATION NOTES

**Corrected in v1.10 — this section previously said "Shopify Dawn/Liquid
theme sections," which does NOT match what's actually being built.**
Checked directly against the repo (`stores/shopify/`, 2026-09-06): every
recent one-off store (`react-furlo`, `react-aurelo`, `react-lullabyloom`,
`react-lumora`) is a plain **React 19 + Vite + Tailwind v4** app, built
from a real, existing starter — `stores/shopify/react-store-template`
— not a Shopify Liquid theme. (`hydrogen-alphaforbaby` is the one
Hydrogen/Shopify-integrated exception — alphaforbaby specifically, not
the pattern for new trending-product stores.) Build from
`react-store-template`, not from scratch and not as a Liquid theme:

- **It's config-driven, exactly like Section 5 wants.** The whole page
  renders from one typed object (`src/config/types.ts`'s
  `ProductConfig`, filled in per-store in `src/config/demoProduct.ts` or
  a copy of it) — every Section 5 blueprint item already has a matching
  component in `src/components/`: `Gallery`, `BuyBox` (includes the
  bundle-tier block), `BenefitBullets`, `WhyItWorks`, `LifestyleBlock`,
  `ComparisonBlock`, `ReviewsSection`, `GuaranteeBlock`, `FaqAccordion`,
  `SecondaryCta`, `StickyMobileBar`, `Footer`, `AnnouncementBar`,
  `CountdownTimer`. Launching a new store means writing a new config
  object with real content, not writing new components — per the
  template's own README: "No component needs to change for a new
  product. If a new page section is genuinely needed, add it once here
  and every future store gets it too." If you find yourself hand-rolling
  a bundle block or a review card in a one-off build instead of filling
  in the existing component's config shape, stop — you're duplicating
  something that already exists and won't benefit the next store.
- **The background-effect, support-widget, and bundle-tier components
  already exist too** (added in v1.10; confirmed with real Playwright
  screenshots in v1.12 — hero, bundle block, wave divider/lifestyle
  area, reviews, and the Nora widget opened, all rendering correctly).
  That same visual check caught a real bug a type-check couldn't: the
  "Most Popular"/"Best Deal!" badges were clipped invisible by the tier
  card's `overflow-hidden` — fixed in `BuyBox.tsx` (Section 7.D should
  get this as bug #4 on the next pass). Still do your own `npm run dev`
  look on any NEW config/content you add — a visual check is cheap
  insurance against exactly this class of CSS-clipping bug, and it's
  now proven to catch real ones, not just theoretical ones. Use these
  components instead of inventing new ones or describing effects only in
  prose:
  - `BackgroundEffects.tsx` exports `GradientBlobs` (soft blurred color
    blobs, zero dependency) and `WaveDivider` (SVG curve between two
    section backgrounds) — both already wired into `App.tsx` at the
    lifestyle block and around the reviews section. This is what
    Section 8.C's "background effects" should resolve to in code, not
    a from-scratch npm library search.
  - `SupportWidget.tsx` renders the Nora 24/7 bubble from
    `ProductConfig.support` (`agentName`, `email`, `badge`) — already
    wired into `App.tsx`. `demoProduct.ts`'s sample value uses a
    `.example` placeholder email on purpose; every real store config
    must either carry the real support inbox Itzik provides or keep
    that placeholder and flag it as an open gap (7.E) — the widget
    itself detects and displays a placeholder warning automatically.
  - `Gallery.tsx` now has hover-revealed prev/next arrows in
    `--accent`, and `BuyBox.tsx`'s bundle block (`QuantityDiscount` with
    `badge`/`price`/`compareAt`/`addOns`) renders the confirmed
    starnestshop shape — named tier badges, nested add-on checkboxes —
    instead of the old plain 3-button grid. Note: add-on totals aren't
    yet wired into the actual cart/checkout total (`CartContext.tsx`) —
    that's a real follow-up, don't claim the add-ons affect the charged
    price until that plumbing exists.
  - `ProductConfig.heroVideo` (`{ src, poster? }`) renders Section 7.B
    Slot 1 as a full-bleed autoplay/muted/looping background behind the
    hero headline, matching the confirmed beelyra.com pattern — already
    wired into `App.tsx`.
  - `Review.photo` and `Review.variantPurchased` (optional fields) let
    `ReviewsSection.tsx` render a real customer photo and "✓ Verified
    buyer" per Section 5 item 14's confirmed shape (was item 8 pre-v1.30)
   — falls back to an
    initials avatar when no photo is given.
- This template is a standalone React SPA, not a Shopify theme — reviews,
  countdown, and bundle data all come straight from real values you put
  into `ProductConfig` (Section 7.C's honesty states map directly onto
  `ReviewsConfig.state`/`UrgencyConfig.mode` in `types.ts`), not from
  installing a Shopify app into a theme. Checkout itself is the one
  piece genuinely not wired yet (`CartContext.tsx`'s add-to-cart is
  local UI state only) — per the template's own README, connect it via
  either the **Shopify Storefront API** (create/update a cart by
  GraphQL, redirect to `checkoutUrl` — the pattern already used in
  `hydrogen-alphaforbaby`) or the lighter-weight **Shopify Buy Button
  SDK**. Do this before calling a store launch-ready; a store that looks
  complete but can't actually take an order isn't done.
- If the product was sourced via Section 2, connect it + set the
  shipping method in the CJ panel once the Shopify product/checkout
  side is live, same as catalog sourcing (`product-sourcing.md` §1/§6).
- Legal/footer pages (Refund Policy, Shipping Policy, Privacy Policy,
  Terms of Service — `ProductConfig.policyLinks`) must point to real,
  accurate policy content matching what the brief's `shipping_reality`
  and guarantee terms actually promise — never boilerplate that
  contradicts the page copy.
