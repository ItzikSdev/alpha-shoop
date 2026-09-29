import {createHydrogenContext} from '@shopify/hydrogen';
import {AppSession} from '~/lib/session';
import {CART_QUERY_FRAGMENT} from '~/lib/fragments';

// Define the additional context object
const additionalContext = {
  // Additional context for custom properties, CMS clients, 3P SDKs, etc.
  // These will be available as both context.propertyName and context.get(propertyContext)
  // Example of complex objects that could be added:
  // cms: await createCMSClient(env),
  // reviews: await createReviewsClient(env),
};

/**
 * Creates Hydrogen context for React Router 7.9.x
 * Returns HydrogenRouterContextProvider with hybrid access patterns
 * @param {Request} request
 * @param {Env} env
 * @param {ExecutionContext} executionContext
 */
export async function createHydrogenRouterContext(
  request,
  env,
  executionContext,
) {
  /**
   * Open a cache instance in the worker and a custom session instance.
   */
  if (!env?.SESSION_SECRET) {
    throw new Error('SESSION_SECRET environment variable is not set');
  }

  const waitUntil = executionContext.waitUntil.bind(executionContext);
  const [cache, session] = await Promise.all([
    caches.open('hydrogen'),
    AppSession.init(request, [env.SESSION_SECRET]),
  ]);

  // The Oxygen-injected PRIVATE_STOREFRONT_API_TOKEN cannot read metafields: it
  // returns null for EVERY `metafield(...)` field (reviews, review_photos,
  // size_guide) while all other product data resolves normally — so the failure
  // is silent, and the size guide had been dead in production because of it.
  // Verified 2026-09-11: the same query with PUBLIC_STOREFRONT_API_TOKEN returns
  // those metafields in full. Hydrogen prefers the private token whenever it is
  // present, so withholding it is what forces the working path.
  // Proper fix is to grant that token `unauthenticated_read_metafields` in the
  // Hydrogen/Oxygen storefront settings, then drop these two lines.
  const {PRIVATE_STOREFRONT_API_TOKEN: _lacksMetafieldScope, ...envPublicTokenOnly} = env;

  const hydrogenContext = createHydrogenContext(
    {
      env: envPublicTokenOnly,
      request,
      cache,
      waitUntil,
      session,
      // Or detect from URL path based on locale subpath, cookies, or any other strategy
      i18n: {language: 'EN', country: 'US'},
      cart: {
        queryFragment: CART_QUERY_FRAGMENT,
      },
    },
    additionalContext,
  );

  return hydrogenContext;
}

/** @typedef {Class<additionalContext>} AdditionalContextType */

/** @typedef {import('storefrontapi.generated').CartApiQueryFragment} CartApiQueryFragment */
