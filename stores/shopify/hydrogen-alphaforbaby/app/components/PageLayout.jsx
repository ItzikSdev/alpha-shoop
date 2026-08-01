import {Await, NavLink, Link} from 'react-router';
import {Suspense, useId, useState, useEffect, useRef} from 'react';
import {Aside, useAside} from '~/components/Aside';
import {Footer} from '~/components/Footer';
import {Header} from '~/components/Header';
import {CartMain} from '~/components/CartMain';
import {
  SEARCH_ENDPOINT,
  SearchFormPredictive,
} from '~/components/SearchFormPredictive';
import {SearchResultsPredictive} from '~/components/SearchResultsPredictive';
import {config} from '~/lib/theme';

// Dark scrolling announcement bar — from theme.config.json
const MARQUEE = config.announcement;
const PAY_ICONS = config.paymentIcons || [];

/**
 * Show the chrome (marquee + header) when at the top or scrolling UP; hide it
 * when scrolling DOWN. Returns 'up' | 'down'. Mobile-first: keeps the header
 * out of the way while browsing, brings it back the moment you scroll up.
 */
function useScrollDirection() {
  const [dir, setDir] = useState('up');
  const lastY = useRef(0);
  useEffect(() => {
    lastY.current = window.scrollY;
    let ticking = false;
    function onScroll() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(() => {
        const y = window.scrollY;
        const delta = y - lastY.current;
        // Ignore tiny jitters; always show near the very top.
        if (y < 60) {
          setDir('up');
        } else if (delta > 6) {
          setDir('down');
        } else if (delta < -6) {
          setDir('up');
        }
        lastY.current = y;
        ticking = false;
      });
    }
    window.addEventListener('scroll', onScroll, {passive: true});
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return dir;
}

/** The top-level chrome. Everything is wrapped in `.tob` so the ported design CSS applies. */
export function PageLayout({cart, children = null, isLoggedIn}) {
  const dir = useScrollDirection();
  return (
    <Aside.Provider>
      <div className={`tob tob-chrome-${dir}`}>
        <AnnouncementMarquee />
        {/* All drawers rendered here so they're inside .tob and get the CSS vars */}
        <MobileMenuAside isLoggedIn={isLoggedIn} />
        <CartAside cart={cart} />
        <SearchAside />
        <Header cart={cart} isLoggedIn={isLoggedIn} />
        <main>{children}</main>
        <Footer />
      </div>
    </Aside.Provider>
  );
}

function AnnouncementMarquee() {
  // one "unit" = all messages + the payment icons; duplicate it so the -50% loop is seamless
  const payGroup = PAY_ICONS.length ? (
    <span className="tob-ann-pay">
      {PAY_ICONS.map((p) => (
        <img
          key={p.src}
          src={p.src}
          alt={p.alt}
          className="tob-ann-pay-ico"
          width="34"
          height="23"
          loading="lazy"
        />
      ))}
    </span>
  ) : null;

  const unit = (
    <>
      {MARQUEE.map((t, i) => (
        <span key={i}>{t}</span>
      ))}
      {payGroup}
    </>
  );

  return (
    <div className="tob-ann" role="complementary" aria-label="Announcements">
      <div className="tob-ann-track">
        {unit}
        {unit}
      </div>
    </div>
  );
}

/**
 * @param {{cart: Promise<CartApiQueryFragment|null>}}
 */
function CartAside({cart}) {
  return (
    <Aside type="cart" heading="CART">
      <Suspense fallback={<p>Loading cart ...</p>}>
        <Await resolve={cart}>
          {(cart) => {
            return <CartMain cart={cart} layout="aside" />;
          }}
        </Await>
      </Suspense>
    </Aside>
  );
}

function SearchAside() {
  const queriesDatalistId = useId();
  return (
    <Aside type="search" heading="SEARCH">
      <div className="predictive-search">
        <br />
        <SearchFormPredictive>
          {({fetchResults, goToSearch, inputRef}) => (
            <>
              <input
                name="q"
                onChange={fetchResults}
                onFocus={fetchResults}
                placeholder="Search"
                ref={inputRef}
                type="search"
                list={queriesDatalistId}
              />
              &nbsp;
              <button onClick={goToSearch}>Search</button>
            </>
          )}
        </SearchFormPredictive>

        <SearchResultsPredictive>
          {({items, total, term, state, closeSearch}) => {
            const {articles, collections, pages, products, queries} = items;

            if (state === 'loading' && term.current) {
              return <div>Loading...</div>;
            }

            if (!total) {
              return <SearchResultsPredictive.Empty term={term} />;
            }

            return (
              <>
                <SearchResultsPredictive.Queries
                  queries={queries}
                  queriesDatalistId={queriesDatalistId}
                />
                <SearchResultsPredictive.Products
                  products={products}
                  closeSearch={closeSearch}
                  term={term}
                />
                <SearchResultsPredictive.Collections
                  collections={collections}
                  closeSearch={closeSearch}
                  term={term}
                />
                <SearchResultsPredictive.Pages
                  pages={pages}
                  closeSearch={closeSearch}
                  term={term}
                />
                <SearchResultsPredictive.Articles
                  articles={articles}
                  closeSearch={closeSearch}
                  term={term}
                />
                {term.current && total ? (
                  <Link
                    onClick={closeSearch}
                    to={`${SEARCH_ENDPOINT}?q=${term.current}`}
                  >
                    <p>
                      View all results for <q>{term.current}</q>
                      &nbsp; →
                    </p>
                  </Link>
                ) : null}
              </>
            );
          }}
        </SearchResultsPredictive>
      </div>
    </Aside>
  );
}

function MobileMenuAside({isLoggedIn}) {
  return (
    <Aside type="mobile" heading="MENU">
      <MobileMenuNav isLoggedIn={isLoggedIn} />
    </Aside>
  );
}

/** Nav links inside the hamburger drawer — NavLink so active state works, close on click */
function MobileMenuNav({isLoggedIn}) {
  const {close, open} = useAside();
  return (
    <nav className="tob-mob-nav" role="navigation" aria-label="Main navigation">
      {/* Cart + Account pinned to the top of the drawer (moved off the header) */}
      <div className="tob-mob-icons">
        <button
          type="button"
          className="tob-mob-ico reset"
          aria-label="Cart"
          onClick={() => open('cart')}
        >
          <MobileBagIcon />
          <span>Cart</span>
        </button>
        <MobileAccountLink isLoggedIn={isLoggedIn} onNavigate={close} />
      </div>
      <NavLink
        to="/"
        end
        className={({isActive}) => (isActive ? 'tob-mob-link tob-mob-link--active' : 'tob-mob-link')}
        onClick={close}
      >
        Home
      </NavLink>
      {config.nav.map((l) => (
        <NavLink
          key={l.url}
          to={l.url}
          className={({isActive}) => (isActive ? 'tob-mob-link tob-mob-link--active' : 'tob-mob-link')}
          onClick={close}
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  );
}

/**
 * @param {{isLoggedIn: Promise<boolean>, onNavigate: () => void}}
 */
function MobileAccountLink({isLoggedIn, onNavigate}) {
  return (
    <Suspense fallback={<MobileAccountLinkResolved loggedIn={false} onNavigate={onNavigate} />}>
      <Await resolve={isLoggedIn}>
        {(loggedIn) => (
          <MobileAccountLinkResolved loggedIn={loggedIn} onNavigate={onNavigate} />
        )}
      </Await>
    </Suspense>
  );
}

function MobileAccountLinkResolved({loggedIn, onNavigate}) {
  return (
    <Link
      to={loggedIn ? '/account' : '/account/login'}
      prefetch="intent"
      className="tob-mob-ico reset"
      aria-label={loggedIn ? 'Account' : 'Sign in'}
      onClick={onNavigate}
    >
      <MobileUserIcon />
      <span>{loggedIn ? 'Account' : 'Sign in'}</span>
    </Link>
  );
}

function MobileUserIcon() {
  return (
    <svg className="tob-ic" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="6.5" r="3.2" />
      <path d="M4 17c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" />
    </svg>
  );
}
function MobileBagIcon() {
  return (
    <svg className="tob-ic" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M5 6h10l1 11H4L5 6z" />
      <path d="M7.5 6V5a2.5 2.5 0 0 1 5 0v1" />
    </svg>
  );
}

/** @typedef {import('storefrontapi.generated').CartApiQueryFragment} CartApiQueryFragment */
