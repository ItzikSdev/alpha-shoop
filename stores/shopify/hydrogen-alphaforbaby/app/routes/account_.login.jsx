import {
  redirect,
  data,
  Form,
  useActionData,
  useLoaderData,
  useNavigation,
  useSearchParams,
} from 'react-router';
import {useState} from 'react';
import {
  findCustomerByEmail,
  verifyCustomerPassword,
  isLoggedIn,
  setSessionCustomerId,
} from '~/lib/customer';
import {reconcileCustomerCart} from '~/lib/cartSync';
import {Input, Button, Typography, Alert} from '@material-tailwind/react';

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.5 0 10.5-2.1 14.3-5.6l-6.6-5.6C29.7 34.6 27 35.5 24 35.5c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.2-4.1 5.6l6.6 5.6C41.9 36 44 30.5 44 24c0-1.3-.1-2.7-.4-3.5z"
      />
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 384 512" aria-hidden="true" fill="currentColor">
      <path d="M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141 0 184.8 0 273.5c0 26.2 4.8 53.3 14.4 81.2 12.8 37.6 59 129.3 107.2 127.8 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-84.1 102.6-121.8-65.2-30.7-57.7-90-57.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z" />
    </svg>
  );
}

function SocialButton({provider, redirectTo, children, disabled}) {
  return (
    <a
      href={`/account/login/${provider}?redirect=${encodeURIComponent(redirectTo)}`}
      aria-disabled={disabled}
      className={`flex items-center justify-center gap-3 w-full rounded-lg border border-blue-gray-100 py-2.5 font-medium text-sm text-blue-gray-700 transition-colors hover:bg-blue-gray-50 ${
        disabled ? 'pointer-events-none opacity-50' : ''
      }`}
    >
      {children}
    </a>
  );
}

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Sign in'}];
};

/**
 * Independent, Admin-API-backed login — replaces the hosted OAuth Customer
 * Account API flow (redirected through the Online Store channel's domain)
 * AND the classic Storefront customerAccessTokenCreate flow that came after
 * it (this shop has Classic customer accounts DISABLED, so even that
 * ultimately redirected off-domain through shopify.com/authentication/...
 * for activation). This form never leaves the site: we verify the password
 * ourselves against a hash we store in a private Admin API metafield, and
 * set our own session cookie — see app/lib/customer.js for the full
 * rationale and data model.
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  const url = new URL(request.url);
  if (isLoggedIn(context.session)) {
    return redirect(url.searchParams.get('redirect') || '/account');
  }
  // Google/Apple OAuth callbacks bounce failures back here with ?error=...
  return {oauthError: url.searchParams.get('error')};
}

/**
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  const form = await request.formData();
  const email = String(form.get('email') || '').trim();
  const password = String(form.get('password') || '');
  const redirectTo = String(form.get('redirect') || '/account');

  if (!email || !password) {
    return data({error: 'Please enter both email and password.'}, {status: 400});
  }

  // Deliberately generic error message on any failure path below — never
  // reveal whether the email exists or the password was wrong.
  const genericError = 'Invalid email or password.';

  try {
    const customer = await findCustomerByEmail(context.env, email);
    const passwordOk = await verifyCustomerPassword(customer, password);
    if (!customer || !passwordOk) {
      return data({error: genericError}, {status: 401});
    }

    setSessionCustomerId(context.session, customer.id);
    const {headers: cartHeaders} = await reconcileCustomerCart({context, customer});
    return redirect(redirectTo, {headers: cartHeaders});
  } catch (error) {
    console.error('[account.login] failed', error);
    return data({error: genericError}, {status: 401});
  }
}

export default function Login() {
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get('redirect') || '/account';
  const {state} = useNavigation();
  /** @type {ActionReturnData} */
  const action = useActionData();
  /** @type {LoaderReturnData} */
  const {oauthError} = useLoaderData();
  const [showEmailForm, setShowEmailForm] = useState(false);

  return (
    <div className="grid min-h-[70vh] place-items-center px-4 py-16">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="text-center flex flex-col gap-1">
          <Typography variant="h3" color="blue-gray">
            Welcome back
          </Typography>
          <Typography variant="small" color="gray">
            Sign in to track orders, save addresses, and check out faster.
          </Typography>
        </div>

        {oauthError ? (
          <Alert color="red" variant="ghost">
            {oauthError}
          </Alert>
        ) : null}

        <div className="flex flex-col gap-3">
          <SocialButton provider="google" redirectTo={redirectTo}>
            <GoogleIcon />
            Continue with Google
          </SocialButton>
          <SocialButton provider="apple" redirectTo={redirectTo}>
            <AppleIcon />
            Continue with Apple
          </SocialButton>
        </div>

        <div className="flex items-center gap-3">
          <span className="h-px flex-1 bg-blue-gray-100" />
          <Typography variant="small" color="gray">
            or
          </Typography>
          <span className="h-px flex-1 bg-blue-gray-100" />
        </div>

        {!showEmailForm ? (
          <Button
            variant="outlined"
            fullWidth
            onClick={() => setShowEmailForm(true)}
          >
            Continue with email
          </Button>
        ) : (
          <Form method="POST" className="flex flex-col gap-4">
            <input type="hidden" name="redirect" value={redirectTo} />
            <Input
              id="email"
              name="email"
              type="email"
              label="Email"
              autoComplete="email"
              required
              autoFocus
              crossOrigin=""
            />
            <Input
              id="password"
              name="password"
              type="password"
              label="Password"
              autoComplete="current-password"
              required
              crossOrigin=""
            />
            {action?.error ? (
              <Alert color="red" variant="ghost">
                {action.error}
              </Alert>
            ) : null}
            <Button type="submit" fullWidth disabled={state !== 'idle'}>
              {state !== 'idle' ? 'Signing in…' : 'Sign in'}
            </Button>
            <div className="flex items-center justify-between text-sm text-blue-gray-500">
              <a href="/account/recover" className="login-underline-link">
                Forgot password?
              </a>
              <a
                href={`/account/register?redirect=${encodeURIComponent(redirectTo)}`}
                className="login-underline-link"
              >
                Create account
              </a>
            </div>
          </Form>
        )}

        <Typography variant="small" color="gray" className="text-center">
          By continuing, you agree to our{' '}
          <a href="/policies/terms-of-service" className="login-underline-link">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="/policies/privacy-policy" className="login-underline-link">
            Privacy Policy
          </a>
          .
        </Typography>
      </div>
    </div>
  );
}

/**
 * @typedef {{error: string}} ActionResponse
 */

/** @typedef {import('./+types/account_.login').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
