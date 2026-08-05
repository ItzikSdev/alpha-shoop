import {redirect} from 'react-router';
import {jwtVerify, createRemoteJWKSet} from 'jose';
import {findOrCreateCustomerForOAuth, setSessionCustomerId} from '~/lib/customer';
import {reconcileCustomerCart} from '~/lib/cartSync';

// Cached across requests within the same isolate — jose fetches Google's
// JWKS lazily and re-fetches on `kid` cache misses / expiry.
const GOOGLE_JWKS = createRemoteJWKSet(
  new URL('https://www.googleapis.com/oauth2/v3/certs'),
);

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const errorParam = url.searchParams.get('error');

  const redirectTo = context.session.get('oauthRedirect') || '/account';
  const expectedState = context.session.get('oauthState');
  context.session.unset('oauthState');
  context.session.unset('oauthRedirect');

  if (errorParam) {
    return redirect(
      `/account/login?error=${encodeURIComponent('Google sign-in was cancelled.')}`,
    );
  }
  if (!code || !state || state !== expectedState) {
    return redirect(
      `/account/login?error=${encodeURIComponent('Google sign-in failed (invalid state). Please try again.')}`,
    );
  }

  const clientId = context.env.GOOGLE_CLIENT_ID;
  const clientSecret = context.env.GOOGLE_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    return new Response('Google sign-in is not configured.', {status: 500});
  }

  const redirectUri = `${url.origin}/account/login/google/callback`;

  try {
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    });
    const tokenBody = await tokenRes.json();
    if (!tokenRes.ok || !tokenBody.id_token) {
      throw new Error(tokenBody.error_description || 'Google token exchange failed.');
    }

    // Verifies signature against Google's live JWKS, plus issuer/audience —
    // this is what makes trusting the email in the token safe.
    const {payload} = await jwtVerify(tokenBody.id_token, GOOGLE_JWKS, {
      issuer: ['https://accounts.google.com', 'accounts.google.com'],
      audience: clientId,
    });

    if (!payload.email) {
      throw new Error('Google did not return an email address.');
    }
    if (payload.email_verified === false) {
      throw new Error('Google account email is not verified.');
    }

    const customer = await findOrCreateCustomerForOAuth(context.env, {
      email: payload.email,
      firstName: payload.given_name,
      lastName: payload.family_name,
      provider: 'google',
      subjectId: payload.sub,
    });

    setSessionCustomerId(context.session, customer.id);
    const {headers: cartHeaders} = await reconcileCustomerCart({context, customer});
    return redirect(redirectTo, {headers: cartHeaders});
  } catch (error) {
    console.error('[account.login.google.callback] failed', error);
    return redirect(
      `/account/login?error=${encodeURIComponent('Google sign-in failed. Please try again or use email.')}`,
    );
  }
}

/** @typedef {import('./+types/account_.login.google.callback').Route} Route */
