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
(e.g. `hydrogen-alphaforbaby` → `alphaforbaby`). Non-store work (agent/
pipeline code under `src/`, docs, etc.) doesn't need this prefix.

## Full workflow

See **`docs/DEV_WORKFLOW.md`** for the complete standing playbook this
convention is part of — branch naming, the no-production-without-review
rule, preview-before-review requirement, commit discipline, logging, and
the status-honesty rule. That file is the source of truth; keep this
section in sync with it rather than duplicating detail here.
