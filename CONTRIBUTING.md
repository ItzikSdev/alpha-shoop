# Contributing

## Branch naming for store work

This repo hosts multiple Shopify/Hydrogen storefronts under `stores/shopify/`.
Branches that touch a specific store's code must be namespaced by that store,
not given a generic feature name:

```
<store-slug>/<feature-description>
```

Examples:

- `alphaforbaby/pdp-conversion-improvements`
- `alphaforbaby/checkout-currency-fix`
- `timeofbaby/hero-video-refresh`

`<store-slug>` matches the store's directory name under `stores/shopify/`
(e.g. `hydrogen-alphaforbaby` → `alphaforbaby`). This keeps branches
identifiable at a glance once more than one store is under active
development at the same time, and lets the per-store Oxygen deploy
workflows (`.github/workflows/oxygen-deploy-<store>.yml`, each scoped by
`paths:` to its own `stores/shopify/<store>/**`) be reasoned about by
branch name alone.

Non-store work (agent/pipeline code under `src/`, docs, etc.) doesn't need
this prefix — use a plain descriptive branch name as usual.

## Workflow for store-code changes

1. Branch from `main` using the naming convention above.
2. Do all work on that branch. Never push directly to `main` or trigger a
   production deploy without explicit review/approval from the store owner.
3. Each meaningful change is its own commit with a descriptive message
   (what changed and why, not just what).
4. Pushing the branch triggers the store's Oxygen deploy workflow, which
   deploys to Shopify's Preview environment (not Production, which is
   bound to `main` — see `npx shopify hydrogen env list`). Share the
   preview link for review before merging.
5. Merge to `main` only after explicit sign-off.
