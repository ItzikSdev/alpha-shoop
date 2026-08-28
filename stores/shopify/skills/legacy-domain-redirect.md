# Legacy myshopify.com domain — redirect to the real (Hydrogen) storefront

Use this whenever a new store's Hydrogen storefront goes live, or whenever a
visitor could land on the classic `*.myshopify.com` domain and see the
unbranded default theme. Apply it as a standard step in every store's
go-live routine — don't rediscover this.

---

## 1. Why this is needed

Every Shopify store has a default `*.myshopify.com` domain tied to the
classic **Online Store** sales channel (Dawn theme by default) — separate
from the custom domain a headless Hydrogen storefront serves from.

**Checkout always runs on the `*.myshopify.com` domain regardless** (verified
live on alphaforbaby, 2026-08-26: `cartCreate`'s `checkoutUrl` resolves to
`kgg8n0-k0.myshopify.com/checkouts/cn/...`, never the custom domain). This is
normal Shopify behavior, not a bug — do not try to move checkout itself.

The actual problem: a visitor who lands on the myshopify.com root — via
back-navigation during/after checkout, a stray old link, or search engines
indexing it — sees the default Dawn theme (unbranded, often near-empty),
which looks broken or like a different store.

## 2. What NOT to do: password-protect the Online Store channel

Tried and reverted on alphaforbaby, 2026-08-26. Shopify's native storefront
password gate caught `/cart/c/...` paths on this store's configuration —
confirmed live (checkout redirected to the password page). **Never use
password protection to hide the classic theme** — it risks breaking real
checkout for reasons that aren't obviously visible until a real customer
hits it. There is no known way to make Shopify's password gate reliably
exclude checkout paths — don't attempt it again without new evidence this
has actually changed.

## 3. What to do instead: an immediate JS redirect on the homepage only

Replace **only** the Online Store channel's homepage/index template with a
minimal section that redirects immediately, preserving path and query
string:

```html
<script>
  window.location.replace(
    "https://<CUSTOM_DOMAIN>" + window.location.pathname + window.location.search
  );
</script>
```

Keep minimal branded fallback content below the script (store name + a
manual link to `https://<CUSTOM_DOMAIN>`) for non-JS clients/crawlers that
don't execute it.

**Scope — homepage only.** Leave product/collection templates on the classic
channel alone unless there's a specific reason to touch them; they aren't
what a lost visitor typically hits, and touching more surface area than
needed adds risk for no benefit.

**Implementation** (Admin REST theme-asset API, same pattern used elsewhere
in this repo — see `src/mcp_tools/shopify_design.py` / `_shopify_rest`):
1. Find the live theme: `GET themes.json`, the one with `"role": "main"`.
2. Add a new, isolated section asset, e.g. `sections/afb-redirect.liquid`,
   containing the script + fallback content above.
3. Overwrite `templates/index.json` to reference only that new section:
   `{"sections":{"main":{"type":"<section-name>","settings":{}}},"order":["main"]}`.

Do not touch `templates/product.json`, `templates/collection.json`, the
`layout/theme.liquid` cart/checkout includes, or anything under
`/cart/`, `/checkout/`, `/checkouts/` — this pattern only ever needs the
homepage template.

## 4. Verification — required every time, in this order

a. **Scope check**: confirm via Admin API which files were actually
   written (the asset PUT response echoes the `key`) — only
   `templates/index.json` and the new section file, nothing under
   `cart`/`checkout`/`checkouts`.
b. **Checkout, before and after**: a real `cartCreate` → `checkoutUrl` call
   via the Storefront API, confirming the redirect chain still lands on
   `/checkouts/cn/...` (or equivalent) identically before and after the
   template change. Do this both times — not just once "to be safe".
c. **Browser check**: confirm in an actual browser (not just curl) that the
   myshopify.com root auto-redirects to the custom domain with no click
   needed. `curl` only proves the script is present in the raw HTML, not
   that it executes — a real browser check is required, not optional.

## 5. When to apply

Standard step whenever a new store's Hydrogen storefront is set up and goes
live — do this as routine, at the same time the custom domain is pointed at
the Hydrogen deployment, not as a reactive fix after someone reports seeing
the wrong theme.

## 6. CI/CD: the Oxygen deploy workflow is per-store, scope it from day one

Each store's Hydrogen storefront lives in its own `stores/shopify/<name>/`
subdirectory in this monorepo, and each gets its own GitHub Actions
workflow deploying to its own Oxygen environment (e.g.
`.github/workflows/oxygen-deploy-alphaforbaby.yml`). When Shopify Admin's
"Connect to GitHub" flow auto-generates this file (via a PR), it defaults
to running at the repo root against `on: [push]` with no scoping — wrong
for a monorepo. Fix it in that PR before merging:

1. **`working-directory`**: add `defaults.run.working-directory:
   stores/shopify/<name>` at the job level (and scope the npm-cache
   `hashFiles(...)` key to that store's `package-lock.json`) — otherwise
   `npm ci` runs at the repo root and fails.
2. **`paths:` filter**: scope `on.push.paths` to
   `stores/shopify/<name>/**` — otherwise every push anywhere in the
   monorepo (including the unrelated Python backend) triggers a Hydrogen
   rebuild for this store.
3. **Rename the file** to something store-specific
   (`oxygen-deploy-<name>.yml`), not Shopify's generic auto-generated name
   — so a second store's auto-generated workflow file is obviously
   separate, not something that collides or needs merging with the first.

**When adding store #2**: copy the existing store's workflow file, rename
it for the new store, update both the `paths:` filter and
`working-directory` to the new store's subdirectory, and set up its own
`OXYGEN_DEPLOYMENT_TOKEN_<id>` secret (Shopify's Connect-to-GitHub flow
issues one per storefront). This makes onboarding a new store's CI/CD a
copy-paste exercise, not a rediscovery.
