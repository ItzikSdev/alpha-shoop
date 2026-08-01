import {data, Form, useActionData, useNavigation} from 'react-router';
import {Input, Button, Typography, Alert} from '@material-tailwind/react';
import {createPasswordResetToken} from '~/lib/customer';
import {sendPasswordResetEmail} from '~/lib/email';

/**
 * Forgot-password flow, backed by our own reset-token metafields (see
 * app/lib/customer.js's createPasswordResetToken/resetPasswordWithToken)
 * and Resend for delivery (app/lib/email.js) — not Shopify's own customer
 * email system, which this store doesn't use for auth at all (see
 * app/lib/customer.js's top-of-file rationale).
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Forgot password'}];
};

/**
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  const form = await request.formData();
  const email = String(form.get('email') || '').trim();

  if (!email) {
    return data({error: 'Please enter your email address.'}, {status: 400});
  }

  // Always the same outcome shown to the user regardless of whether the
  // email matches an account — never leak account existence.
  try {
    const result = await createPasswordResetToken(context.env, email);
    if (result) {
      const resetUrl = new URL(
        `/account/reset?token=${encodeURIComponent(result.token)}&email=${encodeURIComponent(email)}`,
        new URL(request.url).origin,
      ).toString();
      await sendPasswordResetEmail(context.env, {to: result.customer.email, resetUrl});
    }
  } catch (error) {
    console.error('[account.recover] failed', error);
    // Still show the generic success message — don't reveal internal errors,
    // and don't let a delivery hiccup block the user from trying again.
  }

  return data({sent: true});
}

export default function Recover() {
  const {state} = useNavigation();
  /** @type {ActionReturnData} */
  const action = useActionData();

  if (action?.sent) {
    return (
      <div className="grid min-h-[70vh] place-items-center px-4 py-16">
        <div className="w-full max-w-sm flex flex-col gap-6 text-center">
          <Typography variant="h3" color="blue-gray">
            Check your email
          </Typography>
          <Typography variant="paragraph" color="gray">
            If that email has an account, we&apos;ve sent a link to reset your password. The
            link expires in 30 minutes.
          </Typography>
          <Typography variant="small" color="gray">
            <a href="/account/login" className="login-underline-link">
              Back to sign in
            </a>
          </Typography>
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-[70vh] place-items-center px-4 py-16">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="text-center flex flex-col gap-1">
          <Typography variant="h3" color="blue-gray">
            Forgot your password?
          </Typography>
          <Typography variant="small" color="gray">
            Enter your email and we&apos;ll send you a reset link.
          </Typography>
        </div>
        <Form method="POST" className="flex flex-col gap-4">
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
          {action?.error ? (
            <Alert color="red" variant="ghost">
              {action.error}
            </Alert>
          ) : null}
          <Button type="submit" fullWidth disabled={state !== 'idle'}>
            {state !== 'idle' ? 'Sending…' : 'Send reset link'}
          </Button>
        </Form>
        <Typography variant="small" color="gray" className="text-center">
          <a href="/account/login" className="login-underline-link">
            Back to sign in
          </a>
        </Typography>
      </div>
    </div>
  );
}

/**
 * @typedef {{error?: string, sent?: boolean}} ActionResponse
 */

/** @typedef {import('./+types/account_.recover').Route} Route */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
