/**
 * Adds a product to a Shopify collection via Admin API.
 * Usage: node scripts/add-to-collection.mjs <productGid> <collectionHandle>
 */
import {createAdminApiClient} from '@shopify/admin-api-client';

const STORE_DOMAIN = 'kgg8n0-k0.myshopify.com';
// Admin API token — read from env
const ADMIN_TOKEN = process.env.SHOPIFY_ADMIN_TOKEN;

if (!ADMIN_TOKEN) {
  console.error('❌  Set SHOPIFY_ADMIN_TOKEN env var');
  process.exit(1);
}

const client = createAdminApiClient({
  storeDomain: STORE_DOMAIN,
  apiVersion: '2025-01',
  accessToken: ADMIN_TOKEN,
});

const [,, productGid, collectionHandle] = process.argv;

if (!productGid || !collectionHandle) {
  console.error('Usage: node scripts/add-to-collection.mjs <productGid> <collectionHandle>');
  process.exit(1);
}

// 1. Find collection by handle
const {data: colData, errors: colErrors} = await client.request(`
  query GetCollection($handle: String!) {
    collectionByHandle(handle: $handle) {
      id
      title
    }
  }
`, {variables: {handle: collectionHandle}});

if (colErrors) { console.error(colErrors); process.exit(1); }
const collection = colData?.collectionByHandle;
if (!collection) {
  console.error(`❌  Collection "${collectionHandle}" not found`);
  process.exit(1);
}
console.log(`✓ Found collection: ${collection.title} (${collection.id})`);

// 2. Add product to collection
const {data: mutData, errors: mutErrors} = await client.request(`
  mutation AddProductToCollection($id: ID!, $productIds: [ID!]!) {
    collectionAddProducts(id: $id, productIds: $productIds) {
      collection { id title productsCount { count } }
      userErrors { field message }
    }
  }
`, {variables: {id: collection.id, productIds: [productGid]}});

if (mutErrors) { console.error(mutErrors); process.exit(1); }
const result = mutData?.collectionAddProducts;
if (result?.userErrors?.length) {
  console.error('❌  User errors:', result.userErrors);
  process.exit(1);
}
console.log(`✅  Added to "${result.collection.title}" — total products: ${result.collection.productsCount.count}`);
