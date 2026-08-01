import {
  data as remixData,
  Form,
  NavLink,
  Outlet,
  useLoaderData,
} from 'react-router';
import {Typography, Button} from '@material-tailwind/react';
import {requireCustomer} from '~/lib/customer';

export function shouldRevalidate() {
  return true;
}

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  // Redirects to /account/login (preserving the destination) if there's no
  // logged-in customerId in our own session (see app/lib/customer.js).
  const customer = await requireCustomer(context, request);

  return remixData(
    {customer},
    {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    },
  );
}

export default function AccountLayout() {
  /** @type {LoaderReturnData} */
  const {customer} = useLoaderData();

  const heading = customer
    ? customer.firstName
      ? `Welcome, ${customer.firstName}`
      : `Welcome to your account.`
    : 'Account Details';

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 flex flex-col gap-8">
      <Typography variant="h3" color="blue-gray">
        {heading}
      </Typography>
      <AccountMenu />
      <Outlet context={{customer}} />
    </div>
  );
}

function AccountMenu() {
  function navLinkClass({isActive}) {
    return `pb-3 text-sm font-medium border-b-2 transition-colors ${
      isActive
        ? 'border-blue-gray-900 text-blue-gray-900'
        : 'border-transparent text-blue-gray-400 hover:text-blue-gray-700'
    }`;
  }

  return (
    <nav
      role="navigation"
      className="flex items-center gap-6 border-b border-blue-gray-100"
    >
      <NavLink to="/account/orders" className={navLinkClass}>
        Orders
      </NavLink>
      <NavLink to="/account/profile" className={navLinkClass}>
        Profile
      </NavLink>
      <NavLink to="/account/addresses" className={navLinkClass}>
        Addresses
      </NavLink>
      <Logout />
    </nav>
  );
}

function Logout() {
  return (
    <Form method="POST" action="/account/logout" className="ml-auto pb-3">
      <Button type="submit" variant="text" size="sm" className="p-0 normal-case text-blue-gray-400 hover:text-blue-gray-700">
        Sign out
      </Button>
    </Form>
  );
}

/** @typedef {import('./+types/account').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
