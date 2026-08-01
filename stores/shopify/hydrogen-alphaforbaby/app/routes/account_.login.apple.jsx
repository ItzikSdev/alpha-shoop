import {redirect} from 'react-router';

/**
 * Starts the "Sign in with Apple" authorization-code flow. Apple's
 * registered Return URL for this client (com.alphaforbaby.web) is ONLY
 * `https://alphaforbaby.com/account/login/apple/callback` — no localhost is
 * registered, so this leg can only be exercised end-to-end against
 * production. Locally we can still confirm the redirect itself (URL +
 * params), just not complete a real round trip.
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  const url = new URL(request.url);
  const redirectTo = url.searchParams.get('redirect') || '/account';

  const clientId = context.env.APPLE_CLIENT_ID;
  if (!clientId) {
    return new Response(
      'Apple sign-in is not configured (missing APPLE_CLIENT_ID).',
      {status: 500},
    );
  }

  const state = crypto.randomUUID();
  context.session.set('oauthState', state);
  context.session.set('oauthRedirect', redirectTo);

  const redirectUri = `${url.origin}/account/login/apple/callback`;

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    response_mode: 'form_post', // Apple POSTs the result to the callback.
    scope: 'name email',
    state,
  });

  return redirect(`https://appleid.apple.com/auth/authorize?${params.toString()}`);
}

/** @typedef {import('./+types/account_.login.apple').Route} Route */
