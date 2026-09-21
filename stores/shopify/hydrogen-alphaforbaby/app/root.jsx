import {useEffect} from 'react';
import {ThemeProvider} from '@material-tailwind/react';
import {Analytics, getShopAnalytics, useNonce} from '@shopify/hydrogen';
import {
  data,
  Outlet,
  useRouteError,
  isRouteErrorResponse,
  Links,
  Meta,
  Scripts,
  ScrollRestoration,
  useRouteLoaderData,
} from 'react-router';
import resetStyles from './styles/reset.css?url';
import appStyles from './styles/app.css?url';
import {themeCss, config} from './lib/theme';
import {PageLayout} from './components/PageLayout';
import {isLoggedIn, getSessionCustomerId, getCustomerById} from './lib/customer';
import {reconcileCustomerCart} from './lib/cartSync';

/**
 * This is important to avoid re-fetching root queries on sub-navigations
 * @type {ShouldRevalidateFunction}
 */
export const shouldRevalidate = ({formMethod, currentUrl, nextUrl}) => {
  // revalidate when a mutation is performed e.g add to cart, login...
  if (formMethod && formMethod !== 'GET') return true;

  // revalidate when manually revalidating via useRevalidator
  if (currentUrl.toString() === nextUrl.toString()) return true;

  // Defaulting to no revalidation for root loader data to improve performance.
  // When using this feature, you risk your UI getting out of sync with your server.
  // Use with caution. If you are uncomfortable with this optimization, update the
  // line below to `return defaultShouldRevalidate` instead.
  // For more details see: https://remix.run/docs/en/main/route/should-revalidate
  return false;
};

/**
 * The main and reset stylesheets are added in the Layout component
 * to prevent a bug in development HMR updates.
 *
 * This avoids the "failed to execute 'insertBefore' on 'Node'" error
 * that occurs after editing and navigating to another page.
 *
 * It's a temporary fix until the issue is resolved.
 * https://github.com/remix-run/remix/issues/9242
 */
export function links() {
  // Favicons come from theme.config.json → favicons (all paths, no bundler import).
  const f = config.favicons || {};
  const icons = [];
  if (f.svg) icons.push({rel: 'icon', type: 'image/svg+xml', href: f.svg});
  if (f.png32)
    icons.push({rel: 'icon', type: 'image/png', sizes: '32x32', href: f.png32});
  if (f.appleTouch)
    icons.push({rel: 'apple-touch-icon', sizes: '180x180', href: f.appleTouch});
  if (f.png512)
    icons.push({rel: 'icon', type: 'image/png', sizes: '512x512', href: f.png512});
  return [
    {rel: 'preconnect', href: 'https://cdn.shopify.com'},
    {rel: 'preconnect', href: 'https://shop.app'},
    // Assistant (Google Fonts) — the approved fallback for the "Classical"
    // theme's FbTubicSans-Light face (licensed, not bundled here). Keep this
    // fallback rather than substituting a different font if FbTubicSans is
    // ever added later — see stores/shopify design handoff README.
    // Assistant is self-hosted from /public/fonts via @font-face in app.css.
    // The Google Fonts <link> that used to sit here was blocked by the CSP
    // (no fonts.googleapis.com in style-src, no font-src at all), so it never
    // loaded a single glyph — removed rather than whitelisted, so the font
    // cannot break again the next time the policy changes.
    {
      rel: 'preload', href: '/fonts/assistant-latin.woff2', as: 'font',
      type: 'font/woff2', crossOrigin: 'anonymous',
    },
    ...icons,
  ];
}

/**
 * @param {Route.LoaderArgs} args
 */
export async function loader(args) {
  const {context} = args;
  const {session, env, cart} = context;

  // Resolve the cart BEFORE the deferred/streamed data, so a logged-in
  // customer's saved cart (added on another device) can be reconciled here
  // — this is what feeds BOTH the header cart badge AND the slide-out cart
  // drawer (PageLayout's CartAside), which is how most shoppers actually
  // check their cart, not by navigating to the full /cart page (which has
  // its own independent reconciliation in routes/cart.jsx). Reconciling
  // needs an Admin API customer lookup, so this only adds latency for
  // logged-in requests — guests keep the original fully-deferred cart.get().
  let cartHeaders = new Headers();
  let cartData;
  if (isLoggedIn(session)) {
    const customerId = getSessionCustomerId(session);
    const customer = customerId ? await getCustomerById(env, customerId) : null;
    if (customer) {
      const reconciled = await reconcileCustomerCart({context, customer});
      cartHeaders = reconciled.headers;
      cartData = reconciled.cart;
    }
  }
  const cartPromise = cartData ? Promise.resolve(cartData) : cart.get();

  // Start fetching non-critical data without blocking time to first byte
  const deferredData = loadDeferredData(args, cartPromise);

  // Await the critical data required to render initial state of the page
  const criticalData = await loadCriticalData(args);

  const {storefront} = context;

  return data(
    {
      ...deferredData,
      ...criticalData,
      publicStoreDomain: env.PUBLIC_STORE_DOMAIN,
      shop: getShopAnalytics({
        storefront,
        publicStorefrontId: env.PUBLIC_STOREFRONT_ID,
      }),
      consent: {
        // Fallback to the store domain so a missing PUBLIC_CHECKOUT_DOMAIN in Oxygen
        // env doesn't crash the Analytics.Provider (which broke cart/menu clicks).
        checkoutDomain: env.PUBLIC_CHECKOUT_DOMAIN || env.PUBLIC_STORE_DOMAIN,
        storefrontAccessToken: env.PUBLIC_STOREFRONT_API_TOKEN,
        // OFF: the privacy banner requires Customer-Privacy config in Oxygen env and was
        // crashing Analytics.Provider on hydration → dead cart/menu clicks. Re-enable only
        // after configuring admin → Settings → Customer privacy + PUBLIC_CHECKOUT_DOMAIN.
        withPrivacyBanner: false,
        // localize the privacy banner
        country: storefront.i18n.country,
        language: storefront.i18n.language,
      },
    },
    {headers: cartHeaders},
  );
}

/**
 * Load data necessary for rendering content above the fold. This is the critical data
 * needed to render the page. If it's unavailable, the whole page should 400 or 500 error.
 * @param {Route.LoaderArgs}
 */
async function loadCriticalData({context}) {
  // Nav is hardcoded via app/theme.config.json's `nav` array (owner NAV RULE),
  // so we don't depend on Shopify online-store menus here.
  return {};
}

/**
 * Load data for rendering content below the fold. This data is deferred and will be
 * fetched after the initial page load. If it's unavailable, the page should still 200.
 * Make sure to not throw any errors here, as it will cause the page to 500.
 * @param {Route.LoaderArgs} args
 * @param {Promise<object|null>} cartPromise resolved (possibly reconciled) in loader() above
 */
function loadDeferredData({context}, cartPromise) {
  const {session} = context;
  return {
    cart: cartPromise,
    // Session-only check (no Storefront API round trip) — just used to pick
    // which account icon/label to render. Account routes independently
    // verify the token against the Storefront API via requireCustomer().
    isLoggedIn: Promise.resolve(isLoggedIn(session)),
  };
}

/**
 * @param {{children?: React.ReactNode}}
 */
/** Microsoft Clarity, loaded AFTER hydration.
 *  Its official snippet injects a <script> into <head> synchronously during
 *  parsing; React then hydrates against a <head> that has one more child than
 *  the server rendered, and reports a <title> mismatch. Running it in an effect
 *  sidesteps that entirely — same tracking, no pre-hydration DOM mutation. */
function useClarity(projectId) {
  useEffect(() => {
    if (!projectId || window.clarity) return;
    window.clarity =
      window.clarity || function () { (window.clarity.q = window.clarity.q || []).push(arguments); };
    const s = document.createElement('script');
    s.async = true;
    s.src = `https://www.clarity.ms/tag/${projectId}`;
    document.body.appendChild(s);
  }, [projectId]);
}

export function Layout({children}) {
  const nonce = useNonce();
  useClarity('y9evik4b8h');

  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <link rel="stylesheet" href={resetStyles}></link>
        <link rel="stylesheet" href={appStyles}></link>
        {/* Theme tokens (colors + font sizes) from app/theme.config.json → CSS vars */}
        <style
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{__html: themeCss()}}
        />
        {/* Redirect any non-canonical host (myshopify.com, .myshopify.dev previews,
            www, etc.) to the real brand domain from theme.config.json — keeps every
            entry point (search results, old links) landing on the canonical site. */}
        <script
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{
            __html: `(function(){
              var canonical = ${JSON.stringify(config.brand.canonicalDomain)};
              try {
                var host = window.location.hostname;
                var target = new URL(canonical).hostname;
                // Only bounce the hosts this was ever meant to catch: the raw
                // myshopify domain and a www variant. Everything else — localhost,
                // Oxygen preview deploys (*.myshopify.dev / *.shopifypreview.com),
                // any staging host — must be left alone, or a preview link
                // silently lands the viewer on production instead (which is
                // exactly how a "fixed" build kept appearing unfixed).
                var shouldRedirect =
                  /\.myshopify\.com$/.test(host) || host === 'www.' + target;
                if (shouldRedirect && host !== target) {
                  window.location.replace(canonical + window.location.pathname + window.location.search);
                }
              } catch (e) {}
            })();`,
          }}
        />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration nonce={nonce} />
        <Scripts nonce={nonce} />
      </body>
    </html>
  );
}

export default function App() {
  /** @type {RootLoader} */
  const data = useRouteLoaderData('root');

  if (!data) {
    return <Outlet />;
  }

  return (
    <ThemeProvider>
      <Analytics.Provider
        cart={data.cart}
        shop={data.shop}
        consent={data.consent}
      >
        <PageLayout {...data}>
          <Outlet />
        </PageLayout>
      </Analytics.Provider>
    </ThemeProvider>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();
  let errorMessage = 'Unknown error';
  let errorStatus = 500;

  if (isRouteErrorResponse(error)) {
    errorMessage = error?.data?.message ?? error.data;
    errorStatus = error.status;
  } else if (error instanceof Error) {
    errorMessage = error.message;
  }

  return (
    <div className="route-error">
      <h1>Oops</h1>
      <h2>{errorStatus}</h2>
      {errorMessage && (
        <fieldset>
          <pre>{errorMessage}</pre>
        </fieldset>
      )}
    </div>
  );
}

/** @typedef {LoaderReturnData} RootLoader */

/** @typedef {import('react-router').ShouldRevalidateFunction} ShouldRevalidateFunction */
/** @typedef {import('./+types/root').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
