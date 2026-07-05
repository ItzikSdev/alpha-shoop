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
- 2026-07-05 — nav moved to hamburger-only (Header.jsx, PageLayout.jsx, app.css); local hero/tile images.
- 2026-07-05 — Desktop nav restored (DesktopNav in Header.jsx, CSS ≥820px); hamburger hidden on desktop, shown on mobile; product image CSS fixed (.tob .product-image + .tobp grid); deployed.
