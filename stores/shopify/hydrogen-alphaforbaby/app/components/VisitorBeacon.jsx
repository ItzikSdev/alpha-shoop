import {useEffect} from 'react';
import {useAnalytics} from '@shopify/hydrogen';

/**
 * Live-visitor beacon for the Alpha Shoop 3D office.
 *
 * Why this exists: Shopify Custom Pixels (Customer events) do not run on a
 * Hydrogen/Oxygen storefront — there is no web-pixels sandbox on these pages —
 * so real visitors never reached the office's "store building". This listens to
 * Hydrogen's own analytics bus (same as MetaPixel) and posts anonymous, non-PII
 * events to the beacon (Cloudflare Tunnel → beacon service → Redis).
 *
 * Sent: a random per-tab id (sessionStorage, not a cookie, gone when the tab
 * closes), event name, referrer, page URL (for utm_source), and nothing else.
 * Never: name, email, address, IP, cart contents. Purchase is NOT sent from
 * here (checkout is hosted by Shopify); the Shopify checkout pixel covers it.
 *
 * Inert until `visitorBeaconUrl` AND `visitorBeaconToken` are set in
 * app/theme.config.json. The token only filters noise; it ships in the page.
 * No visual output — this component renders nothing.
 */
const EVENT_MAP = {
  page_viewed: 'page_viewed',
  collection_viewed: 'collection_viewed',
  search_viewed: 'search_submitted',
  product_viewed: 'product_viewed',
  product_added_to_cart: 'product_added_to_cart',
  cart_viewed: 'cart_viewed',
};

function visitorId() {
  try {
    let id = window.sessionStorage.getItem('_av');
    if (!id) {
      id =
        (window.crypto?.randomUUID && window.crypto.randomUUID()) ||
        `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      window.sessionStorage.setItem('_av', id);
    }
    return id;
  } catch {
    // storage blocked: fall back to a per-page-load id (still anonymous)
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }
}

export function VisitorBeacon({url, token}) {
  const {subscribe, register} = useAnalytics();
  const {ready} = register('VisitorBeacon');

  useEffect(() => {
    if (!url || !token || typeof window === 'undefined') {
      ready();
      return;
    }
    const cid = visitorId();
    const send = (ev) => {
      try {
        fetch(url, {
          method: 'POST',
          keepalive: true,
          mode: 'no-cors',
          headers: {'Content-Type': 'text/plain'},
          body: JSON.stringify({
            t: token,
            cid,
            ev,
            ref: document.referrer || '',
            url: window.location.href,
          }),
        }).catch(() => {});
      } catch {
        /* never break the storefront */
      }
    };
    Object.entries(EVENT_MAP).forEach(([hydrogenEvent, beaconEvent]) => {
      subscribe(hydrogenEvent, () => send(beaconEvent));
    });
    ready();
    // subscribe/register are stable for the provider's lifetime
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, token]);

  return null;
}
