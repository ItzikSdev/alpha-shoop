import {redirect} from 'react-router';
import {hashPassword, verifyPassword, sha256Hex} from '~/lib/password';
import {shopifyAdminQuery} from '~/lib/shopifyAdmin';
import {
  CUSTOMER_BY_EMAIL_QUERY,
  CUSTOMER_BY_ID_QUERY,
  CUSTOMER_CREATE_ADMIN_MUTATION,
  CUSTOMER_UPDATE_ADMIN_MUTATION,
  METAFIELDS_SET_MUTATION,
  CUSTOMER_ADDRESS_CREATE_MUTATION,
  CUSTOMER_ADDRESS_UPDATE_MUTATION,
  CUSTOMER_ADDRESS_DELETE_MUTATION,
  CUSTOMER_ORDERS_ADMIN_QUERY,
  ORDER_BY_ID_ADMIN_QUERY,
} from '~/graphql/customer/CustomerAdmin';

/**
 * Independent (non-Shopify-hosted) customer identity system.
 *
 * WHY: Shopify's hosted OAuth Customer Account API redirects sign-in through
 * `shop.primaryDomain` (the Online Store channel's domain,
 * kgg8n0-k0.myshopify.com), never this Hydrogen channel's alphaforbaby.com —
 * a confirmed platform quirk with no config fix. The classic Storefront API
 * (`customerAccessTokenCreate`) looked like a workaround, but this shop has
 * Classic customer accounts DISABLED at the platform level
 * (`shop.customerAccounts === "DISABLED"`), so `customerCreate` succeeds but
 * the resulting account requires email verification, and Shopify's own
 * activation/login links redirect through shopify.com/authentication/... —
 * the same off-domain problem one level deeper. Neither of Shopify's own
 * customer-login systems can be used as the auth mechanism on this shop on
 * the Basic plan.
 *
 * WHAT WE DO INSTEAD: we run our own password hashing (app/lib/password.js,
 * PBKDF2 via Web Crypto) and our own session (app/lib/session.js, unchanged
 * — only what we store in it changes). Shopify Customer records are still
 * created/read via the ADMIN API (not Storefront), purely as CRM/order data
 * so orders, addresses, and profile info stay visible in Shopify admin and
 * tied to checkout — but Shopify's login/activation/password system itself
 * is never touched. All three auth methods (password, Google, Apple)
 * converge on one session shape: `session.set('customerId', adminCustomerGid)`.
 * Every /account/* page reads customer data via the Admin API using that id.
 *
 * Our password hash (and, informationally, OAuth provider subject ids) are
 * stored as private Admin-only metafields under the `custom_auth` namespace
 * — see app/graphql/customer/CustomerAdmin.js for the exact fields. These
 * are only ever read/written from server-side loaders/actions via
 * shopifyAdminQuery (which itself only runs with a private, non-PUBLIC_ env
 * var) — never sent to the client.
 */
export const CUSTOMER_ID_SESSION_KEY = 'customerId';

// ---------------------------------------------------------------------------
// Session helpers
// ---------------------------------------------------------------------------

/**
 * Synchronous, no-network check used for header/UI state (e.g. the account
 * icon). Just checks a session key is present — account routes independently
 * re-verify by fetching the customer via requireCustomer().
 * @param {AppSession} session
 */
export function isLoggedIn(session) {
  return Boolean(session.get(CUSTOMER_ID_SESSION_KEY));
}

/** @param {AppSession} session */
export function getSessionCustomerId(session) {
  return session.get(CUSTOMER_ID_SESSION_KEY) ?? null;
}

/**
 * @param {AppSession} session
 * @param {string} customerGid e.g. "gid://shopify/Customer/1234567890"
 */
export function setSessionCustomerId(session, customerGid) {
  session.set(CUSTOMER_ID_SESSION_KEY, customerGid);
}

/** @param {AppSession} session */
export function clearSessionCustomerId(session) {
  session.unset(CUSTOMER_ID_SESSION_KEY);
}

/** @param {Request} request */
function redirectToLogin(request) {
  const {pathname, search} = new URL(request.url);
  const params = new URLSearchParams({redirect: pathname + search});
  return redirect(`/account/login?${params.toString()}`);
}

/**
 * Requires a logged-in customer for a route loader/action, redirecting to
 * the login route (preserving the original destination via ?redirect=) if
 * there's no session id, or if the id no longer resolves to a real
 * customer (deleted in Shopify admin, etc).
 * @param {{env: Env, session: AppSession}} context
 * @param {Request} request
 */
export async function requireCustomer(context, request) {
  const customerId = getSessionCustomerId(context.session);
  if (!customerId) {
    throw redirectToLogin(request);
  }
  const customer = await getCustomerById(context.env, customerId);
  if (!customer) {
    clearSessionCustomerId(context.session);
    throw redirectToLogin(request);
  }
  return customer;
}

// ---------------------------------------------------------------------------
// Admin API customer read/write helpers
// ---------------------------------------------------------------------------

/**
 * Pulls the `custom_auth.*` metafield values out into a `_auth` sub-object
 * and strips the raw metafield fields from the top level, so callers get a
 * clean customer object plus an explicit, hard-to-misuse home for secrets.
 */
function shapeCustomer(customer) {
  if (!customer) return null;
  const {
    passwordHash,
    googleSub,
    appleSub,
    resetTokenHash,
    resetTokenExpires,
    addressesV2,
    ...rest
  } = customer;
  return {
    ...rest,
    // Admin API's paginated `addressesV2` connection flattened into a plain
    // array — matches the shape the (already-built) addresses UI expects.
    addresses: addressesV2?.nodes ?? [],
    _auth: {
      passwordHash: passwordHash?.value ?? null,
      googleSub: googleSub?.value ?? null,
      appleSub: appleSub?.value ?? null,
      resetTokenHash: resetTokenHash?.value ?? null,
      resetTokenExpires: resetTokenExpires?.value ?? null,
    },
  };
}

/**
 * Exact-match lookup by email via `customerByIdentifier` (not the fuzzy
 * `customers(query:)` search) — used by login, register (duplicate check),
 * and OAuth find-or-create.
 * @param {Env} env
 * @param {string} email
 */
export async function findCustomerByEmail(env, email) {
  const normalized = email.trim().toLowerCase();
  const data = await shopifyAdminQuery(env, CUSTOMER_BY_EMAIL_QUERY, {
    identifier: {emailAddress: normalized},
  });
  return shapeCustomer(data?.customerByIdentifier);
}

/**
 * @param {Env} env
 * @param {string} customerGid
 */
export async function getCustomerById(env, customerGid) {
  if (!customerGid) return null;
  const data = await shopifyAdminQuery(env, CUSTOMER_BY_ID_QUERY, {
    id: customerGid,
  });
  return shapeCustomer(data?.customer);
}

/**
 * @param {Env} env
 * @param {string} customerGid
 * @param {Record<string, string | null | undefined>} fields keys are the
 *   metafield `key` under the `custom_auth` namespace, e.g. `{password_hash: '...'}`
 */
async function setAuthMetafields(env, customerGid, fields) {
  const metafields = Object.entries(fields)
    .filter(([, value]) => value != null)
    .map(([key, value]) => ({
      ownerId: customerGid,
      namespace: 'custom_auth',
      key,
      type: 'single_line_text_field',
      value: String(value),
    }));
  if (!metafields.length) return;

  const data = await shopifyAdminQuery(env, METAFIELDS_SET_MUTATION, {
    metafields,
  });
  const errors = data?.metafieldsSet?.userErrors;
  if (errors?.length) {
    throw new Error(errors[0].message);
  }
}

/**
 * Creates a Shopify Admin customer + our password-hash metafield in one
 * mutation. `customerCreate` (Admin API) never sends an activation/invite
 * email itself — that only happens via the separate
 * `customerSendAccountInviteEmail` mutation, which this app never calls —
 * so this is safe to do without the customer receiving any Shopify email.
 * @param {Env} env
 * @param {{email: string, password: string, firstName?: string, lastName?: string}} input
 */
export async function createCustomerAccount(env, {email, password, firstName, lastName}) {
  const normalized = email.trim().toLowerCase();
  const passwordHash = await hashPassword(password);

  const data = await shopifyAdminQuery(env, CUSTOMER_CREATE_ADMIN_MUTATION, {
    input: {
      email: normalized,
      firstName: firstName || undefined,
      lastName: lastName || undefined,
      metafields: [
        {
          namespace: 'custom_auth',
          key: 'password_hash',
          type: 'single_line_text_field',
          value: passwordHash,
        },
      ],
    },
  });

  const errors = data?.customerCreate?.userErrors;
  if (errors?.length) {
    throw new Error(errors[0].message);
  }
  const customer = shapeCustomer(data?.customerCreate?.customer);
  if (!customer) {
    throw new Error('Could not create account. Please try again.');
  }
  return customer;
}

/**
 * Handles the guest-checkout-then-register case: Shopify auto-creates a
 * Customer record for the email used at checkout, so a later registration
 * attempt with that same email would otherwise hit "account already
 * exists" — a dead end, since that record has no password set and the
 * shopper has no way to log into it. If the existing customer genuinely
 * has no password_hash yet, this "claims" it by setting one (and filling
 * in any missing name) instead of treating it as a conflict. If it DOES
 * already have a password, this is a real conflict and the caller should
 * still refuse.
 * @param {Env} env
 * @param {ReturnType<typeof shapeCustomer>} existingCustomer
 * @param {{password: string, firstName?: string, lastName?: string}} input
 */
export async function claimGuestCustomerAccount(env, existingCustomer, {password, firstName, lastName}) {
  const passwordHash = await hashPassword(password);

  const fields = {};
  if (firstName && !existingCustomer.firstName) fields.firstName = firstName;
  if (lastName && !existingCustomer.lastName) fields.lastName = lastName;
  if (Object.keys(fields).length) {
    await updateCustomerProfile(env, existingCustomer.id, fields);
  }

  await setAuthMetafields(env, existingCustomer.id, {password_hash: passwordHash});

  return getCustomerById(env, existingCustomer.id);
}

/**
 * @param {{_auth: {passwordHash: string | null}} | null} customer
 * @param {string} password
 */
export async function verifyCustomerPassword(customer, password) {
  if (!customer?._auth?.passwordHash) return false;
  return verifyPassword(password, customer._auth.passwordHash);
}

const RESET_TOKEN_TTL_MS = 30 * 60 * 1000; // 30 minutes

/**
 * Generates a one-time password-reset token for a customer (if the email
 * matches an account) and stores only its SHA-256 hash + expiry, never the
 * raw token itself — mirrors how passwords are never stored in plaintext.
 * Returns `null` if no account matches, WITHOUT the caller leaking that
 * distinction to the end user (see account_.recover.jsx: always shows the
 * same generic confirmation regardless of this return value).
 * @param {Env} env
 * @param {string} email
 * @returns {Promise<{customer: object, token: string} | null>}
 */
export async function createPasswordResetToken(env, email) {
  const customer = await findCustomerByEmail(env, email);
  if (!customer) return null;

  const token = crypto.randomUUID().replace(/-/g, '') + crypto.randomUUID().replace(/-/g, '');
  const tokenHash = await sha256Hex(token);
  const expiresAt = new Date(Date.now() + RESET_TOKEN_TTL_MS).toISOString();

  await setAuthMetafields(env, customer.id, {
    reset_token_hash: tokenHash,
    reset_token_expires: expiresAt,
  });

  return {customer, token};
}

/**
 * Verifies a reset token (by re-hashing and comparing) and, if valid and
 * unexpired, sets a new password hash and clears the token so it can't be
 * reused. Generic errors only — never reveals which specific check failed.
 * @param {Env} env
 * @param {{email: string, token: string, newPassword: string}} input
 */
export async function resetPasswordWithToken(env, {email, token, newPassword}) {
  const customer = await findCustomerByEmail(env, email);
  const genericError = 'This reset link is invalid or has expired.';
  if (!customer?._auth?.resetTokenHash || !customer?._auth?.resetTokenExpires) {
    throw new Error(genericError);
  }

  const expiresAt = new Date(customer._auth.resetTokenExpires).getTime();
  if (!Number.isFinite(expiresAt) || Date.now() > expiresAt) {
    throw new Error(genericError);
  }

  const providedHash = await sha256Hex(token);
  if (providedHash !== customer._auth.resetTokenHash) {
    throw new Error(genericError);
  }

  const passwordHash = await hashPassword(newPassword);
  await setAuthMetafields(env, customer.id, {
    password_hash: passwordHash,
    // Admin API's metafieldsSet rejects blank string values ("Value can't
    // be blank"), so the token can't just be cleared to `''`. Instead:
    // stamp expiry into the past (fails the expiry check above regardless
    // of the hash) and overwrite the hash with a placeholder that can never
    // equal a real sha256Hex digest — both make the token permanently
    // unusable without needing a metafieldsDelete round-trip.
    reset_token_hash: 'used',
    reset_token_expires: new Date(0).toISOString(),
  });

  return customer;
}

/**
 * Find-or-create for OAuth sign-in (Google/Apple).
 *
 * Matching strategy: BY EMAIL, not by the provider's `sub` id. Both
 * providers only hand this app a verified ID token after they've
 * authenticated the user themselves, so trusting the token's email address
 * is standard practice for "Sign in with X" integrations. The provider
 * `sub` is still recorded as an informational `custom_auth.*_sub` metafield
 * (useful context if support ever needs to confirm which provider a
 * customer used), but it is NOT the lookup key: the Admin API's
 * `customerByIdentifier` only matches on id/email/phone, and the only way
 * to search by an arbitrary metafield value is the fuzzy `customers(query:)`
 * search, which isn't reliable for exact identity matching. Email-matching
 * is simpler and was judged good enough for a Basic-plan store with one
 * checkout identity per email; revisit if this ever needs to support a
 * customer changing the email on one provider but not another.
 * @param {Env} env
 * @param {{email: string, firstName?: string, lastName?: string, provider: 'google'|'apple', subjectId?: string}} input
 */
export async function findOrCreateCustomerForOAuth(
  env,
  {email, firstName, lastName, provider, subjectId},
) {
  let customer = await findCustomerByEmail(env, email);

  if (!customer) {
    const data = await shopifyAdminQuery(env, CUSTOMER_CREATE_ADMIN_MUTATION, {
      input: {
        email: email.trim().toLowerCase(),
        firstName: firstName || undefined,
        lastName: lastName || undefined,
      },
    });
    const errors = data?.customerCreate?.userErrors;
    if (errors?.length) {
      throw new Error(errors[0].message);
    }
    customer = shapeCustomer(data?.customerCreate?.customer);
  }

  if (!customer) {
    throw new Error('Could not create account.');
  }

  const subKey = provider === 'google' ? 'googleSub' : 'appleSub';
  if (subjectId && customer._auth[subKey] !== subjectId) {
    await setAuthMetafields(env, customer.id, {
      [provider === 'google' ? 'google_sub' : 'apple_sub']: subjectId,
    });
  }

  return customer;
}

/**
 * @param {Env} env
 * @param {string} customerGid
 * @param {{firstName?: string, lastName?: string, phone?: string}} fields
 */
export async function updateCustomerProfile(env, customerGid, fields) {
  const input = {id: customerGid};
  if (fields.firstName != null) input.firstName = fields.firstName;
  if (fields.lastName != null) input.lastName = fields.lastName;
  if (fields.phone != null) input.phone = fields.phone;

  const data = await shopifyAdminQuery(env, CUSTOMER_UPDATE_ADMIN_MUTATION, {
    input,
  });
  const errors = data?.customerUpdate?.userErrors;
  if (errors?.length) {
    throw new Error(errors[0].message);
  }
  return shapeCustomer(data?.customerUpdate?.customer);
}

// ---------------------------------------------------------------------------
// Addresses (Admin API)
// ---------------------------------------------------------------------------

/**
 * @param {Env} env
 * @param {string} customerGid
 * @param {Record<string, string>} address
 * @param {boolean} [setAsDefault]
 */
export async function createCustomerAddress(env, customerGid, address, setAsDefault = false) {
  const data = await shopifyAdminQuery(env, CUSTOMER_ADDRESS_CREATE_MUTATION, {
    customerId: customerGid,
    address,
    setAsDefault,
  });
  const errors = data?.customerAddressCreate?.userErrors;
  if (errors?.length) throw new Error(errors[0].message);
  return data?.customerAddressCreate?.address;
}

/**
 * @param {Env} env
 * @param {string} customerGid
 * @param {string} addressId
 * @param {Record<string, string>} address
 * @param {boolean} [setAsDefault]
 */
export async function updateCustomerAddress(env, customerGid, addressId, address, setAsDefault = false) {
  const data = await shopifyAdminQuery(env, CUSTOMER_ADDRESS_UPDATE_MUTATION, {
    customerId: customerGid,
    addressId,
    address,
    setAsDefault,
  });
  const errors = data?.customerAddressUpdate?.userErrors;
  if (errors?.length) throw new Error(errors[0].message);
  return data?.customerAddressUpdate?.address;
}

/**
 * @param {Env} env
 * @param {string} customerGid
 * @param {string} addressId
 */
export async function deleteCustomerAddress(env, customerGid, addressId) {
  const data = await shopifyAdminQuery(env, CUSTOMER_ADDRESS_DELETE_MUTATION, {
    customerId: customerGid,
    addressId,
  });
  const errors = data?.customerAddressDelete?.userErrors;
  if (errors?.length) throw new Error(errors[0].message);
  return data?.customerAddressDelete?.deletedAddressId;
}

// ---------------------------------------------------------------------------
// Orders (Admin API)
// ---------------------------------------------------------------------------

function numericIdFromGid(gid) {
  return gid?.split('/').pop();
}

/**
 * @param {Env} env
 * @param {string} customerGid
 * @param {{searchQuery?: string, paginationVariables?: Record<string, unknown>}} [options]
 */
export async function getCustomerOrders(env, customerGid, options = {}) {
  const {searchQuery, paginationVariables = {}} = options;
  const parts = [`customer_id:${numericIdFromGid(customerGid)}`];
  if (searchQuery) parts.push(searchQuery);

  const data = await shopifyAdminQuery(env, CUSTOMER_ORDERS_ADMIN_QUERY, {
    query: parts.join(' AND '),
    ...paginationVariables,
  });
  return data?.orders;
}

/**
 * Fetches a single order by its Admin GID and verifies it belongs to the
 * given customer before returning it, so one customer can never view
 * another's order by guessing/tampering with the id in the URL.
 * @param {Env} env
 * @param {string} orderGid
 * @param {string} customerGid
 */
export async function getOrderById(env, orderGid, customerGid) {
  const data = await shopifyAdminQuery(env, ORDER_BY_ID_ADMIN_QUERY, {
    id: orderGid,
  });
  const order = data?.order;
  if (!order) return null;
  if (order.customer?.id !== customerGid) return null;
  return order;
}

/** @typedef {import('~/lib/session').AppSession} AppSession */
/** @typedef {import('@shopify/hydrogen').HydrogenEnv} Env */
