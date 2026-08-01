import {redirect} from 'react-router';

// Fallback catch-all for any unmatched /account/* path (e.g. a stale bookmark
// to the old OAuth /account/authorize callback). Just bounces to /account,
// whose own loader enforces the login redirect if needed.
export async function loader() {
  return redirect('/account');
}

/** @typedef {import('./+types/account.$').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
