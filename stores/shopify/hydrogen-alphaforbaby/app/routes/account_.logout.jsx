import {redirect} from 'react-router';
import {clearSessionCustomerId} from '~/lib/customer';

// if we don't implement this, /account/logout will get caught by account.$.jsx to do login

export async function loader() {
  return redirect('/');
}

/**
 * @param {Route.ActionArgs}
 */
export async function action({context}) {
  clearSessionCustomerId(context.session);
  return redirect('/');
}

/** @typedef {import('./+types/account_.logout').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
