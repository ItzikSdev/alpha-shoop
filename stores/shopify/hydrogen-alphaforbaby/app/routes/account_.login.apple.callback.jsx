import {redirect} from 'react-router';
import {jwtVerify, createRemoteJWKSet, importPKCS8, SignJWT} from 'jose';
import {findOrCreateCustomerForOAuth, setSessionCustomerId} from '~/lib/customer';
import {reconcileCustomerCart, mergeHeaders} from '~/lib/cartSync';

const APPLE_JWKS = createRemoteJWKSet(new URL('https://appleid.apple.com/auth/keys'));

// Always cleared once read — see account_.login.apple.jsx for why this is a
// dedicated SameSite=None cookie rather than the main session.
const CLEAR_APPLE_OAUTH_COOKIE = 'apple_oauth=; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=0';

/**
 * @param {Request} request
 */
function readAppleOAuthCookie(request) {
  const cookieHeader = request.headers.get('Cookie') || '';
  const match = cookieHeader.match(/(?:^|;\s*)apple_oauth=([^;]+)/);
  if (!match) return null;
  try {
    return JSON.parse(decodeURIComponent(match[1]));
  } catch {
    return null;
  }
}

/**
 * @param {string} location
 * @param {Headers} [extraHeaders] e.g. a cart-id cookie from reconcileCustomerCart
 *   — merged in (not overwritten) since both are `Set-Cookie` headers.
 */
function redirectClearingAppleCookie(location, extraHeaders) {
  const headers = mergeHeaders(new Headers({'Set-Cookie': CLEAR_APPLE_OAUTH_COOKIE}), extraHeaders);
  return redirect(location, {headers});
}

/**
 * Generates Apple's required `client_secret` ourselves: a short-lived ES256
 * JWT signed with our Apple private key (APPLE_PRIVATE_KEY), NOT a static
 * secret — Apple's token endpoint expects a freshly-signed one per request
 * (or at least per some window; we mint a new one every time for simplicity).
 * @param {Env} env
 */
async function generateAppleClientSecret(env) {
  // .env files commonly store multi-line PEM keys with literal `\n`
  // sequences instead of real newlines — normalize either form.
  const pem = String(env.APPLE_PRIVATE_KEY || '').includes('\\n')
    ? String(env.APPLE_PRIVATE_KEY).replace(/\\n/g, '\n')
    : String(env.APPLE_PRIVATE_KEY || '');

  const privateKey = await importPKCS8(pem, 'ES256');
  const now = Math.floor(Date.now() / 1000);

  return new SignJWT({})
    .setProtectedHeader({alg: 'ES256', kid: env.APPLE_KEY_ID})
    .setIssuer(env.APPLE_TEAM_ID)
    .setIssuedAt(now)
    .setExpirationTime(now + 300)
    .setAudience('https://appleid.apple.com')
    .setSubject(env.APPLE_CLIENT_ID)
    .sign(privateKey);
}

// Apple only sends the `user` field (containing name) on the very FIRST
// authorization a user ever grants this app — every subsequent login omits
// it entirely, even if the user revokes and re-grants in some cases. Name
// must be treated as optional here; once we have the customer's name from
// that first login it lives in the Shopify Admin customer record, not
// something we need Apple to keep re-sending.
export async function action({request, context}) {
  if (request.method !== 'POST') {
    return redirect('/account/login');
  }

  const form = await request.formData();
  const code = form.get('code');
  const state = form.get('state');
  const errorParam = form.get('error');
  const userJson = form.get('user');

  const stored = readAppleOAuthCookie(request);
  const redirectTo = stored?.redirectTo || '/account';
  const expectedState = stored?.state;

  if (errorParam) {
    return redirectClearingAppleCookie(
      `/account/login?error=${encodeURIComponent('Apple sign-in was cancelled.')}`,
    );
  }
  if (!code || !state || !expectedState || state !== expectedState) {
    return redirectClearingAppleCookie(
      `/account/login?error=${encodeURIComponent('Apple sign-in failed (invalid state). Please try again.')}`,
    );
  }

  const {APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY} = context.env;
  if (!APPLE_CLIENT_ID || !APPLE_TEAM_ID || !APPLE_KEY_ID || !APPLE_PRIVATE_KEY) {
    return new Response('Apple sign-in is not configured.', {status: 500});
  }

  const url = new URL(request.url);
  const redirectUri = `${url.origin}/account/login/apple/callback`;

  try {
    const clientSecret = await generateAppleClientSecret(context.env);

    const tokenRes = await fetch('https://appleid.apple.com/auth/token', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams({
        code: String(code),
        client_id: APPLE_CLIENT_ID,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    });
    const tokenBody = await tokenRes.json();
    if (!tokenRes.ok || !tokenBody.id_token) {
      throw new Error(tokenBody.error_description || 'Apple token exchange failed.');
    }

    const {payload} = await jwtVerify(tokenBody.id_token, APPLE_JWKS, {
      issuer: 'https://appleid.apple.com',
      audience: APPLE_CLIENT_ID,
    });

    if (!payload.email) {
      throw new Error('Apple did not return an email address.');
    }

    let firstName;
    let lastName;
    if (typeof userJson === 'string' && userJson.length) {
      try {
        const parsed = JSON.parse(userJson);
        firstName = parsed?.name?.firstName;
        lastName = parsed?.name?.lastName;
      } catch {
        // Malformed/unexpected `user` payload — proceed without a name.
      }
    }

    const customer = await findOrCreateCustomerForOAuth(context.env, {
      email: payload.email,
      firstName,
      lastName,
      provider: 'apple',
      subjectId: payload.sub,
    });

    setSessionCustomerId(context.session, customer.id);
    const {headers: cartHeaders} = await reconcileCustomerCart({context, customer});
    return redirectClearingAppleCookie(redirectTo, cartHeaders);
  } catch (error) {
    console.error('[account.login.apple.callback] failed', error);
    return redirectClearingAppleCookie(
      `/account/login?error=${encodeURIComponent('Apple sign-in failed. Please try again or use email.')}`,
    );
  }
}

// Apple's flow always POSTs here; a stray GET (e.g. someone bookmarking the
// callback URL) just bounces to login.
export async function loader() {
  return redirect('/account/login');
}

/** @typedef {import('@shopify/hydrogen').HydrogenEnv} Env */
/** @typedef {import('./+types/account_.login.apple.callback').Route} Route */
