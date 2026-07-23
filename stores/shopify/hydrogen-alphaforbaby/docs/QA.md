# QA Checklist — test the whole store like a QA engineer

Run after any change (and fully for a new store). Test **desktop AND mobile**. Fix every ✗.

## 1. Links (nothing broken, nothing wrong)
- [ ] Every nav link resolves (200), goes to the RIGHT place: Baby Boys / Baby Girls / Unisex.
- [ ] Every footer link resolves — and the footer contains **only appropriate links**
      (Shop = the 3 collections; Legal = Shipping/Refund/Privacy/Terms/Accessibility/Contact;
      Support email). **No stray/irrelevant links** (no "Do Not Sell", no social lists unless real).
- [ ] Policy links (`/policies/*`) + `/pages/accessibility` + `/pages/contact` all load.
- [ ] Product cards, category tiles, hero CTA, logo → all link correctly (no 404).
- [ ] `/collections/all`, `/search`, `/cart`, `/account` load without error.

## 2. Store text (appropriate + correct)
- [ ] All storefront text is **English** (no Hebrew anywhere on the store).
- [ ] Footer/nav/labels are relevant to the store; no leftover template or placeholder text.
- [ ] No `[TODO]`, no lorem ipsum, no owner personal details anywhere public.
- [ ] Announcement bar / trust pills / testimonials read correctly.

## 3. Product ↔ collection correctness (right item in the right place)
- [ ] Each product appears **only in the collection it belongs to**: a baby-**girl** garment must
      NOT appear under Baby Boys, and vice-versa; unisex only under Unisex.
- [ ] Product title/handle matches the item (garment type + audience correct).
- [ ] Variant options (Color/Size) match the product; unavailable options are disabled/sold-out.

## 4. Mobile / responsive
- [ ] Test at ~375px and ~820px: no horizontal scroll, nothing overlaps or is cut off.
- [ ] Hero, tiles, product grid, product page, cart all reflow cleanly on mobile.
- [ ] Tap targets (nav icons, buttons, swatches) are usable; text is readable (not tiny/huge).

## 5. Functions (the store actually works)
- [ ] Add-to-cart adds the item; cart shows line items + subtotal.
- [ ] **Checkout reaches Shopify checkout** (not a redirect back to home). If it bounces to home →
      a payment provider is not enabled (Settings → Payments) — flag it; it's not a code bug.
- [ ] Search returns results; account/login link works (or is intentionally disabled).
- [ ] Images load (hero carousel + tiles are `<img>`/local files, CSP-safe — not external URLs).

**Report:** list each ✗ with the page + what's wrong, fix, re-run.

## 6. Product media (required)
- [ ] **Minimum 2 images per product** — a 1-image product is not acceptable.
- [ ] Images within a product are **NOT similar/duplicate** (dedupe by content, not filename).
- [ ] **No product appears twice** in the store (no duplicate listing — same title or same main image).
- [ ] Product is in the RIGHT collection (e.g. a pink bow romper must NOT be under Baby Boys).
