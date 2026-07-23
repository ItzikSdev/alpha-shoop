#!/usr/bin/env bash
# ============================================================================
# Create a NEW Shopify store profile from this template (this app is the template).
#
#   ./scripts/new-store.sh <new-store-slug>
#   ./scripts/new-store.sh cozypaws
#
# It creates store-profiles/<slug>/ with:
#   - theme.config.json  (copied from alphaforbaby — edit brand/colors/hero/products)
#   - store.env          (secrets skeleton — fill domain + tokens)
# Then: edit those two files and run ./scripts/deploy.sh <slug>
# ============================================================================
set -euo pipefail

SLUG="${1:-}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$APP_DIR/store-profiles/alphaforbaby"
DEST="$APP_DIR/store-profiles/$SLUG"

die() { echo "❌ $*" >&2; exit 1; }
[ -n "$SLUG" ] || die "usage: ./scripts/new-store.sh <new-store-slug>"
[[ "$SLUG" =~ ^[a-z0-9-]+$ ]] || die "slug must be lowercase letters/numbers/hyphens"
[ ! -d "$DEST" ] || die "store-profiles/$SLUG already exists"
[ -d "$SRC" ] || die "template profile store-profiles/alphaforbaby missing"

mkdir -p "$DEST"
cp "$SRC/theme.config.json" "$DEST/theme.config.json"

cat > "$DEST/store.env" <<EOF
# ── $SLUG — deploy secrets (git-ignored) ──
SESSION_SECRET="$(node -e 'console.log(require("crypto").randomBytes(24).toString("hex"))' 2>/dev/null || openssl rand -hex 24)"

# Shopify Storefront API (public, read-only). Mint via Admin API storefrontAccessTokenCreate
# or take it from the store's Headless/Hydrogen channel.
PUBLIC_STORE_DOMAIN="your-store.myshopify.com"
PUBLIC_STOREFRONT_API_TOKEN=""
PUBLIC_STOREFRONT_API_VERSION="2025-01"
PUBLIC_CHECKOUT_DOMAIN="your-store.myshopify.com"

# Oxygen deploy token — from the Hydrogen/Headless channel in Shopify admin.
SHOPIFY_HYDROGEN_DEPLOYMENT_TOKEN=""
EOF

echo "✅ Created store-profiles/$SLUG/"
echo "   Next:"
echo "   1. Edit store-profiles/$SLUG/theme.config.json  (brand, colors, hero, tiles, legal, favicons)"
echo "   2. Fill store-profiles/$SLUG/store.env          (domain + storefront token + deploy token)"
echo "   3. ./scripts/deploy.sh $SLUG"
