# SKILL: store-audit — run ALL checks before production (PRD)

**When to run:** before shipping/deploying a store, after a batch of changes, or when reviewing a
newly-cloned store. Triggers: "audit the store", "QA the store", "check before production",
"run all the checks", "is the store ready to ship".

Audit a Hydrogen store end-to-end against its own docs + a professional release checklist, then
report findings (most severe first) and fix them. Storefronts are **English-only**.

## Inputs
- Store slug (default `alphaforbaby`) → app at `stores/shopify/hydrogen-<slug>/`.
- Its docs (read FIRST — they define "correct"): `hydrogen-<slug>/docs/AGENT_WORKFLOW.md`, `docs/QA.md`,
  `docs/SEO.md`, `ui-ux-pro skill`. **A new store runs the FULL set.**

## How to run
1. **Read the 4 docs**, then work through every section below. Verify programmatically
   (curl/grep/build) or by loading the page — desktop **and** ~375px mobile.
2. **Build gate:** `npm run build` must pass.
3. Collect findings as `severity | area | page | problem | fix` (blocker > major > minor).
4. Report ranked findings. When fixing: fix → rebuild → re-verify → redeploy (`scripts/deploy.sh`) →
   log to `changelog/CHANGELOG.md`. Follow `docs/AGENT_WORKFLOW.md`.

## Checklist (docs + extra pre-PRD checks)

### A. Unfinished / placeholder text (the #1 "looks unfinished" issue)
- [ ] Grep the app for leftovers: `TODO`, `FIXME`, `[INSERT`, `lorem`, `Hydrogen |`, `Mock.shop`,
      `example.com`, `change-me`, `your-store`, `coming soon`. **Zero** in anything user-visible.
- [ ] Page `<title>`/meta use the brand name, not "Hydrogen". No empty headings/labels.
- [ ] No `[TODO]`/placeholder or fabricated values on legal/contact pages — missing details are omitted.

### B. QA (see docs/QA.md)
- [ ] Every nav/footer/tile/card/policy/CTA link → 200 and correct target (crawl them).
- [ ] Footer has **only appropriate links**; no stray items.
- [ ] Product in the RIGHT collection (baby-girl item not under Baby Boys, etc.).
- [ ] Mobile at 375px: no horizontal scroll, nothing cut off/overlapping.
- [ ] Add-to-cart works; **checkout reaches Shopify** (if it bounces to home → payments not enabled).

### C. SEO (see docs/SEO.md)
- [ ] Unique title + meta description + one H1 per page; clean handles; robots.txt + sitemap.xml.
- [ ] Per product: unique selling copy, descriptive alt text, **no duplicate images in a product**,
      **no duplicate products**, price present (never `$0`), price sane (not too high vs market).

### D. UI/UX (see ui-ux-pro skill)
- [ ] **Background rule:** white store bg → white-bg product photos; non-white bg → NO white-bg photos.
- [ ] Uniform card ratio; consistent type scale + spacing; accessible contrast.
- [ ] Effects (carousel/hover/transitions) smooth, no jank/layout-shift, degrade on mobile.

### E. Extra release checks (before PRD)
- [ ] **No broken images** (hero/tiles/product images 200; local/CSP-safe, not external URLs).
- [ ] **No 404s / console errors** on any route; 404 page is branded.
- [ ] **Accessibility:** alt text everywhere, keyboard-navigable, visible focus, heading order.
- [ ] **Performance:** images lazy + sized; no huge bundles; fast TTFB.
- [ ] **Legal + privacy:** policies load; consent/cookie banner present; no owner personal data public.
- [ ] **Security:** no secrets/tokens in the client bundle; HTTPS; private token never client-side.
- [ ] **Favicon + OG/social tags** set; share preview looks right.
- [ ] **Analytics** wired (if expected); events fire.
- [ ] **Responsive** at 375 / 768 / 1280; **cross-browser** quick check.

## Output
A findings table (most severe first) + verdict: **SHIP** / **FIX FIRST**.

- **Deploy:** follow `hydrogen-<slug>/docs/CI_CD.md` — `npx shopify hydrogen deploy --force --no-lockfile-check --env-branch main` (production).
