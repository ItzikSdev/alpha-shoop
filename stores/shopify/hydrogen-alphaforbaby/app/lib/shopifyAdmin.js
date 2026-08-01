// Server-side-only Shopify Admin GraphQL client. NEVER import this from a
// component that renders on the client — it reads a private (non-PUBLIC_)
// env var, so it must only ever run inside loaders/actions (Oxygen worker).
const ADMIN_API_VERSION = '2025-01';

/**
 * @param {Env} env
 * @param {string} query
 * @param {Record<string, unknown>} variables
 */
export async function shopifyAdminQuery(env, query, variables = {}) {
  // SHOPIFY_ADMIN_STORE_DOMAIN is the *.myshopify.com domain the Admin API
  // actually lives on — PUBLIC_STORE_DOMAIN can point at a storefront/custom
  // domain that doesn't resolve under /admin/api/, so prefer the dedicated var.
  const domain = env.SHOPIFY_ADMIN_STORE_DOMAIN || env.PUBLIC_STORE_DOMAIN;
  const token = env.SHOPIFY_ADMIN_TOKEN;
  if (!token) {
    throw new Error(
      'SHOPIFY_ADMIN_TOKEN is not set (see .env.example) — cannot write to the Shopify Admin API',
    );
  }

  const res = await fetch(
    `https://${domain}/admin/api/${ADMIN_API_VERSION}/graphql.json`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': token,
      },
      body: JSON.stringify({query, variables}),
    },
  );

  const body = await res.json();
  if (body.errors) {
    throw new Error(JSON.stringify(body.errors));
  }
  return body.data;
}
