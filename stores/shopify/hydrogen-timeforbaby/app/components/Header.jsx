import {Suspense, useState, useRef, useEffect} from 'react';
import {Await, NavLink, Link} from 'react-router';
import {useAnalytics, useOptimisticCart} from '@shopify/hydrogen';
import {useAside} from '~/components/Aside';
import {SearchFormPredictive} from '~/components/SearchFormPredictive';
import {SearchResultsPredictive} from '~/components/SearchResultsPredictive';
import {config} from '~/lib/theme';

// Brand + nav come from app/theme.config.json (clone-friendly).
const LOGO = config.brand.logoText;
const LOGO_IMG = config.brand.logoImage;

/**
 * @param {{cart: Promise<CartApiQueryFragment|null>, isLoggedIn: Promise<boolean>}}\
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

        {/* Desktop nav — visible on screens ≥ 820 px */}
        <DesktopNav />

        {/* Persistent search bar — always visible in the header (desktop) */}
        <HeaderSearch />

        <HeaderCtas isLoggedIn={isLoggedIn} cart={cart} />
      </div>
    </header>
  );
}

/**
 * Always-on search field in the header with a live predictive dropdown.
 * Results appear INSIDE the navbar (dropdown) — no page jump to /search.
 * Pressing Enter still runs a full search on /search as a fallback.
 */
function HeaderSearch() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  // Close the dropdown when clicking outside the search area.
  useEffect(() => {
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  return (
    <div className="tob-hsearch-wrap" ref={wrapRef}>
      <SearchFormPredictive className="tob-hsearch" role="search">
        {({fetchResults, goToSearch, inputRef}) => (
          <>
            <IconSearch />
            <input
              ref={inputRef}
              type="search"
              name="q"
              placeholder="Search products…"
              aria-label="Search products"
              enterKeyHint="search"
              onChange={(e) => {
                setOpen(true);
                fetchResults(e);
              }}
              onFocus={(e) => {
                setOpen(true);
                fetchResults(e);
              }}
              onClick={(e) => {
                setOpen(true);
                fetchResults(e);
              }}
            />
          </>
        )}
      </SearchFormPredictive>

      {open && (
        <div className="tob-hsearch-drop">
          <SearchResultsPredictive>
            {({items, total, term, state, closeSearch}) => {
              const {products, collections, pages} = items;
              const handleClose = () => {
                closeSearch();
                setOpen(false);
              };
              // Empty field → predictive search is NOT run (it can't take an
              // empty term). Show a "browse all" shortcut to the full catalog.
              if (!term.current) {
                return (
                  <Link
                    className="tob-hsearch-all"
                    to="/collections/all"
                    onClick={handleClose}
                  >
                    Browse all products →
                  </Link>
                );
              }
              if (state === 'loading' && !total) {
                return <p className="tob-hsearch-msg">Loading products…</p>;
              }
              if (!total) {
                return (
                  <p className="tob-hsearch-msg">
                    No results for “{term.current}”.
                  </p>
                );
              }
              return (
                <>
                  <SearchResultsPredictive.Products
                    products={products}
                    closeSearch={handleClose}
                    term={term}
                  />
                  <SearchResultsPredictive.Collections
                    collections={collections}
                    closeSearch={handleClose}
                    term={term}
                  />
                  <SearchResultsPredictive.Pages
                    pages={pages}
                    closeSearch={handleClose}
                    term={term}
                  />
                  <Link
                    className="tob-hsearch-all"
                    to={`/search?q=${term.current}`}
                    onClick={handleClose}
                  >
                    View all results for “{term.current}” →
                  </Link>
                </>
              );
            }}
          </SearchResultsPredictive>
        </div>
      )}
    </div>
  );
}

/** Desktop nav links — hidden on mobile (CSS handles it) */
function DesktopNav() {
  return (
    <nav className="tob-hnav tob-hnav-desktop" role="navigation" aria-label="Main navigation">
      <NavLink to="/" end>Home</NavLink>
      {config.nav.map((l) => (
        <NavLink key={l.url} to={l.url}>{l.label}</NavLink>
      ))}
    </nav>
  );
}

/**
 * @param {{isLoggedIn: Promise<boolean>, cart: Promise<CartApiQueryFragment|null>}}
 */
function HeaderCtas({isLoggedIn, cart}) {
  const {open} = useAside();
  return (
    <nav className="tob-hcta" role="navigation" aria-label="Header actions">
      {/* Hamburger — always visible, opens the slide-in menu with nav links */}
      <button
        className="tob-hmob reset"
        aria-label="Open menu"
        onClick={() => open('mobile')}
      >
        <IconMenu />
      </button>
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
  const {open} = useAside();
  const {publish, shop, cart, prevCart} = useAnalytics();
  return (
    <button
      className="tob-hcart reset"
      aria-label={`Cart, ${count} item${count === 1 ? '' : 's'}`}
      onClick={() => {
        open('cart');
        publish('cart_viewed', {
          cart,
          prevCart,
          shop,
          url: typeof window !== 'undefined' ? window.location.href : '',
        });
      }}
    >
      <IconBag />
      {count > 0 && <span className="tob-hcart-count">{count}</span>}
    </button>
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
