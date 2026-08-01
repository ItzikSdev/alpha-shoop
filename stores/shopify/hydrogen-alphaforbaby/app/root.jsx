import {ThemeProvider} from '@material-tailwind/react';
import {Analytics, getShopAnalytics, useNonce} from '@shopify/hydrogen';
import {
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
import {isLoggedIn} from './lib/customer';

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
    ...icons,
  ];
}

/**
 * @param {Route.LoaderArgs} args
 */
export async function loader(args) {
  // Start fetching non-critical data without blocking time to first byte
  const deferredData = loadDeferredData(args);

  // Await the critical data required to render initial state of the page
  const criticalData = await loadCriticalData(args);

  const {storefront, env} = args.context;

  return {
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
      country: args.context.storefront.i18n.country,
      language: args.context.storefront.i18n.language,
    },
  };
}

/**
 * Load data necessary for rendering content above the fold. This is the critical data
 * needed to render the page. If it's unavailable, the whole page should 400 or 500 error.
 * @param {Route.LoaderArgs}
 */
async function loadCriticalData({context}) {
  // Nav is hardcoded (owner NAV RULE: Baby Boys / Baby Girls / Unisex), so we
  // don't depend on Shopify online-store menus here.
  return {};
}

/**
 * Load data for rendering content below the fold. This data is deferred and will be
 * fetched after the initial page load. If it's unavailable, the page should still 200.
 * Make sure to not throw any errors here, as it will cause the page to 500.
 * @param {Route.LoaderArgs}
 */
function loadDeferredData({context}) {
  const {session, cart} = context;
  return {
    cart: cart.get(),
    // Session-only check (no Storefront API round trip) — just used to pick
    // which account icon/label to render. Account routes independently
    // verify the token against the Storefront API via requireCustomer().
    isLoggedIn: Promise.resolve(isLoggedIn(session)),
  };
}

/**
 * @param {{children?: React.ReactNode}}
 */
export function Layout({children}) {
  const nonce = useNonce();

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
                var target = new URL(canonical).hostname;
                if (window.location.hostname !== target) {
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
