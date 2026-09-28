import {useEffect} from 'react';
import {useAnalytics} from '@shopify/hydrogen';

/**
 * Meta (Facebook/Instagram) pixel for the Hydrogen storefront.
 *
 * Why this exists: until 2026-09-25 the storefront sent Meta nothing at all —
 * no fbq, no connect.facebook.net, not in the CSP either. Paid ads would have
 * run blind: Meta can't find buyers if it never sees a product view or an
 * add-to-cart. The Purchase event is NOT sent from here: checkout is hosted by
 * Shopify, and Purchase comes from the Facebook & Instagram sales channel's
 * pixel + Conversions API on checkout (Shopify admin → Facebook & Instagram →
 * Settings → Data sharing: Maximum). Sending it here too would double-count.
 *
 * Inert until `metaPixelId` is set in app/theme.config.json. A pixel id is a
 * public identifier (it ships in every page's HTML), not a secret.
 *
 * Events: PageView on every page, ViewContent on a product page, AddToCart on
 * add. It listens to Hydrogen's own analytics bus, so it sees exactly the
 * events Shopify's analytics sees — no second source of truth.
 */
export function MetaPixel({pixelId}) {
  const {subscribe, register} = useAnalytics();
  const {ready} = register('MetaPixel');

  useEffect(() => {
    if (!pixelId || typeof window === 'undefined') {
      ready();
      return;
    }
    // Standard Meta base code, run from an effect (not an inline <script>) so
    // it needs no CSP nonce; connect.facebook.net is allowed in entry.server.
    if (!window.fbq) {
      !(function (f, b, e, v, n, t, s) {
        if (f.fbq) return;
        n = f.fbq = function () {
          n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
        };
        if (!f._fbq) f._fbq = n;
        n.push = n; n.loaded = !0; n.version = '2.0'; n.queue = [];
        t = b.createElement(e); t.async = !0; t.src = v;
        s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
      })(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
      window.fbq('init', pixelId);
    }

    const money = (m) => Number(m?.amount || 0);
    subscribe('page_viewed', () => window.fbq('track', 'PageView'));
    subscribe('product_viewed', (data) => {
      const p = data?.products?.[0];
      if (!p) return;
      window.fbq('track', 'ViewContent', {
        content_ids: [String(p.variantId || p.id)],
        content_name: p.title,
        content_type: 'product',
        value: Number(p.price || 0),
        currency: data?.shop?.currency || 'USD',
      });
    });
    subscribe('product_added_to_cart', (data) => {
      const line = data?.currentLine;
      if (!line) return;
      const qty = line.quantity || 1;
      window.fbq('track', 'AddToCart', {
        content_ids: [String(line.merchandise?.id || '')],
        content_name: line.merchandise?.product?.title,
        content_type: 'product',
        value: money(line.cost?.totalAmount) || money(line.merchandise?.price) * qty,
        currency: line.cost?.totalAmount?.currencyCode || 'USD',
      });
    });
    ready();
    // subscribe/register are stable for the provider's lifetime
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pixelId]);

  return null;
}
