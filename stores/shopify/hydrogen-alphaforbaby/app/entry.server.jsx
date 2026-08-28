import {ServerRouter} from 'react-router';
import {isbot} from 'isbot';
import {renderToReadableStream} from 'react-dom/server';
import {createContentSecurityPolicy} from '@shopify/hydrogen';

/**
 * @param {Request} request
 * @param {number} responseStatusCode
 * @param {Headers} responseHeaders
 * @param {EntryContext} reactRouterContext
 * @param {HydrogenRouterContextProvider} context
 */
export default async function handleRequest(
  request,
  responseStatusCode,
  responseHeaders,
  reactRouterContext,
  context,
) {
  const {nonce, header, NonceProvider} = createContentSecurityPolicy({
    shop: {
      checkoutDomain: context.env.PUBLIC_CHECKOUT_DOMAIN,
      storeDomain: context.env.PUBLIC_STORE_DOMAIN,
    },
    // Reel's product-rotation videos are served from Shopify's own video CDN
    // (cdn.shopify.com/.../videos/...), which isn't covered by the default
    // policy — without this, the browser silently blocks the <video> element
    // ("media-src" falls back to "default-src 'self'" and refuses the load).
    mediaSrc: ["'self'", 'https://cdn.shopify.com', 'https://*.myshopify.com'],
    // Microsoft Clarity (2026-08-28): the root-layout snippet is nonce'd and
    // executes fine, but it then does document.createElement('script') with
    // src=clarity.ms — a DYNAMICALLY inserted script gets no nonce, so without
    // this it's silently blocked by the default script-src fallback (and its
    // own data-collection beacons blocked by connect-src) in every
    // CSP-respecting browser, not just Safari/ad-blockers. These two lists
    // replicate Hydrogen's existing computed defaults (visible live before
    // this change) plus clarity.ms — an override here REPLACES the default
    // for that directive, so the prior entries must stay, not just clarity.ms.
    scriptSrc: ["'self'", 'https://cdn.shopify.com', 'https://shopify.com', 'https://www.clarity.ms', 'https://*.clarity.ms'],
    connectSrc: [
      "'self'", 'https://cdn.shopify.com/', 'https://monorail-edge.shopifysvc.com',
      'https://alphaforbaby.com', 'https://kgg8n0-k0.myshopify.com',
      'https://www.clarity.ms', 'https://*.clarity.ms',
    ],
  });

  const body = await renderToReadableStream(
    <NonceProvider>
      <ServerRouter
        context={reactRouterContext}
        url={request.url}
        nonce={nonce}
      />
    </NonceProvider>,
    {
      nonce,
      signal: request.signal,
      onError(error) {
        console.error(error);
        responseStatusCode = 500;
      },
    },
  );

  if (isbot(request.headers.get('user-agent'))) {
    await body.allReady;
  }

  responseHeaders.set('Content-Type', 'text/html');
  responseHeaders.set('Content-Security-Policy', header);

  return new Response(body, {
    headers: responseHeaders,
    status: responseStatusCode,
  });
}

/** @typedef {import('@shopify/hydrogen').HydrogenRouterContextProvider} HydrogenRouterContextProvider */
/** @typedef {import('react-router').EntryContext} EntryContext */
