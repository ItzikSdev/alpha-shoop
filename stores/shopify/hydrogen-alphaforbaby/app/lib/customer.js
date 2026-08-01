import {redirect} from 'react-router';
import {
  CUSTOMER_ACCESS_TOKEN_CREATE_MUTATION,
  CUSTOMER_CREATE_MUTATION,
  CUSTOMER_QUERY,
} from '~/graphql/customer/CustomerAuth';

/**
 * Custom (classic Storefront API) customer session helpers.
 *
 * This replaces the hosted OAuth Customer Account API client
 * (`context.customerAccount`), which redirects sign-in through
 * `shop.primaryDomain` — the Online Store channel's domain
 * (kgg8n0-k0.myshopify.com's linked domain), not this Hydrogen channel's
 * domain (alphaforbaby.com). That's a confirmed Shopify platform quirk for
 * headless/multi-channel setups with no Admin API or config-level fix.
 *
 * `customerAccessTokenCreate` (classic customer accounts, still supported by
 * the Storefront API for headless/Hydrogen storefronts) never leaves this
 * site, so it sidesteps the domain issue entirely. The resulting access
 * token is stored inside the app's existing signed, httpOnly session cookie
 * (see ~/lib/session.js) under the key below — no separate cookie needed.
 */
export const CUSTOMER_ACCESS_TOKEN_SESSION_KEY = 'customerAccessToken';

/**
 * @param {AppSession} session
 * @returns {{accessToken: string, expiresAt: string} | null}
 */
function readTokenPayload(session) {
  const payload = session.get(CUSTOMER_ACCESS_TOKEN_SESSION_KEY);
  if (!payload?.accessToken) return null;
  if (payload.expiresAt && new Date(payload.expiresAt).getTime() <= Date.now()) {
    return null;
  }
  return payload;
}

/**
 * @param {AppSession} session
 */
export function getCustomerAccessToken(session) {
  return readTokenPayload(session)?.accessToken ?? null;
}

/**
 * Synchronous, no-network check used for header/UI state (e.g. the account
 * icon). Does not verify the token against the Storefront API — just that a
 * non-expired token is present in the session.
 * @param {AppSession} session
 */
export function isLoggedIn(session) {
  return Boolean(readTokenPayload(session));
}

/**
 * @param {AppSession} session
 * @param {{accessToken: string, expiresAt: string}} token
 */
export function setCustomerAccessToken(session, token) {
  session.set(CUSTOMER_ACCESS_TOKEN_SESSION_KEY, token);
}

/**
 * @param {AppSession} session
 */
export function clearCustomerAccessToken(session) {
  session.unset(CUSTOMER_ACCESS_TOKEN_SESSION_KEY);
}

/**
 * Signs a customer in against the Storefront API's `customerAccessTokenCreate`
 * mutation. Throws a real Error (surfacing the Storefront API's own message)
 * on bad credentials so the login form can display it.
 *
 * Note: `storefront.query`/`.mutate` return the GraphQL `data` payload
 * directly (and throw on transport/GraphQL-level errors) — unlike the old
 * OAuth `customerAccount.query/mutate`, which returned a `{data, errors}`
 * tuple. Business-logic errors (bad password, etc.) show up as
 * `customerUserErrors` inside the returned data, not as thrown errors.
 * @param {{storefront: Storefront}} context
 * @param {{email: string, password: string}} credentials
 */
export async function loginWithPassword({storefront}, {email, password}) {
  const data = await storefront.mutate(CUSTOMER_ACCESS_TOKEN_CREATE_MUTATION, {
    variables: {input: {email, password}},
  });

  const userErrors = data?.customerAccessTokenCreate?.customerUserErrors;
  if (userErrors?.length) {
    throw new Error(userErrors[0].message);
  }

  const token = data?.customerAccessTokenCreate?.customerAccessToken;
  if (!token?.accessToken) {
    throw new Error('Sign-in failed. Please try again.');
  }

  return token;
}

/**
 * Creates a new customer via the Storefront API's `customerCreate` mutation,
 * then signs them in immediately (Shopify does not return an access token
 * from customerCreate itself — a separate customerAccessTokenCreate call is
 * required right after).
 * @param {{storefront: Storefront}} context
 * @param {{email: string, password: string, firstName?: string, lastName?: string}} input
 */
export async function registerCustomer({storefront}, input) {
  const data = await storefront.mutate(CUSTOMER_CREATE_MUTATION, {
    variables: {input},
  });

  const userErrors = data?.customerCreate?.customerUserErrors;
  if (userErrors?.length) {
    throw new Error(userErrors[0].message);
  }
  if (!data?.customerCreate?.customer) {
    throw new Error('Could not create account. Please try again.');
  }

  return loginWithPassword({storefront}, {email: input.email, password: input.password});
}

/**
 * Fetches the logged-in customer from the Storefront API using the token
 * stored in the session. Clears the token and returns null if it's missing,
 * invalid, or expired (Storefront API returns no error, just `customer: null`,
 * for a bad/expired token).
 * @param {{storefront: Storefront, session: AppSession}} context
 */
export async function getLoggedInCustomer({storefront, session}) {
  const accessToken = getCustomerAccessToken(session);
  if (!accessToken) return null;

  const data = await storefront.query(CUSTOMER_QUERY, {
    variables: {
      customerAccessToken: accessToken,
      language: storefront.i18n?.language,
    },
  });

  if (!data?.customer) {
    clearCustomerAccessToken(session);
    return null;
  }

  return data.customer;
}

/**
 * Requires a logged-in customer for a route loader/action, redirecting to
 * the custom login route (preserving the original destination via
 * ?redirect=) if there's no valid session token.
 *
 * Note: doesn't need to attach a Set-Cookie header itself — server.js
 * commits `context.session` onto whatever response goes out (including a
 * thrown redirect) whenever `session.isPending` is true, which
 * `clearCustomerAccessToken` above already sets.
 * @param {{storefront: Storefront, session: AppSession}} context
 * @param {Request} request
 */
export async function requireCustomer(context, request) {
  const customer = await getLoggedInCustomer(context);
  if (!customer) {
    const {pathname, search} = new URL(request.url);
    const params = new URLSearchParams({redirect: pathname + search});
    throw redirect(`/account/login?${params.toString()}`);
  }
  return customer;
}

/** @typedef {import('@shopify/hydrogen').Storefront} Storefront */
/** @typedef {import('~/lib/session').AppSession} AppSession */
