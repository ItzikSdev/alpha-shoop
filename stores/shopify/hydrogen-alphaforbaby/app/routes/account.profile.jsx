import {
  data,
  Form,
  useActionData,
  useNavigation,
  useOutletContext,
} from 'react-router';
import {Input, Button, Typography, Alert} from '@material-tailwind/react';
import {requireCustomer, updateCustomerProfile} from '~/lib/customer';

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Profile'}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  await requireCustomer(context, request);
  return {};
}

/**
 * Updates the customer's profile via the Admin API. Auth is enforced by
 * requiring a valid session customerId (set by our own login/register/OAuth
 * flows) — never a Shopify Storefront customerAccessToken.
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  if (request.method !== 'PUT') {
    return data({error: 'Method not allowed'}, {status: 405});
  }

  const customer = await requireCustomer(context, request);
  const form = await request.formData();

  try {
    const fields = {};
    for (const key of ['firstName', 'lastName']) {
      const value = form.get(key);
      if (typeof value === 'string' && value.length) {
        fields[key] = value;
      }
    }

    const updated = await updateCustomerProfile(context.env, customer.id, fields);

    return {error: null, customer: updated};
  } catch (error) {
    console.error('[account.profile] update failed', error);
    return data(
      {error: error instanceof Error ? error.message : 'Could not update profile.', customer: null},
      {status: 400},
    );
  }
}

export default function AccountProfile() {
  const account = useOutletContext();
  const {state} = useNavigation();
  /** @type {ActionReturnData} */
  const action = useActionData();
  const customer = action?.customer ?? account?.customer;

  return (
    <div className="max-w-md flex flex-col gap-6">
      <Typography variant="h4" color="blue-gray">
        My profile
      </Typography>
      <SignInMethods customer={customer} />
      <Form method="PUT" className="flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="w-full">
            <Input
              id="firstName"
              name="firstName"
              type="text"
              label="First name"
              autoComplete="given-name"
              defaultValue={customer?.firstName ?? ''}
              minLength={2}
              crossOrigin=""
            />
          </div>
          <div className="w-full">
            <Input
              id="lastName"
              name="lastName"
              type="text"
              label="Last name"
              autoComplete="family-name"
              defaultValue={customer?.lastName ?? ''}
              minLength={2}
              crossOrigin=""
            />
          </div>
        </div>
        {action?.error ? (
          <Alert color="red" variant="ghost">
            {action.error}
          </Alert>
        ) : null}
        <Button type="submit" disabled={state !== 'idle'} className="self-start">
          {state !== 'idle' ? 'Updating…' : 'Update'}
        </Button>
      </Form>
    </div>
  );
}

/**
 * Shows which method(s) this account can sign in with, and the account email
 * — informational only, sourced from the `_auth` presence flags already on
 * the customer object (never the password hash itself). Since OAuth
 * find-or-create matches strictly by email (see app/lib/customer.js), every
 * linked method shares the same one account email, so it's shown once.
 * @param {{customer: object | null}} props
 */
function SignInMethods({customer}) {
  if (!customer) return null;
  const methods = [
    customer._auth?.passwordHash ? 'Email & password' : null,
    customer._auth?.googleSub ? 'Google' : null,
    customer._auth?.appleSub ? 'Apple' : null,
  ].filter(Boolean);

  if (!methods.length) return null;

  return (
    <div className="rounded-lg border border-blue-gray-100 bg-blue-gray-50/50 px-4 py-3">
      <Typography variant="small" color="blue-gray" className="font-medium">
        Signed in with {methods.join(' + ')}
      </Typography>
      <Typography variant="small" color="gray">
        {customer.email}
      </Typography>
    </div>
  );
}

/**
 * @typedef {{
 *   error: string | null;
 *   customer: object | null;
 * }} ActionResponse
 */

/** @typedef {import('./+types/account.profile').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
