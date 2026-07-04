import {Suspense} from 'react';
import {Await, NavLink, Link} from 'react-router';
import {useAnalytics, useOptimisticCart} from '@shopify/hydrogen';
import {useAside} from '~/components/Aside';
import {config} from '~/lib/theme';

// Brand + nav come from app/theme.config.json (clone-friendly).
const NAV = config.nav;
const LOGO = config.brand.logoText;
const LOGO_IMG = config.brand.logoImage;

/**
 * @param {{cart: Promise<CartApiQueryFragment|null>, isLoggedIn: Promise<boolean>}}
 */
export function Header({cart, isLoggedIn}) {
  return (
    <header className="tob-header">
      <div className="tob-wrap tob-hrow">
        <NavLink prefetch="intent" to="/" end className="tob-hlogo">
          {LOGO_IMG && (
            <img className="tob-hlogo-mark" src={LOGO_IMG} alt="" aria-hidden="true" />
          )}
          <span>{LOGO}</span>
        </NavLink>

        <nav className="tob-hnav" role="navigation">
          {NAV.map((item) => (
            <NavLink key={item.url} prefetch="intent" to={item.url}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <HeaderCtas isLoggedIn={isLoggedIn} cart={cart} />
      </div>
    </header>
  );
}

/**
 * @param {{isLoggedIn: Promise<boolean>, cart: Promise<CartApiQueryFragment|null>}}
 */
function HeaderCtas({isLoggedIn, cart}) {
  const {open} = useAside();
  return (
    <nav className="tob-hcta" role="navigation">
      <button
        className="tob-hmob reset"
        aria-label="Open menu"
        onClick={() => open('mobile')}
      >
        <IconMenu />
      </button>
      <Link prefetch="intent" to="/search" aria-label="Search">
        <IconSearch />
      </Link>
      <NavLink prefetch="intent" to="/account" aria-label="Account">
        <Suspense fallback={<IconUser />}>
          <Await resolve={isLoggedIn} errorElement={<IconUser />}>
            {() => <IconUser />}
          </Await>
        </Suspense>
      </NavLink>
      <CartToggle cart={cart} />
    </nav>
  );
}

/**
 * @param {{count: number}}
 */
function CartBadge({count}) {
  const {publish, shop, cart, prevCart} = useAnalytics();
  return (
    <Link
      className="tob-hcart"
      to="/cart"
      prefetch="intent"
      aria-label={`Cart, ${count} item${count === 1 ? '' : 's'}`}
      onClick={() =>
        publish('cart_viewed', {
          cart,
          prevCart,
          shop,
          url: typeof window !== 'undefined' ? window.location.href : '',
        })
      }
    >
      <IconBag />
      {count > 0 && <span className="tob-hcart-count">{count}</span>}
    </Link>
  );
}

/* ── Shopify-style line icons (inline SVG, currentColor) ── */
function IconSearch() {
  return (
    <svg className="tob-ic" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="9" cy="9" r="6" />
      <line x1="13.5" y1="13.5" x2="18" y2="18" />
    </svg>
  );
}
function IconUser() {
  return (
    <svg className="tob-ic" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="6.5" r="3.2" />
      <path d="M4 17c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" />
    </svg>
  );
}
function IconBag() {
  return (
    <svg className="tob-ic" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M5 6h10l1 11H4L5 6z" />
      <path d="M7.5 6V5a2.5 2.5 0 0 1 5 0v1" />
    </svg>
  );
}
function IconMenu() {
  return (
    <svg className="tob-ic" viewBox="0 0 20 20" aria-hidden="true">
      <line x1="3" y1="6" x2="17" y2="6" />
      <line x1="3" y1="10" x2="17" y2="10" />
      <line x1="3" y1="14" x2="17" y2="14" />
    </svg>
  );
}

/**
 * @param {{cart: Promise<CartApiQueryFragment|null>}}
 */
function CartToggle({cart}) {
  return (
    <Suspense fallback={<CartBadge count={0} />}>
      <Await resolve={cart}>
        {(resolved) => <CartBadgeOptimistic cart={resolved} />}
      </Await>
    </Suspense>
  );
}

function CartBadgeOptimistic({cart}) {
  const optimistic = useOptimisticCart(cart);
  return <CartBadge count={optimistic?.totalQuantity ?? 0} />;
}

/** @typedef {import('storefrontapi.generated').CartApiQueryFragment} CartApiQueryFragment */
