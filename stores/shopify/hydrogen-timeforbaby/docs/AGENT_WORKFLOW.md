# Agent Workflow — what Sol MUST do after every change

Sol runs this **after any change** to a store (code, `theme.config.json`, products, copy).
The template must never be tangled: change a store by editing its `theme.config.json`
(and `app/*.jsx` only when structure must change). Storefronts are **ENGLISH-ONLY**.

## After EVERY change (required, in order)
1. **Build** — `npm run build` must pass. If it fails, fix before anything else.
2. **Run the 3 check docs** on the changed area (and anything it could affect):
   - [`QA.md`](QA.md) — links, text/footer, mobile, product↔collection correctness, functions.
   - [`SEO.md`](SEO.md) — titles/meta/alt, unique copy, no dup images/products, price sane.
   - [`ui-ux-pro skill`](ui-ux-pro skill) — background/product-image rule, effects, visual polish.
3. **Verify live behavior** — load the affected page(s) and confirm the change actually works
   (not just that it compiled). Check desktop **and** mobile widths.
4. **Deploy** — `./scripts/deploy.sh <slug>` — for PRODUCTION use `npx shopify hydrogen deploy --force --no-lockfile-check --env-branch main` (see docs/CI_CD.md).
   Never deploy if step 1 failed.
5. **Log + narrate** — post to Slack what changed + which checks passed, and append a line to
   the store's `changelog/CHANGELOG.md` (title, time, context, what changed).

## New store (built from the template) — MORE checks (run the FULL set)
When creating a store via `./scripts/new-store.sh <slug>`, run **everything above PLUS**:
- [ ] Every value in `theme.config.json` replaced for the new brand (name, logo, colors, hero,
      tiles, testimonials, legal, favicons) — **no leftover "TIMEFOR BABY" / baby-clothes copy**.
- [ ] `store.env` filled: domain, Storefront API token, Oxygen deploy token.
- [ ] All 3 collections exist in Shopify and are populated; nav links resolve (no 404).
- [ ] Policies pulled from Shopify (Privacy/Refund/Shipping/Terms) render; no `[TODO]`/personal data.
- [ ] Full [`QA.md`](QA.md) + [`SEO.md`](SEO.md) + [`ui-ux-pro skill`](ui-ux-pro skill) pass end-to-end.
- [ ] Payments enabled and a test cart **reaches checkout** (see QA "checkout" check).
- [ ] Favicon + logo are the new brand's, not the template's.

## Hard rules (never violate)
- ENGLISH-ONLY storefronts. Never publish the owner's personal details — only public contact is
  `suppot.timeforbaby@alpha-tech.live`.
- Don't rewrite the template wholesale; don't revert approved design.
- If a required detail is missing, **omit it** — never ship a `[TODO]`/placeholder or a fake value.
