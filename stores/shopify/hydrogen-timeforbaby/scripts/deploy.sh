#!/usr/bin/env bash
# ============================================================================
# Local CI/CD — build on THIS machine and deploy to Shopify Oxygen.
# NO GitHub Actions. Multi-store: each store has a profile under store-profiles/.
#
#   ./scripts/deploy.sh <store-slug> [--preview]
#   ./scripts/deploy.sh timeforbaby
#
# What it does:
#   1. Loads store-profiles/<slug>/store.env  (domain, storefront token, deploy token)
#   2. Activates store-profiles/<slug>/theme.config.json  (brand/design/products)
#   3. npm ci + npm run build   (local build)
#   4. shopify hydrogen deploy  (uploads the built app to that store's Oxygen)
# ============================================================================
set -euo pipefail

SLUG="${1:-}"
MODE="${2:-}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE_DIR="$APP_DIR/store-profiles/$SLUG"

die() { echo "❌ $*" >&2; exit 1; }

[ -n "$SLUG" ] || die "usage: ./scripts/deploy.sh <store-slug> [--preview]"
[ -d "$PROFILE_DIR" ] || die "no profile: store-profiles/$SLUG (run ./scripts/new-store.sh $SLUG first)"
[ -f "$PROFILE_DIR/store.env" ] || die "missing $PROFILE_DIR/store.env"
[ -f "$PROFILE_DIR/theme.config.json" ] || die "missing $PROFILE_DIR/theme.config.json"

# Node version guard (Hydrogen supports ^22 || ^24; Node 25 is unsupported)
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [ "$NODE_MAJOR" != "22" ] && [ "$NODE_MAJOR" != "24" ]; then
  echo "⚠️  Node $NODE_MAJOR detected. Hydrogen wants 22 or 24. Run: nvm use 22" >&2
fi

echo "▶ Deploying store '$SLUG' from $APP_DIR"

# 1) load secrets
set -a; # shellcheck disable=SC1090
source "$PROFILE_DIR/store.env"; set +a
[ -n "${SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN:-}" ] || \
  die "SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN is empty in $PROFILE_DIR/store.env.
     Install the Hydrogen/Headless channel in Shopify admin for this store, copy its
     Oxygen deployment token into that file, then re-run."

# 2) activate this store's design + a matching .env for the build
cp "$PROFILE_DIR/theme.config.json" "$APP_DIR/app/theme.config.json"
cp "$PROFILE_DIR/store.env" "$APP_DIR/.env"
echo "  ✓ activated theme.config.json + .env for $SLUG (domain: ${PUBLIC_STORE_DOMAIN:-?})"

cd "$APP_DIR"

# 3) local build
echo "▶ Installing deps + building locally…"
npm ci --no-audit --no-fund
npm run build

# 4) deploy to Oxygen
DEPLOY_FLAGS="--no-lockfile-check --force --env-branch main"   # production (live domain)
if [ "$MODE" = "--preview" ]; then
  DEPLOY_FLAGS="--no-lockfile-check --force --preview"
  echo "▶ Deploying to Oxygen (PREVIEW)…"
else
  echo "▶ Deploying to Oxygen (production)…"
fi
# The deploy token authenticates + targets the right Oxygen storefront.
SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN="$SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN" \
  CI=1 SHOPIFY_CLI_NO_ANALYTICS=1 npx shopify hydrogen deploy $DEPLOY_FLAGS

echo "✅ Deployed store '$SLUG'."
