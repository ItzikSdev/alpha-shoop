import {redirect, data, Form, useActionData, useNavigation, useLoaderData} from 'react-router';
import {Input, Button, Typography, Alert} from '@material-tailwind/react';
import {resetPasswordWithToken, setSessionCustomerId} from '~/lib/customer';

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Reset password'}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request}) {
  const url = new URL(request.url);
  const token = url.searchParams.get('token') || '';
  const email = url.searchParams.get('email') || '';
  if (!token || !email) {
    throw new Response('Missing reset token.', {status: 400});
  }
  return {token, email};
}

/**
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  const form = await request.formData();
  const token = String(form.get('token') || '');
  const email = String(form.get('email') || '');
  const password = String(form.get('password') || '');

  if (password.length < 5) {
    return data({error: 'Password must be at least 5 characters.'}, {status: 400});
  }

  try {
    const customer = await resetPasswordWithToken(context.env, {
      email,
      token,
      newPassword: password,
    });
    setSessionCustomerId(context.session, customer.id);
    return redirect('/account');
  } catch (error) {
    return data(
      {error: error instanceof Error ? error.message : 'Could not reset password.'},
      {status: 400},
    );
  }
}

export default function Reset() {
  const {token, email} = useLoaderData();
  const {state} = useNavigation();
  /** @type {ActionReturnData} */
  const action = useActionData();

  return (
    <div className="grid min-h-[70vh] place-items-center px-4 py-16">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="text-center flex flex-col gap-1">
          <Typography variant="h3" color="blue-gray">
            Set a new password
          </Typography>
        </div>
        <Form method="POST" className="flex flex-col gap-4">
          <input type="hidden" name="token" value={token} />
          <input type="hidden" name="email" value={email} />
          <Input
            id="password"
            name="password"
            type="password"
            label="New password"
            autoComplete="new-password"
            required
            autoFocus
            crossOrigin=""
          />
          {action?.error ? (
            <Alert color="red" variant="ghost">
              {action.error}{' '}
              <a href="/account/recover" className="login-underline-link">
                Request a new link
              </a>
            </Alert>
          ) : null}
          <Button type="submit" fullWidth disabled={state !== 'idle'}>
            {state !== 'idle' ? 'Saving…' : 'Save password'}
          </Button>
        </Form>
      </div>
    </div>
  );
}

/**
 * @typedef {{error: string}} ActionResponse
 */

/** @typedef {import('./+types/account_.reset').Route} Route */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
