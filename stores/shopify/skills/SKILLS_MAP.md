# Skills map — which skill Sol uses for which task

Sol: pick the RIGHT skill for the request, READ it, then do the work yourself. You own the store.
Base path for the Shopify toolkit skills: `stores/shopify/skills/.claude/skills/<name>/SKILL.md`.

## Route by request type
| The request is about… | Use skill |
|---|---|
| **Find / add / vet PRODUCTS** (source from CJ, fill a collection, fix 1-image products, sourcing targets) | `skills/product-sourcing.md` |
| **UI / UX / design / visual / "looks off" / buttons / spacing / mobile look** | `skills/ui-ux-pro.md` |
| **Full store check before shipping (QA/SEO/links/mobile)** | `skills/store-audit.md` |
| **Hydrogen storefront CODE** (React/Remix, routes, components, `theme.config.json`) | `.claude/skills/shopify-hydrogen/SKILL.md` |
| **Material Tailwind / product-page redesign** (Carousel, Dialog, any `@material-tailwind/react` component) | `skills/material-tailwind.md` |
| **Storefront GraphQL** (query products/collections/cart for the frontend) | `.claude/skills/shopify-storefront-graphql/SKILL.md` |
| **Manage store DATA** (move products between collections / fix categorization, dedupe, fix $0 or high prices, SEO titles/meta, variants, images) → use the `shopify_admin` TOOL | `.claude/skills/shopify-admin/SKILL.md` |
| **Metafields / custom data** (size chart, material, structured data) | `.claude/skills/shopify-custom-data/SKILL.md` |
| **Liquid theme** (Online Store 2.0, sections, snippets) | `.claude/skills/shopify-liquid/SKILL.md` |
| **Shopify Functions** (discounts, cart/checkout logic) | `.claude/skills/shopify-functions/SKILL.md` |
| **Shopify CLI** (dev/build/deploy commands) | `.claude/skills/shopify-use-shopify-cli/SKILL.md` + `docs/CI_CD.md` |
| **Build / deploy / release (CI/CD)** | `hydrogen-alphaforbaby/docs/CI_CD.md` |
| **Anything else Shopify** | list `.claude/skills/` and pick the closest `shopify-*` skill |

## Method (always)
1. Identify the task type → read the matching skill above (and `docs/STORE_MEMORY.md` for what you already know).
2. Do the work yourself with your tools (edit_store_file, shell, shopify_admin, …).
3. TEST it works (build passes; for interactive UI add a temporary console.log to prove open/close).
4. Deploy per `docs/CI_CD.md` (`./scripts/deploy.sh alphaforbaby`), verify the live domain, report to Slack.
5. Append one line to `docs/STORE_MEMORY.md` recent-changes.
