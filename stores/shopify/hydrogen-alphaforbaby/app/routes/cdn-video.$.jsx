/**
 * Same-origin proxy for the shop's demo product videos.
 *
 * Background (found 2026-09-28): `product.media.nodes[].sources[].url` comes
 * back from the Storefront API using the "Online Store" sales channel's own
 * primary domain (checkout.alphaforbaby.com) for its `/cdn/shop/videos/...`
 * path, not `cdn.shopify.com`. That domain isn't in this site's CSP
 * `media-src` at all, so a `<video src="https://checkout.alphaforbaby.com/...">`
 * is flat-out rejected by Chrome ("Media load rejected by URL safety
 * check" — a CSP media-src violation, not an actual network/CORS problem;
 * the URL itself returns a clean 200 with `access-control-allow-origin: *`
 * when fetched directly). Pointing at `kgg8n0-k0.myshopify.com` instead
 * doesn't fix it either: that host IS listed in media-src
 * (`https://*.myshopify.com`), and a plain `fetch()` to it succeeds fine
 * (206 partial content, correct headers) — but a live `<video src>` to that
 * same URL still just hangs at readyState 0 with no error event, which
 * looks like a Chromium quirk in how <video>/<audio> evaluate a wildcard
 * media-src match. `'self'` is the only source in that directive that is
 * unambiguous, so instead of fighting the wildcard we proxy the bytes
 * through our own domain here.
 *
 * Route: /cdn-video/<anything after /cdn/shop/videos/> — e.g. the product
 * page rewrites `.../cdn/shop/videos/c/vp/<id>/<file>.mp4` to
 * `/cdn-video/c/vp/<id>/<file>.mp4` before handing it to <video src>.
 * Forwards the Range header both ways so seeking/scrubbing still works.
 */

const SHOP_MEDIA_ORIGIN = 'https://kgg8n0-k0.myshopify.com';

/** Only forward-slash-separated path segments of the shape Shopify's video
 * CDN actually uses — blocks this from being turned into an open proxy for
 * an arbitrary URL. */
const SAFE_PATH = /^[\w-]+(\/[\w.-]+)*$/;

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, params}) {
  const path = params['*'] || '';
  if (!SAFE_PATH.test(path)) {
    return new Response('Not found', {status: 404});
  }

  const upstreamUrl = `${SHOP_MEDIA_ORIGIN}/cdn/shop/videos/${path}`;
  const range = request.headers.get('Range');

  const upstreamResponse = await fetch(upstreamUrl, {
    headers: range ? {Range: range} : undefined,
  });

  if (!upstreamResponse.ok && upstreamResponse.status !== 206) {
    return new Response('Not found', {status: 404});
  }

  const headers = new Headers();
  headers.set(
    'Content-Type',
    upstreamResponse.headers.get('Content-Type') || 'video/mp4',
  );
  headers.set('Accept-Ranges', 'bytes');
  headers.set('Cache-Control', 'public, max-age=31536000, immutable');
  const contentRange = upstreamResponse.headers.get('Content-Range');
  if (contentRange) headers.set('Content-Range', contentRange);
  const contentLength = upstreamResponse.headers.get('Content-Length');
  if (contentLength) headers.set('Content-Length', contentLength);

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers,
  });
}

/** @typedef {import('./+types/cdn-video.$').Route} Route */
