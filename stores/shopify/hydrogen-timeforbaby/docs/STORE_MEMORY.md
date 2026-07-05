# Store memory — Sol's persistent knowledge of THIS store (read once, update after changes)

Sol: this is your memory of the store. It's injected into your prompt so you DON'T re-read
everything each time. After you change something, APPEND a short line under "Recent changes".

## Map (where things are)
- **`app/theme.config.json`** — drives the WHOLE look + content (brand, logo, favicons, colors,
  font sizes, nav, announcement, hero+images, tiles, pills, testimonials, legal, legalLinks).
  Change the store by editing THIS first. Colors/sizes → CSS vars injected in `app/root.jsx`.
- **`app/styles/app.css`** — all styles (`.tob*` classes). Large file — use edit_store_file (surgical).
- **`app/components/`** — Header.jsx (logo + hamburger + cart/search icons; nav is hamburger-only),
  Footer.jsx (Shop + Support + Legal links), PageLayout.jsx (marquee + header + main + footer + mobile drawer),
  ProductItem.jsx (product card), ProductForm.jsx (variant selectors + add-to-cart).
- **`app/routes/`** — `_index.jsx` (home: hero carousel, pills, tiles, product grid, testimonials),
  `products.$handle.jsx`, `collections.$handle.jsx`, `cart.jsx` (full page), `search.jsx`,
  `policies.$handle.jsx` (Privacy/Refund/Shipping/Terms pulled LIVE from Shopify),
  `pages.accessibility.jsx` + `pages.contact.jsx` (from `app/lib/legal.js`).
- **`public/images/`** — hero-1..5.jpg + tile-{baby-boys,baby-girls,unisex}.jpg (LOCAL, CSP-safe).
- **`store-profiles/timeforbaby/`** — `theme.config.json` + `store.env` (deploy token). Deploy = `./scripts/deploy.sh timeforbaby`.

## How it works
- Products + collections come LIVE from the Shopify Storefront API (nothing hardcoded).
- Policies come LIVE from Shopify. Checkout → Shopify (needs a payment provider enabled).
- Nav links live ONLY in the hamburger drawer (Header.jsx → PageLayout MobileMenuAside).
- ENGLISH-ONLY storefront. Production deploy = `./scripts/deploy.sh timeforbaby` (--env-branch main).

## Recent changes (append newest on top — one line each)
- 2026-07-05 — Fixed cart DRAWER desktop layout (app.css): the ≥820px `@media (min-width:820px)` block (cart PAGE 2-col grid) was leaking onto the drawer's `.cart-details`, putting line items + summary side-by-side/overlapping with Checkout cut off. Added drawer-scoped overrides INSIDE that media query (`.tob .overlay[data-type="cart"] aside{width:400px;max-width:92vw}` + force `.cart-details` back to single-column flex, summary full-width). Also added a base `.cart-summary-aside` block: stacked summary, Subtotal as space-between row, discount/gift inputs on one line, full-width 52px dark Continue-to-Checkout CTA (hover/focus ring), `br` hidden. Matches mobile. Build passed, deployed.
- 2026-07-05 — Added express "Buy it now" button on product page (ProductForm.jsx) under Add-to-cart: uses AddToCartButton with redirectTo="checkout" sentinel; cart.jsx action converts "checkout" → cartResult.checkoutUrl (303) so shopper lands straight on Shopify checkout (PayPal/dynamic buttons show there once enabled in Settings→Payments). AddToCartButton now accepts className. Styled .tob-buynow (outline→fill hover, 52px min, focus ring) per ui-ux-pro. Build passed, deployed.
- 2026-07-05 — Cart drawer CSS fix (app.css): added missing `.sr-only` util (hides "Line items" label); added full `.tob .cart-*` block (Subtotal now a flex space-between row so the AMOUNT shows on the right; line items with 76px thumbs, qty/remove controls, primary checkout CTA, drawer flex-column so summary pins to bottom; cart PAGE gets 2-col grid ≥820px). Build passed, deployed.
- 2026-07-05 — Fixed collection categorization: moved 3 from Baby Boys (Fishing Print, Classic Crew Neck, Cozy Autumn Layered — all described as "unisex") + 2 from Baby Girls (Cotton Baby Essentials Set, Cozy Split-Leg Sleepsuit — gender-neutral prints) into Unisex via collectionAdd/RemoveProducts.
- 2026-07-05 — nav moved to hamburger-only (Header.jsx, PageLayout.jsx, app.css); local hero/tile images.
- 2026-07-05 — Desktop nav restored (DesktopNav in Header.jsx, CSS ≥820px); hamburger hidden on desktop, shown on mobile; product image CSS fixed (.tob .product-image + .tobp grid); deployed.
- 2026-07-05 — Bug fix: added productPage.trustBadges to theme.config.json (was missing → runtime crash on product page); fixed hero secondaryLink /pages/about-us → /collections/all (was 404); deployed.
