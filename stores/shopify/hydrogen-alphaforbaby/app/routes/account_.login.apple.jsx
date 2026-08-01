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

  // NOTE: deliberately NOT using context.session (SameSite=Lax) for the
  // CSRF state here. Apple's callback is a cross-site POST
  // (response_mode=form_post below), and browsers do not send SameSite=Lax
  // cookies on cross-site POST requests (only top-level GET navigations) —
  // so anything stored in the main session would already be gone by the
  // time the callback runs. This dedicated cookie uses SameSite=None
  // (scoped ONLY to this one short-lived value, not the real session) so it
  // actually survives the round trip to appleid.apple.com and back.
  const state = crypto.randomUUID();
  const cookieValue = encodeURIComponent(JSON.stringify({state, redirectTo}));

  const redirectUri = `${url.origin}/account/login/apple/callback`;

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    response_mode: 'form_post', // Apple POSTs the result to the callback.
    scope: 'name email',
    state,
  });

  return redirect(`https://appleid.apple.com/auth/authorize?${params.toString()}`, {
    headers: {
      'Set-Cookie': `apple_oauth=${cookieValue}; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=600`,
    },
  });
}

/** @typedef {import('./+types/account_.login.apple').Route} Route */
