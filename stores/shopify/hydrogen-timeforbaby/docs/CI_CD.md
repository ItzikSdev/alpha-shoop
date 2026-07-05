# CI/CD — how Sol builds & deploys (LOCAL, not GitHub Actions)

Deploys run **on this machine**, not in GitHub Actions. Each store is a profile under
`store-profiles/<slug>/` (`theme.config.json` + git-ignored `store.env` with the Oxygen deploy token).

## The flow (dev → test → production)
1. **Dev/localhost first.** Edit code / `theme.config.json`. Preview locally if possible.
2. **Build gate:** `npm run build` MUST pass. Fix any error before deploying.
3. **Run the checks:** QA.md + SEO.md + UIUX.md + the store-audit skill. Fix findings.
4. **Deploy to PRODUCTION** (the live domain = the `main` git-branch environment on Oxygen):
   ```bash
   set -a; source store-profiles/<slug>/store.env; set +a
   npx shopify hydrogen deploy --force --no-lockfile-check --env-branch main
   ```
   - `--env-branch main` → the **production** environment (the one the custom domain serves).
     Without it the deploy lands on the wrong environment and the live site won't update.
   - `--force` → allow deploying with uncommitted working-tree changes.
   - Requires `SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN` (from `store.env`) + Node on PATH.
   - `--preview` (instead of `--env-branch main`) deploys to a preview env for testing.
5. **Verify live:** load the domain and confirm the change is there. Note: raw Oxygen
   `*.myshopify.dev` URLs are staff-gated (302/403 to Shopify login) — check the real domain in a
   browser. Cloudflare may 403 non-browser `curl`.
6. **Report to Slack** what changed + what was fixed, and append to `changelog/CHANGELOG.md`.

## Notes / gotchas
- The helper `./scripts/deploy.sh <slug>` does build + deploy, but pass production via the
  `--env-branch main` path above (the script defaults to `--force`; add env-branch when going live).
- Node must be **22 or 24** (Hydrogen doesn't support 25). Use `nvm use 22` if needed.
- New store: also run `./scripts/new-store.sh <slug>` first, fill its `theme.config.json` + `store.env`.
- Never commit `store.env` or `.env` (secrets). Public Storefront token is fine client-side; the
  deploy token + private token are secrets.
