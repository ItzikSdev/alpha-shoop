# CJ Dropshipping × Shopify (Headless / Hydrogen) — Hands‑Free Automation Guide

> **Goal:** architect the store so a **dedicated CJ Agent** can source products, keep
> inventory in sync, and fulfil orders **completely hands‑free**, while a **Shopify
> Hydrogen** storefront (React/Remix + Storefront GraphQL API) renders every new
> product and variant **without a single manual code change**.
>
> **Stack this guide assumes**
> - **Backend / commerce engine:** Shopify (Admin API is the source of truth for products, inventory, orders).
> - **Frontend:** Shopify **Hydrogen** (Remix) deployed on **Oxygen**, reading the **Storefront GraphQL API**.
> - **Supplier:** **CJ Dropshipping**, operated by a **dedicated CJ Agent** (a human account manager) + the **CJdropshipping Shopify app** (the automation engine).
>
> **Mental model — three planes, one contract:**
> ```
>  CJ (supply)  ──push products / sync stock / push tracking──▶  SHOPIFY (system of record)
>                                                                     │
>                                                     Storefront GraphQL API (read‑only)
>                                                                     ▼
>                                                          HYDROGEN (Oxygen) storefront
> ```
> Shopify is the contract in the middle. The CJ side only ever **writes** to Shopify;
> the Hydrogen side only ever **reads** from Shopify. Get that boundary right and the
> whole thing runs itself.

---

## 0. Current state vs. target (read this first)

| | You have today | This guide moves you to |
|---|---|---|
| Storefront | Shopify **Liquid theme** (Online Store 2.0), rendered from JSON specs and pushed via the Python pipeline | **Hydrogen** headless app on **Oxygen**, reading the Storefront API |
| CJ link | CJdropshipping app installed (auto tracking) | Full auto: sourcing → stock sync → **auto‑pay wallet** → auto‑fulfil |
| Agent | Pipeline agents (Hunter/Devon) push products | A scoped **CJ Agent staff account** + app OAuth, least privilege |

> **Migration note:** going headless means the Liquid theme stops being the customer‑facing
> site — Hydrogen replaces it. Shopify Admin (products/orders/inventory) stays exactly the
> same, so **the entire CJ automation below is identical whether you stay on Liquid or move
> to Hydrogen.** Only Section 3 (the frontend) changes. Do Sections 1–2 first; they pay off
> immediately regardless of frontend.

---

## 1. Backend Integration — CJ ↔ Shopify (the automation engine)

Everything hands‑free lives in the **CJdropshipping app + CJ dashboard settings**. The app
holds an OAuth grant against your Shopify store and does all the writing.

### 1.1 Connect CJ to the Shopify backend
1. **Shopify Admin → Apps → Shopify App Store → install “CJdropshipping”.** During install,
   Shopify shows the OAuth scopes the app requests (products, orders, inventory, fulfilment,
   assigned fulfilment orders). Approve them — these scopes are what let CJ run unattended.
2. In the **CJ dashboard → Authorization / My Shopify** confirm the store shows **Authorized**.
   If you run multiple stores from one CJ account, make sure the **correct store** is the
   active binding.
3. **One‑time product connection:** each product must be **mapped** CJ SKU → Shopify variant.
   New products listed *through* CJ are auto‑mapped. Products created in Shopify by other means
   must be connected once in **CJ → My Products → Connect** (per‑variant SKU binding). This is
   the only routinely‑manual step, and it’s a per‑product one‑off.

### 1.2 Automatic order fulfilment
Goal: customer pays on your site → CJ receives the order → CJ ships → tracking flows back →
Shopify emails the customer. Zero clicks.

In **CJ dashboard → Settings → Orders (Auto‑fulfil / Order settings):**
- **Auto‑sync Shopify orders → ON.** CJ polls Shopify (via the fulfilment‑order scopes) and
  pulls paid orders automatically.
- **Auto‑place / auto‑create CJ order → ON.** Incoming Shopify orders become CJ orders without
  manual import.
- **Auto‑fulfil & write‑back tracking → ON.** When CJ ships, it writes the **tracking number +
  carrier** onto the Shopify **fulfilment**, which flips the order to *Fulfilled* and triggers
  Shopify’s shipping‑confirmation email to the customer.
- **Shipping method rule:** set a **default shipping method per destination** (e.g. CJ Packet /
  Global Registered) in CJ so the agent never has to pick one per order. (This is the other
  historically‑manual knob — set it once per store.)

> Result: an order placed at 3am is paid, sent to CJ, and queued for shipment before anyone
> logs in. The only thing standing between “paid” and “shipped” is the wallet (next).

### 1.3 Inventory sync (never oversell)
In **CJ dashboard → Settings → Inventory:**
- **Auto inventory sync → ON.** CJ periodically pushes each mapped SKU’s stock to the Shopify
  **inventory level** for your fulfilment location via the Admin API. Frequency is CJ‑side
  (typically several times a day) — treat it as *near*‑real‑time, not instant.
- **Out‑of‑stock behaviour:** decide **“set variant to 0 / continue selling = OFF”** so Shopify
  marks the variant unavailable when CJ hits zero. This is what makes `availableForSale` flip
  to `false` on the Storefront API, which is how Hydrogen greys out the option (Section 3.6).
- **Location:** make sure Shopify has **one fulfilment location** that CJ writes to, and that
  it’s the location your Storefront API / Hydrogen reads availability from.

### 1.4 Wallet payment automation (the money loop)
This is what makes fulfilment *truly* hands‑free — otherwise every order waits for a human to
click “Pay”.

In **CJ dashboard → Balance / Wallet:**
- **Top up the CJ Wallet** (bank/card/PayPal) to a working float.
- **Enable “Auto Pay” / “Balance auto‑deduct” for auto‑fulfilled orders → ON.** Now a synced
  Shopify order is **paid from wallet automatically**, CJ procures + ships, no approval step.
- **Set a low‑balance alert** (email/Slack) and, ideally, **auto‑recharge** if your CJ plan
  supports it. A drained wallet silently stalls every order — the alert is your safety net.
- **Reconciliation:** CJ wallet debits = your **COGS**. Export CJ wallet statements monthly and
  match against Shopify order revenue to watch margin. (Your repo already tracks retail vs cost
  in `product_mappings`; feed CJ wallet debits into the same ledger.)

### 1.5 Product sourcing → push to the Shopify backend
The agent’s day‑to‑day “source products” loop:
1. Agent finds a product in the **CJ catalog** (or via CJ’s sourcing request for a specific item).
2. Agent edits it in CJ (title, images, description, the variants to keep, retail price/markup
   rule) and clicks **“List to Store / Push to Shopify”.**
3. CJ creates the product in Shopify via the Admin API: product, **variants** (each bound to its
   CJ SKU), images, and inventory. From this moment Shopify is the source of truth.
4. **Pricing:** set CJ’s **auto‑pricing rule** (e.g. `cost × multiplier + $X`) so retail prices
   are populated on push — never leave a `$0` variant. Your store rules (min margin, vetting)
   apply here: the agent only lists items that clear them.

> After 1.5, the product exists in Shopify. Section 1.6 is the **one setting that decides whether
> Hydrogen can see it.**

### 1.6 Publish to the Headless sales channel  ⚠️ the make‑or‑break step
A Hydrogen storefront reads through a **Storefront API token that is scoped to a specific sales
channel** (the **“Headless”** channel, installed via Shopify’s *Headless* app — or the older
*Hydrogen* channel). **A product is invisible to Hydrogen until it is published to that channel.**

- In **Shopify Admin → Sales channels → Headless**, make it a **default channel** so new products
  are auto‑published to it, **or**
- Ensure the CJ push / a small automation sets the product’s **`publications`** to include the
  Headless channel (Admin API `publishablePublish`), **or**
- Add a **webhook‑driven step** (Section 3.4) that publishes any new product to Headless.

If “new products aren’t showing up on the Hydrogen site,” **99% of the time it’s this** — the
product is live on Shopify but not published to the Headless channel.

---

## 2. Agent Permissions — a secure Shopify staff account for the CJ Agent

Two distinct identities are involved. Don’t confuse them:

| Identity | What it is | How it authenticates |
|---|---|---|
| **CJdropshipping app** | The automation software | **OAuth** (scopes approved at install) — this already has API access; a human account does **not** grant the app anything |
| **CJ Agent (human)** | Your dedicated account manager | A **staff account** you create, for when *they* log into Shopify Admin to manage products/orders |

> The app does the automation. The staff account is only for the human agent’s manual work.
> Give it the **least privilege** that lets them push products and troubleshoot fulfilment —
> nothing more.

### 2.1 Staff account vs. Collaborator account
- **Collaborator account (preferred):** the agent requests access from their **Shopify Partner**
  account; you approve with **specific permissions** and it **doesn’t consume a staff seat**, and
  is easy to revoke. Use this if the agent has a Partner account.
- **Staff account:** you invite `agent@…` directly. Fine, but uses a seat and ties access to an
  email you must manage.

**Settings → Users and permissions → Add staff / Manage collaborator requests.**

### 2.2 Exact permissions to enable (least privilege)
Tick **only** these boxes:

| Permission | Why the agent needs it |
|---|---|
| **Products** | Create/edit products, variants, media, collections — the core “push products” job |
| **Orders** | View orders + **fulfil and ship orders**; investigate stuck fulfilments |
| **Draft orders** | (Optional) manual/replacement orders |
| **Manage inventory** | Adjust stock / fix a bad sync (part of Products) |
| **Apps and sales channels → *View only*** | See the CJ app status without being able to install/remove apps |

**Explicitly DO NOT grant:**
- ❌ **Settings** (store config, domains, checkout, payment providers)
- ❌ **Finances / payouts** (bank, payout data)
- ❌ **Customers** — grant **view‑only** *only* if fulfilment troubleshooting truly needs it;
  default to none. (Your owner rule: **never expose personal details** — this is the enforcement point.)
- ❌ **Manage/install apps**, **Manage themes/online store**, **Manage staff**, **Store owner transfer**
- ❌ **Discounts, Gift cards, Marketing** unless a specific task requires it

### 2.3 Security hardening (non‑negotiable)
- **Require 2FA** on the agent account (Settings → force two‑step for staff).
- **Least privilege + time‑boxed:** grant only what a current task needs; **revoke** when the
  engagement pauses. Collaborator access makes this one click.
- **Audit:** review **Settings → Users → last login / activity** periodically. Shopify logs staff
  actions — spot‑check product/price edits.
- **Never share the store‑owner login.** The agent gets *their own* scoped identity, always.
- **Rotate** the CJ app authorization if the agent relationship ends; re‑authorize fresh.

### 2.4 Prefer API tokens over human logins for automation
If *your own* automation (not CJ’s app) needs to write to Shopify, **do not reuse a human staff
login.** Create a **custom app** (Settings → Apps → Develop apps) with an **Admin API access
token** scoped to exactly `write_products, read_products, write_inventory, read_orders,
write_fulfillments`. Tokens are revocable, scoped, and auditable independently of people. (Your
repo already uses an Admin token per store — keep that pattern; keep it out of the browser.)

---

## 3. Hydrogen Frontend Workflow — products render with zero code changes

The headline: **a correctly‑built Hydrogen app never hardcodes products.** It renders
**dynamic routes** that query the Storefront API at request time, so any product/variant the
agent pushes appears automatically. You write the *templates* once; the *data* is always live.

### 3.1 Why new products appear without a deploy
Build routes by **handle**, not by hardcoded lists:
- `app/routes/products.$handle.tsx` → loader queries `product(handle: $handle)`
- `app/routes/collections.$handle.tsx` → loader queries `collection(handle: $handle) { products }`

```ts
// app/routes/products.$handle.tsx (Remix loader — runs on Oxygen, server‑side)
export async function loader({params, context}: LoaderFunctionArgs) {
  const {product} = await context.storefront.query(PRODUCT_QUERY, {
    variables: {handle: params.handle},
    cache: context.storefront.CacheShort(), // see 3.3
  });
  if (!product?.id) throw new Response('Not found', {status: 404});
  return json({product});
}
```
A product pushed by the CJ Agent gets a handle the moment it’s created → its URL resolves
immediately → the same template renders it. **No code change, no redeploy.** Same for a brand‑new
collection or a new variant on an existing product.

> Precondition: it must be **published to the Headless channel** (Section 1.6). The Storefront
> API token literally cannot see unpublished products — this is the #1 “why isn’t it showing” cause.

### 3.2 The Storefront API contract
- Hydrogen ships a `createStorefrontClient` (`context.storefront`) configured with
  `PUBLIC_STORE_DOMAIN`, `PUBLIC_STOREFRONT_API_TOKEN`, `PUBLIC_STOREFRONT_API_VERSION`.
- The token is the **public (unauthenticated) Storefront token** scoped to the Headless channel:
  it can `unauthenticated_read_product_listings`, read collections, create carts, etc.
- Pin an **API version** (e.g. `2025‑01`) and bump it deliberately; don’t float it.

### 3.3 Data fetching & caching (fast *and* fresh)
Hydrogen/Oxygen caches loader queries. Choose the strategy per data type so new products show up
promptly without hammering the API:

| Data | Strategy | Rationale |
|---|---|---|
| Product/collection **content** (title, copy, images) | `CacheLong()` (stale‑while‑revalidate, hours) | Rarely changes; serve fast |
| **Price** | `CacheShort()` (minutes) | Changes occasionally |
| **Availability / `availableForSale`** | `CacheShort()` or per‑request | Must reflect CJ stock sync quickly (don’t oversell) |
| Cart / checkout | **no cache** | Always live |

New products appear at worst after the **cache TTL** — or instantly if you purge on a webhook (3.4).
Never wrap availability in `CacheLong()`, or a sold‑out item lingers as buyable.

### 3.4 Webhooks — make “eventually” into “instantly”
Subscribe (Admin → Settings → Notifications → Webhooks, or via your app) to:
- `products/create`, `products/update` → **purge the product/collection cache** (or trigger an
  Oxygen soft‑purge / on‑demand revalidation) so the new/edited product is live at once.
- `inventory_levels/update` → purge availability cache so sold‑out flips immediately.
- (Optional) `collections/update` → refresh collection pages.

A tiny webhook handler (a route in your Hydrogen app, or a small worker) receives these and
invalidates the matching cache keys. Without webhooks the site is still correct — just up to one
TTL behind. **You do not need webhooks for products to *appear*; you need them to appear *instantly*.**

### 3.5 Metafields — render custom data (size chart, material, CJ attrs) with no code churn
Anything beyond core fields (size chart, fabric, care, badges, the CJ SKU) lives in **metafields**.

1. **Define** each metafield once: **Settings → Custom data → Products → Add definition**
   (namespace + key + type). Definitions give you validation and, crucially, **Storefront API
   visibility**.
2. **Expose to Storefront API:** mark the definition **“Storefront access / visible.”** Undefined
   or hidden metafields won’t return to Hydrogen — this is the metafield equivalent of the
   channel‑publish gotcha.
3. **Agent writes** metafield values via the Admin API on push (or you backfill them).
4. **Hydrogen reads** them in the product query:
   ```graphql
   metafields(identifiers: [
     {namespace: "custom", key: "size_chart"},
     {namespace: "custom", key: "material"}
   ]) { key value type }
   ```
   Render them in the template **by key**. Add a new *value* on any product → it renders. Add a
   new *field type* → you extend the template once, then every product with that field renders.

### 3.6 Variants & availability — render perfectly, disable the unbuyable
Query all variants and their real‑time state, then drive the UI from the data:
```graphql
options { name optionValues { name } }
variants(first: 100) {
  nodes {
    id title availableForSale
    price { amount currencyCode }
    selectedOptions { name value }
    image { url altText width height }
  }
}
```
- **Build the Color/Size selectors from `options`** — never hardcode option names. A new colour
  the agent adds shows up as a new swatch automatically.
- **Variant → image binding:** switch the gallery to `variant.image` on selection (clicking a
  colour swaps to that colour’s photo).
- **Disable the unbuyable:** for any option combination whose variant has `availableForSale:
  false` (or doesn’t exist), render the button **disabled/greyed**, and show **Sold out** on the
  add‑to‑cart. This is the Hydrogen equivalent of your existing store rule — and it’s driven
  entirely by CJ’s inventory sync (Section 1.3) flipping `availableForSale`.

> These three behaviours are exactly your current product‑page rules — they carry over 1:1, just
> expressed as Storefront API reads instead of Liquid.

### 3.7 Media / images
Images the agent pushes appear via `product.images` / `product.media`. Guidance:
- Use Hydrogen’s **`Image`** component with responsive `sizes`; Shopify’s CDN handles resizing.
- Enforce a **uniform aspect ratio** in the card component (e.g. 4:5, `object-fit: cover`) so a
  mixed‑ratio CJ catalog still renders an even grid — the ratio lives in *one* component, so it
  holds for every future product.
- Put **alt text** on every image (SEO + a11y). The agent should write descriptive alt on push.

---

## 4. End‑to‑end trace — one product, fully hands‑free

```
CJ Agent lists a product in CJ  ──▶  CJ app creates it in Shopify (variants+SKU+images+price)
        │                                   │
        │                          (auto‑published to Headless channel — §1.6)
        │                                   ▼
        │                     products/create webhook ──▶ Hydrogen cache purge (§3.4)
        │                                   ▼
        │                     Storefront API now returns it ──▶ /products/<handle> renders (§3.1)
        ▼
Customer buys ──▶ Shopify order (paid) ──▶ CJ auto‑syncs order (§1.2)
        ▼
CJ auto‑pays from Wallet (§1.4) ──▶ CJ procures + ships
        ▼
CJ writes tracking to Shopify fulfilment ──▶ order = Fulfilled ──▶ customer emailed
        ▼
CJ inventory sync updates stock (§1.3) ──▶ availableForSale flips ──▶ Hydrogen greys sold‑out (§3.6)
```
Every arrow is automated. The only human touches are **one‑time**: install/authorize CJ, set the
CJ settings toggles, keep the wallet funded, and scope the agent’s account.

---

## 5. Go‑live checklist

**Backend (CJ ↔ Shopify)**
- [ ] CJdropshipping app installed & store shows **Authorized**
- [ ] Orders: auto‑sync + auto‑place + auto‑fulfil/tracking write‑back **ON**
- [ ] Default **shipping method per destination** set
- [ ] Inventory: auto‑sync **ON**, continue‑selling **OFF**, single fulfilment location
- [ ] Wallet funded + **Auto‑Pay ON** + **low‑balance alert** set
- [ ] Auto‑pricing rule set (no `$0` variants)

**Agent access**
- [ ] Collaborator/staff account with **only** Products, Orders, Draft orders, inventory
- [ ] **2FA enforced**, no Settings/Finances/Apps‑install, Customers = none/view‑only
- [ ] Automation uses a **scoped custom‑app token**, not a human login

**Hydrogen frontend**
- [ ] **Headless channel** installed; new products **auto‑publish** to it
- [ ] Dynamic `products.$handle` / `collections.$handle` routes (no hardcoded catalog)
- [ ] Storefront token + pinned API version in env
- [ ] Caching: content `CacheLong`, price/availability `CacheShort`, cart no‑cache
- [ ] Webhooks purge cache on `products/*` + `inventory_levels/update`
- [ ] Metafield definitions defined **and Storefront‑visible**
- [ ] Variant selectors built from `options`; sold‑out disabled via `availableForSale`

---

## 6. Failure modes & the first thing to check

| Symptom | Almost always | Fix |
|---|---|---|
| New product live in Shopify but **not on Hydrogen** | Not published to **Headless channel** | §1.6 — make Headless a default channel / publish via API |
| New product appears **hours late** | Cache TTL, no webhook | §3.4 — add `products/create` cache purge |
| **Oversold** / sold‑out still buyable | Availability over‑cached, or continue‑selling ON | §1.3 + §3.3 — `CacheShort` availability, continue‑selling OFF |
| Orders synced to CJ but **not shipping** | **Wallet empty** or Auto‑Pay off | §1.4 — fund wallet, enable Auto‑Pay, set alert |
| Tracking not on the order | Auto write‑back off / product not connected | §1.1–§1.2 — connect SKU, enable tracking write‑back |
| Metafield value **not rendering** | Definition not **Storefront‑visible** | §3.5 — expose the definition |
| Agent can see too much | Over‑granted staff permissions | §2.2 — trim to least privilege, enforce 2FA |

---

### Appendix — this repo’s current reality (so nobody gets confused)
Today `stores/shopify/timeforbaby.alpha-tech.live/` renders a **Liquid theme** (not Hydrogen)
from `style/*.json` via the Python pipeline, and the CJdropshipping app is already installed
(auto tracking works). **Sections 1–2 of this guide apply as‑is right now.** Section 3 is the
**target** for when you migrate the storefront to Hydrogen; until then the Liquid theme is the
frontend and “products render automatically” is handled by the theme’s Liquid + the pipeline
instead of Storefront‑API loaders.
