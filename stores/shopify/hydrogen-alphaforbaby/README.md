# ALPHA FOR BABY — Hydrogen storefront

A **Shopify Hydrogen** (React / React-Router 7, deployed on **Oxygen**) headless storefront
for the ALPHA FOR BABY store (`kgg8n0-k0.myshopify.com` → alphaforbaby.alpha-tech.live).
Reads the **Storefront GraphQL API**, so every product/variant the CJ pipeline pushes to
Shopify renders automatically — no code change.

## 🎨 This is a TEMPLATE — reskin / clone by editing ONE JSON file
All the look + content lives in **[`app/theme.config.json`](app/theme.config.json)**:
brand name & logo text, colors, **font sizes**, nav links, announcement bar, hero
(eyebrow/headline/sub/CTA/images/stats), trust pills, category tiles, testimonials, footer,
product-page trust badges. Edit that file and the whole store changes — **no component code**.

- Colors + font sizes become CSS variables (`--tob-*`) injected into `<head>` (see
  `app/lib/theme.js` + `app/root.jsx`); `app/styles/app.css` consumes them.
- To **clone into a new store**: copy this folder to `stores/shopify/hydrogen-<newbrand>/`,
  edit `theme.config.json` (brand, colors, hero, tiles, testimonials) + `.env`
  (`PUBLIC_STORE_DOMAIN` + that store's Storefront token), add a workflow with the new paths.
  Products/collections come live from that store's Storefront API — nothing hardcoded.

The structure was ported from the store template
(`../alphaforbaby.alpha-tech.live/style/site.json` + `product.json`). Font sizes use a normal
premium type scale (tune them in `theme.config.json → tokens.fontSizes`).

## What's built
- **Homepage** (`app/routes/_index.jsx`): dark marquee → editorial split hero (auto carousel) →
  trust pills → category tiles (Baby Boys / Baby Girls / Unisex) → **live product grid** →
  testimonials → dark footer.
- **Collections** (`collections.$handle.jsx`, `/collections/all`): real products, paginated.
- **Product** (`products.$handle.jsx`): gallery, Size/Color selectors, **sold-out variants
  disabled**, add-to-cart, trust badges, real CJ description.
- **Cart / search / account**: Hydrogen defaults, restyled.
- Nav is hardcoded to the owner rule (Baby Boys / Baby Girls / Unisex) — no dependency on
  Shopify online-store menus.

## Legal / compliance pages
**Policies come from Shopify (single source of truth).** Privacy, Refund and Shipping policies
are pulled LIVE from Shopify (admin → Settings → Legal) via `routes/policies.$handle.jsx` at
`/policies/privacy-policy`, `/policies/refund-policy`, `/policies/shipping-policy` — edit them in
Shopify admin, no code. Shopify's built-in **cookie/consent banner** (GDPR/CCPA) is enabled
(`root.jsx → consent.withPrivacyBanner: true`) and the footer has the CCPA **"Do Not Sell or
Share My Personal Information"** control.

Two pages Shopify does **not** generate are kept as JSON-driven template pages
([`app/lib/legal.js`](app/lib/legal.js) → [`PolicyDoc`](app/components/PolicyDoc.jsx)):
`/pages/accessibility` and `/pages/contact`, filled from `theme.config.json → legal`.

> ⚠️ **Not legal advice.** Before going live: (1) in Shopify admin **Settings → Legal**, click
> **"Create from template"** for **Terms of Service** (the store has Privacy/Refund/Shipping but
> no Terms yet), then re-add its link to `theme.config.json → legalLinks`. (2) Fill the real
> business details in `theme.config.json → legal` (`legalEntityName`, `companyNumber`,
> `businessAddress`, accessibility `coordinatorName`/`coordinatorPhone`) — empty fields render as
> `[TODO: …]`; **never use a fake address** (Google/Meta/Stripe ban for misrepresentation).
> (3) Set consent-banner regions in **admin → Settings → Customer privacy**. (4) Lawyer review.

## Local development
```bash
cd stores/shopify/hydrogen-alphaforbaby
nvm use            # Node 22 (see .nvmrc) — Hydrogen supports ^22 || ^24, NOT 25
npm install
cp .env.example .env   # already has the public storefront token wired
npm run dev            # → http://localhost:3000
```
> The `.env` here is git-ignored. The `PUBLIC_STOREFRONT_API_TOKEN` is a **public,
> read-only** Storefront token (safe to ship to the browser) minted via the Admin API
> `storefrontAccessTokenCreate`. Rotate/replace it with the token from the Headless channel
> once that's installed (below).

## Production build
```bash
npm run build && npm run preview
```

## CI/CD → Oxygen (LOCAL builds — no GitHub Actions)
This app is a **multi-store template**. Each store is a profile under `store-profiles/<slug>/`:
- `theme.config.json` — that store's brand/design/products (committed)
- `store.env` — that store's domain + Storefront token + **Oxygen deploy token** (git-ignored)

**Build + deploy happen on this machine** (not in GitHub Actions):
```bash
nvm use 22
./scripts/new-store.sh <slug>     # clone a NEW store profile from the template
#   → edit store-profiles/<slug>/theme.config.json + store.env
./scripts/deploy.sh <slug>        # local: activate profile → npm build → shopify hydrogen deploy
./scripts/deploy.sh <slug> --preview   # deploy to a preview environment instead of production
```
`deploy.sh` copies the store's profile into `app/theme.config.json` + `.env`, builds locally, then
runs `shopify hydrogen deploy` with that store's deploy token — so one codebase deploys many stores.

### Per-store one-time setup (Shopify admin, owner)
1. **Install the “Hydrogen”/“Headless” sales channel** for the store → gives Oxygen hosting +
   the **deploy token** + a production Storefront token. Put the deploy token in that store's
   `store-profiles/<slug>/store.env` as `SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN`.
2. **Publish products to that channel** (make it default) — #1 cause of “products don’t show up”.
3. Set the store's `PUBLIC_STORE_DOMAIN` + `PUBLIC_STOREFRONT_API_TOKEN` in `store.env`.
4. Point the store's domain at its Oxygen storefront.

See the full architecture guide: [`../CJ_AGENT_HYDROGEN_AUTOMATION_GUIDE.md`](../CJ_AGENT_HYDROGEN_AUTOMATION_GUIDE.md).

## Notes for maintainers
- **`~/*` alias:** resolved via an explicit `resolve.alias` in `vite.config.js` (tsconfigPaths
  alone didn’t pick up `jsconfig.json` here). Asset `?url` imports in `app/root.jsx` use relative
  paths for the same reason.
- Restyle by editing `app/styles/app.css` (mirrors `site.json`’s `css`) — keep the font floor.
- `/account` (Customer Account API) needs extra setup (public dev domain + channel) — optional.
