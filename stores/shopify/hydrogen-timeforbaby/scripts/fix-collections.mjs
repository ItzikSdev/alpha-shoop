/**
 * Fix collection assignments for timeforbaby.
 * 
 * Products are classified by their TITLE keywords:
 *   baby-girls  → "girl", "girls", "princess", "floral", "pink", "heart", "sweet", "plaid summer"
 *   baby-boys   → "boy", "boys", "fishing", "cartoon", "monk", "bamboo", "striped", "fleece", "crew neck", "classic"
 *   unisex      → everything else (romper, onesie, bodysuit, loungewear, sleepsuit, waffle, cotton essentials)
 *
 * Usage: SHOPIFY_ADMIN_TOKEN=xxx node scripts/fix-collections.mjs
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

// ── Classification rules ──────────────────────────────────────────────────────
const GIRLS_KEYWORDS = ['girl', 'girls', 'princess', 'floral', 'pink', 'heart', 'sweet', 'plaid summer', 'summer baby girl', 'triangle'];
const BOYS_KEYWORDS  = ['boy', 'boys', 'fishing', 'cartoon', 'monk', 'bamboo', 'striped', 'fleece', 'crew neck', 'classic crew', 'cozy letter', 'split-leg', 'split leg'];

function classify(title) {
  const t = title.toLowerCase();
  if (GIRLS_KEYWORDS.some(k => t.includes(k))) return 'baby-girls';
  if (BOYS_KEYWORDS.some(k => t.includes(k))) return 'baby-boys';
  return 'unisex';
}

// ── Fetch all products ────────────────────────────────────────────────────────
async function getAllProducts() {
  const {data, errors} = await client.request(`
    query {
      products(first: 50) {
        nodes { id title handle }
      }
    }
  `);
  if (errors) throw new Error(JSON.stringify(errors));
  return data.products.nodes;
}

// ── Fetch collection by handle ────────────────────────────────────────────────
async function getCollection(handle) {
  const {data, errors} = await client.request(`
    query GetCollection($handle: String!) {
      collectionByHandle(handle: $handle) {
        id title
        products(first: 50) { nodes { id title } }
      }
    }
  `, {variables: {handle}});
  if (errors) throw new Error(JSON.stringify(errors));
  return data?.collectionByHandle;
}

// ── Add products to collection ────────────────────────────────────────────────
async function addToCollection(collectionId, productIds) {
  if (!productIds.length) return;
  const {data, errors} = await client.request(`
    mutation AddProducts($id: ID!, $productIds: [ID!]!) {
      collectionAddProducts(id: $id, productIds: $productIds) {
        collection { id title productsCount { count } }
        userErrors { field message }
      }
    }
  `, {variables: {id: collectionId, productIds}});
  if (errors) throw new Error(JSON.stringify(errors));
  const ue = data?.collectionAddProducts?.userErrors;
  if (ue?.length) throw new Error(JSON.stringify(ue));
  return data?.collectionAddProducts?.collection;
}

// ── Remove products from collection ──────────────────────────────────────────
async function removeFromCollection(collectionId, productIds) {
  if (!productIds.length) return;
  const {data, errors} = await client.request(`
    mutation RemoveProducts($id: ID!, $productIds: [ID!]!) {
      collectionRemoveProducts(id: $id, productIds: $productIds) {
        job { id }
        userErrors { field message }
      }
    }
  `, {variables: {id: collectionId, productIds}});
  if (errors) throw new Error(JSON.stringify(errors));
  const ue = data?.collectionRemoveProducts?.userErrors;
  if (ue?.length) throw new Error(JSON.stringify(ue));
}

// ── Main ──────────────────────────────────────────────────────────────────────
console.log('🔍 Fetching all products...');
const products = await getAllProducts();
console.log(`   Found ${products.length} products\n`);

// Classify each product
const byCollection = {'baby-boys': [], 'baby-girls': [], 'unisex': []};
for (const p of products) {
  const col = classify(p.title);
  byCollection[col].push(p);
  console.log(`  ${col.padEnd(12)} ← ${p.title}`);
}

console.log('\n📦 Fetching collections...');
const collections = {};
for (const handle of ['baby-boys', 'baby-girls', 'unisex']) {
  const col = await getCollection(handle);
  if (!col) { console.error(`❌  Collection "${handle}" not found — create it in Shopify admin first`); process.exit(1); }
  collections[handle] = col;
  console.log(`   ${handle}: ${col.products.nodes.length} products currently`);
}

// For each collection: add missing, remove wrong ones
for (const handle of ['baby-boys', 'baby-girls', 'unisex']) {
  const col = collections[handle];
  const correctIds = new Set(byCollection[handle].map(p => p.id));
  const currentIds = new Set(col.products.nodes.map(p => p.id));

  const toAdd    = [...correctIds].filter(id => !currentIds.has(id));
  const toRemove = [...currentIds].filter(id => !correctIds.has(id));

  console.log(`\n🔧 ${handle}:`);
  if (toAdd.length) {
    console.log(`   Adding ${toAdd.length} products...`);
    const result = await addToCollection(col.id, toAdd);
    console.log(`   ✅ Now has ${result?.productsCount?.count} products`);
  }
  if (toRemove.length) {
    console.log(`   Removing ${toRemove.length} wrong products...`);
    await removeFromCollection(col.id, toRemove);
    console.log(`   ✅ Removed`);
  }
  if (!toAdd.length && !toRemove.length) {
    console.log(`   ✓ Already correct`);
  }
}

console.log('\n✅ Done! Collections are now correctly assigned.');
