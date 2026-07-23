/**
 * ONE-TIME admin route to fix collection assignments.
 * DELETE THIS FILE after running once.
 * Access: /admin/fix-collections
 */
import {data as jsonData} from 'react-router';

const STORE_DOMAIN = 'kgg8n0-k0.myshopify.com';

const GIRLS_KEYWORDS = ['girl', 'girls', 'princess', 'floral', 'pink', 'heart', 'sweet', 'plaid summer', 'summer baby girl', 'triangle'];
const BOYS_KEYWORDS  = ['boy', 'boys', 'fishing', 'cartoon', 'monk', 'bamboo', 'striped', 'fleece', 'crew neck', 'classic crew', 'cozy letter', 'split-leg', 'split leg'];

function classify(title) {
  const t = title.toLowerCase();
  if (GIRLS_KEYWORDS.some(k => t.includes(k))) return 'baby-girls';
  if (BOYS_KEYWORDS.some(k => t.includes(k))) return 'baby-boys';
  return 'unisex';
}

async function adminQuery(token, query, variables = {}) {
  const res = await fetch(`https://${STORE_DOMAIN}/admin/api/2025-01/graphql.json`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': token,
    },
    body: JSON.stringify({query, variables}),
  });
  return res.json();
}

export async function loader({context, request}) {
  const url = new URL(request.url);
  const dryRun = url.searchParams.get('dry') !== '0';

  // Get admin token from env
  const token = context.env?.SHOPIFY_ADMIN_TOKEN;
  if (!token) {
    return jsonData({error: 'SHOPIFY_ADMIN_TOKEN not set in .env'}, {status: 500});
  }

  const log = [];

  // 1. Get all products
  const {data: pData} = await adminQuery(token, `
    query {
      products(first: 50) {
        nodes { id title handle }
      }
    }
  `);
  const products = pData?.products?.nodes ?? [];
  log.push(`Found ${products.length} products`);

  // Classify
  const byCollection = {'baby-boys': [], 'baby-girls': [], 'unisex': []};
  for (const p of products) {
    const col = classify(p.title);
    byCollection[col].push(p);
    log.push(`  ${col.padEnd(12)} ← ${p.title}`);
  }

  // 2. Get collections
  const collections = {};
  for (const handle of ['baby-boys', 'baby-girls', 'unisex']) {
    const {data: cData} = await adminQuery(token, `
      query GetCollection($handle: String!) {
        collectionByHandle(handle: $handle) {
          id title
          products(first: 50) { nodes { id title } }
        }
      }
    `, {handle});
    const col = cData?.collectionByHandle;
    if (!col) {
      log.push(`❌ Collection "${handle}" not found!`);
      continue;
    }
    collections[handle] = col;
    log.push(`Collection ${handle}: ${col.products.nodes.length} products`);
  }

  // 3. Fix assignments
  const changes = [];
  for (const handle of ['baby-boys', 'baby-girls', 'unisex']) {
    const col = collections[handle];
    if (!col) continue;
    const correctIds = new Set(byCollection[handle].map(p => p.id));
    const currentIds = new Set(col.products.nodes.map(p => p.id));

    const toAdd    = [...correctIds].filter(id => !currentIds.has(id));
    const toRemove = [...currentIds].filter(id => !correctIds.has(id));

    if (toAdd.length) {
      changes.push({action: 'add', collection: handle, collectionId: col.id, productIds: toAdd, products: toAdd.map(id => products.find(p => p.id === id)?.title)});
      if (!dryRun) {
        await adminQuery(token, `
          mutation AddProducts($id: ID!, $productIds: [ID!]!) {
            collectionAddProducts(id: $id, productIds: $productIds) {
              collection { id title productsCount { count } }
              userErrors { field message }
            }
          }
        `, {id: col.id, productIds: toAdd});
        log.push(`✅ Added ${toAdd.length} to ${handle}`);
      }
    }
    if (toRemove.length) {
      changes.push({action: 'remove', collection: handle, collectionId: col.id, productIds: toRemove, products: toRemove.map(id => col.products.nodes.find(p => p.id === id)?.title)});
      if (!dryRun) {
        await adminQuery(token, `
          mutation RemoveProducts($id: ID!, $productIds: [ID!]!) {
            collectionRemoveProducts(id: $id, productIds: $productIds) {
              job { id }
              userErrors { field message }
            }
          }
        `, {id: col.id, productIds: toRemove});
        log.push(`✅ Removed ${toRemove.length} from ${handle}`);
      }
    }
  }

  return jsonData({
    dryRun,
    message: dryRun ? 'DRY RUN — add ?dry=0 to actually apply changes' : 'APPLIED',
    changes,
    log,
  });
}

export default function FixCollections() {
  return (
    <div style={{fontFamily: 'monospace', padding: '2rem', maxWidth: '900px', margin: '0 auto'}}>
      <h1>Fix Collections</h1>
      <p>This is a one-time admin tool. Check the JSON response at <code>/admin/fix-collections</code></p>
      <p>To apply: <a href="/admin/fix-collections?dry=0">/admin/fix-collections?dry=0</a></p>
      <p>Dry run: <a href="/admin/fix-collections">/admin/fix-collections</a></p>
    </div>
  );
}
