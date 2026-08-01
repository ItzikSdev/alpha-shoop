import {redirect} from 'react-router';

/**
 * Starts the Google OAuth authorization-code flow. This is fully
 * independent of Shopify's own customer login — Google authenticates the
 * user, we verify their ID token ourselves (see the callback route), and
 * find-or-create a Shopify Admin API customer by email. No Shopify redirect
 * is ever involved in this leg.
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  const url = new URL(request.url);
  const redirectTo = url.searchParams.get('redirect') || '/account';

  const clientId = context.env.GOOGLE_CLIENT_ID;
  if (!clientId) {
    return new Response(
      'Google sign-in is not configured (missing GOOGLE_CLIENT_ID).',
      {status: 500},
    );
  }

  // CSRF protection: a random value we can only have set ourselves, checked
  // against what Google echoes back to the callback.
  const state = crypto.randomUUID();
  context.session.set('oauthState', state);
  context.session.set('oauthRedirect', redirectTo);

  const redirectUri = `${url.origin}/account/login/google/callback`;

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    state,
    prompt: 'select_account',
  });

  return redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`);
}

/** @typedef {import('./+types/account_.login.google').Route} Route */
