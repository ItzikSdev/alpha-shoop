import {
  redirect,
  data,
  Form,
  useActionData,
  useNavigation,
  useSearchParams,
} from 'react-router';
import {
  findCustomerByEmail,
  createCustomerAccount,
  claimGuestCustomerAccount,
  isLoggedIn,
  setSessionCustomerId,
} from '~/lib/customer';
import {Input, Button, Typography, Alert} from '@material-tailwind/react';

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Create account'}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  if (isLoggedIn(context.session)) {
    const redirectTo = new URL(request.url).searchParams.get('redirect');
    return redirect(redirectTo || '/account');
  }
  return {};
}

/**
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  const form = await request.formData();
  const firstName = String(form.get('firstName') || '').trim();
  const lastName = String(form.get('lastName') || '').trim();
  const email = String(form.get('email') || '').trim();
  const password = String(form.get('password') || '');
  const redirectTo = String(form.get('redirect') || '/account');

  if (!firstName || !lastName) {
    return data({error: 'Please enter your first and last name.'}, {status: 400});
  }
  if (!email || !password) {
    return data({error: 'Please enter both email and password.'}, {status: 400});
  }
  if (password.length < 5) {
    return data({error: 'Password must be at least 5 characters.'}, {status: 400});
  }

  try {
    const existing = await findCustomerByEmail(context.env, email);

    let customer;
    if (existing) {
      // A Shopify Customer record already exists for this email — most
      // commonly because they checked out as a guest before ever creating
      // an account here. If it has no password set yet, "claim" it rather
      // than blocking registration on a record they have no way to log
      // into. If it DOES have a password, it's a genuine existing account.
      if (existing._auth?.passwordHash) {
        return data(
          {error: 'An account with this email already exists.'},
          {status: 400},
        );
      }
      customer = await claimGuestCustomerAccount(context.env, existing, {
        password,
        firstName,
        lastName,
      });
    } else {
      customer = await createCustomerAccount(context.env, {
        email,
        password,
        firstName,
        lastName,
      });
    }

    setSessionCustomerId(context.session, customer.id);
    return redirect(redirectTo);
  } catch (error) {
    console.error('[account.register] failed', error);
    return data(
      {error: error instanceof Error ? error.message : 'Could not create account.'},
      {status: 400},
    );
  }
}

export default function Register() {
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get('redirect') || '/account';
  const {state} = useNavigation();
  /** @type {ActionReturnData} */
  const action = useActionData();

  return (
    <div className="grid min-h-[70vh] place-items-center px-4 py-16">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="text-center flex flex-col gap-1">
          <Typography variant="h3" color="blue-gray">
            Create your account
          </Typography>
          <Typography variant="small" color="gray">
            Track orders, save addresses, and check out faster next time.
          </Typography>
        </div>

        <Form method="POST" className="flex flex-col gap-4">
          <input type="hidden" name="redirect" value={redirectTo} />
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="w-full">
              <Input id="firstName" name="firstName" label="First name" required crossOrigin="" />
            </div>
            <div className="w-full">
              <Input id="lastName" name="lastName" label="Last name" required crossOrigin="" />
            </div>
          </div>
          <Input
            id="email"
            name="email"
            type="email"
            label="Email"
            autoComplete="email"
            required
            crossOrigin=""
          />
          <Input
            id="password"
            name="password"
            type="password"
            label="Password"
            autoComplete="new-password"
            required
            crossOrigin=""
          />
          {action?.error ? (
            <Alert color="red" variant="ghost">
              {action.error}
            </Alert>
          ) : null}
          <Button type="submit" fullWidth disabled={state !== 'idle'}>
            {state !== 'idle' ? 'Creating account…' : 'Create account'}
          </Button>
        </Form>

        <Typography variant="small" color="gray" className="text-center">
          Already have an account?{' '}
          <a
            href={`/account/login?redirect=${encodeURIComponent(redirectTo)}`}
            className="login-underline-link"
          >
            Sign in
          </a>
        </Typography>
      </div>
    </div>
  );
}

/**
 * @typedef {{error: string}} ActionResponse
 */

/** @typedef {import('./+types/account_.register').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
