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

**Rule of thumb:** if anything looks "off", it does not ship. Sweat every visual detail.
