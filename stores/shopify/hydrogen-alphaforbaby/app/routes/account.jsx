import {
  data as remixData,
  Form,
  NavLink,
  Outlet,
  useLoaderData,
} from 'react-router';
import {requireCustomer} from '~/lib/customer';

export function shouldRevalidate() {
  return true;
}

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  // Redirects to /account/login (preserving the destination) if there's no
  // valid customerAccessToken in the session.
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
    <div className="account">
      <h1>{heading}</h1>
      <br />
      <AccountMenu />
      <br />
      <br />
      <Outlet context={{customer}} />
    </div>
  );
}

function AccountMenu() {
  function isActiveStyle({isActive, isPending}) {
    return {
      fontWeight: isActive ? 'bold' : undefined,
      color: isPending ? 'grey' : 'black',
    };
  }

  return (
    <nav role="navigation">
      <NavLink to="/account/orders" style={isActiveStyle}>
        Orders &nbsp;
      </NavLink>
      &nbsp;|&nbsp;
      <NavLink to="/account/profile" style={isActiveStyle}>
        &nbsp; Profile &nbsp;
      </NavLink>
      &nbsp;|&nbsp;
      <NavLink to="/account/addresses" style={isActiveStyle}>
        &nbsp; Addresses &nbsp;
      </NavLink>
      &nbsp;|&nbsp;
      <Logout />
    </nav>
  );
}

function Logout() {
  return (
    <Form className="account-logout" method="POST" action="/account/logout">
      &nbsp;<button type="submit">Sign out</button>
    </Form>
  );
}

/** @typedef {import('./+types/account').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
