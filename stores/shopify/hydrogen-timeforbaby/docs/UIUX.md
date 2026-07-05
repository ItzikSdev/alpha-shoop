# UI/UX Rules — how the store must look and behave

Sol enforces these on every store. The whole look is driven by `app/theme.config.json`.

## Product image ↔ store background (HARD rule)
The product image background must **match** the store background:
- **If the store/page background IS white** → use product photos with a **white background**
  (clean studio-white fits and looks native).
- **If the store/page background is NOT white** (e.g. soft `#f6f4f1`, dark, colored) → **do NOT**
  use white-background product photos — they look pasted/cut-out. Use lifestyle/styled shots or
  photos whose background matches the store, so nothing looks "off".

Check the store's `tokens.colors` (soft/white/ink) and the card/background where the image sits,
then pick product images accordingly.

## Image quality (also see SEO.md)
- Clean, sellable, styled/lifestyle shots. Reject: plain white-studio-only when the bg isn't white,
  visible text/watermark/foreign language, collages, low quality.
- Uniform product-card ratio across the grid (e.g. 4:5, `object-fit: cover`) so the grid is even.

## Typography & layout
- Consistent type scale from `theme.config.json → tokens.fontSizes` (no oversized/undersized text).
- Consistent spacing/margins; sections aligned; nothing overlapping or cramped.
- Contrast is accessible (text readable over images — use the gradient overlays).

## Functions to verify
- Header icons (search/account/cart) work; cart badge counts; mobile menu opens.
- Cart page = line items + subtotal + checkout; add-to-cart works.
- Product page: gallery + Color/Size selectors; sold-out disabled; image swaps on color.

## Effects (present but tasteful, never janky)
- Hero carousel crossfades on a timer + dot click; smooth, no flicker.
- Product cards: hover zoom + rise-in; category tiles: hover zoom.
- Transitions are smooth; no layout shift; effects don't hurt performance or mobile.
- On mobile, heavy effects degrade gracefully (no jank, no horizontal scroll).

## Shopify e-commerce UX best practices (build + check against these)
Conversion- and trust-focused rules Sol builds to and QAs every store against:

**Buttons & CTAs**
- One clear primary CTA per view ("Add to cart" / "Shop the collection") — high contrast, obvious.
- Buttons look clickable (solid fill, adequate padding ≥44px tap target), have hover + active +
  disabled + loading states. "Add to cart" shows feedback; "Sold out" is disabled, not hidden.
- No dead buttons/links; every control does something.

**Product page (highest-value page)**
- Above the fold on mobile: image + title + price + variant selectors + Add-to-cart (not pushed
  below the browser bar). Gallery with multiple real photos; image swaps on variant.
- Price clear; compare-at + % off if discounted. Trust badges (free shipping / returns / secure).
- Concise scannable description (bullets for material/fit/care) — not a wall of text.

**Trust & conversion**
- Visible: free-shipping threshold, returns policy, secure-checkout signal, real reviews/social proof.
- Announcement bar for shipping/returns. Clear, low-friction path to checkout.
- Real contact + policies in footer; nothing that looks like a "ghost store".

**Forms & checkout**
- Minimal fields, clear labels, inline validation, visible errors. Cart → checkout in one tap.
- Checkout must actually work (payment provider enabled) — see QA.md.

**Navigation & IA**
- Simple, predictable nav (the 3 collections). Search reachable. Breadcrumbs on deep pages.
- Logo → home. No dead ends; every page has a next step.

**Visual system**
- Consistent color/type/spacing scale (from theme.config.json). Generous whitespace. Aligned grids.
- Uniform product-card ratio. Accessible contrast (WCAG AA). Readable line-length + size.

**Performance & mobile (mobile is most traffic)**
- Fast LCP: sized/lazy images, no layout shift. Test 375/768/1280 — no horizontal scroll.
- Sticky add-to-cart on mobile product pages is a plus. Effects degrade gracefully on mobile.

**Rule of thumb:** if anything looks "off", it does not ship. Sweat every visual detail.
