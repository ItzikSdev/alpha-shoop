// Shopify Custom Pixel — sends anonymous visit events to the Alpha live-visitors beacon.
// Install (no theme change): Shopify admin → Settings → Customer events → Add custom pixel →
// name it "Alpha live visitors" → paste this file → Save → Connect.
// Replace BEACON_URL and TOKEN below (TOKEN = VISITOR_BEACON_TOKEN from .env; it only filters noise).
// Sent: Shopify's anonymous clientId, event name, referrer, page URL (for utm_source), order total
// on purchase. Never: name, email, address, IP, cart contents.
const BEACON_URL = 'https://beacon.alpha-tech.live/v';
const TOKEN = 'REPLACE-WITH-VISITOR_BEACON_TOKEN';

const EVENTS = ['page_viewed', 'collection_viewed', 'search_submitted', 'product_viewed',
  'product_added_to_cart', 'cart_viewed', 'checkout_started', 'checkout_contact_info_submitted',
  'payment_info_submitted', 'checkout_completed'];

function send(name, event) {
  const doc = (event.context && event.context.document) || {};
  const body = {
    t: TOKEN, cid: event.clientId, ev: name,
    ref: doc.referrer || '', url: (doc.location && doc.location.href) || '',
  };
  if (name === 'checkout_completed') {
    const price = event.data && event.data.checkout && event.data.checkout.totalPrice;
    if (price && typeof price.amount === 'number') body.total = price.amount;
  }
  try {
    fetch(BEACON_URL, { method: 'POST', keepalive: true, mode: 'no-cors',
      headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(body) });
  } catch (e) { /* never break checkout */ }
}

EVENTS.forEach((name) => analytics.subscribe(name, (event) => send(name, event)));
