/**
 * Audits which products are in which collections, and shows mismatches.
 * Usage: node scripts/audit-collections.mjs
 */
import {createAdminApiClient} from '@shopify/admin-api-client';

const STORE_DOMAIN = 'kgg8n0-k0.myshopify.com';
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

const COLLECTION_HANDLES = ['baby-boys', 'baby-girls', 'unisex'];

async function getCollectionProducts(handle) {
  const {data, errors} = await client.request(`
    query GetCollectionProducts($handle: String!) {
      collectionByHandle(handle: $handle) {
        id
        title
        products(first: 50) {
          nodes {
            id
            title
            handle
            tags
          }
        }
      }
    }
  `, {variables: {handle}});
  if (errors) { console.error(errors); return null; }
  return data?.collectionByHandle;
}

async function getAllProducts() {
  const {data, errors} = await client.request(`
    query {
      products(first: 50) {
        nodes {
          id
          title
          handle
          tags
          collections(first: 10) {
            nodes { handle title }
          }
        }
      }
    }
  `);
  if (errors) { console.error(errors); return []; }
  return data?.products?.nodes ?? [];
}

console.log('🔍 Auditing collections...\n');

const allProducts = await getAllProducts();

console.log('=== ALL PRODUCTS + THEIR COLLECTIONS ===');
for (const p of allProducts) {
  const cols = p.collections.nodes.map(c => c.handle).join(', ') || '(none)';
  console.log(`  ${p.title}`);
  console.log(`    tags: [${p.tags.join(', ')}]`);
  console.log(`    collections: ${cols}`);
  console.log(`    id: ${p.id}`);
  console.log('');
}

console.log('\n=== COLLECTION CONTENTS ===');
for (const handle of COLLECTION_HANDLES) {
  const col = await getCollectionProducts(handle);
  if (!col) { console.log(`  ❌ ${handle} — not found`); continue; }
  console.log(`\n  📦 ${col.title} (${handle}) — ${col.products.nodes.length} products:`);
  for (const p of col.products.nodes) {
    console.log(`    - ${p.title} [${p.tags.join(', ')}]`);
  }
}
