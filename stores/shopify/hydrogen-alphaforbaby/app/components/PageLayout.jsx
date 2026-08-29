import {Await, NavLink, Link} from 'react-router';
import {Suspense, useId, useState, useEffect, useRef} from 'react';
import {Aside, useAside} from '~/components/Aside';
import {Footer} from '~/components/Footer';
import {Header} from '~/components/Header';
import {SignInPromo} from '~/components/SignInPromo';
import {TrustBanner} from '~/components/TrustBanner';
import {CartMain} from '~/components/CartMain';
import {
  SEARCH_ENDPOINT,
  SearchFormPredictive,
} from '~/components/SearchFormPredictive';
import {SearchResultsPredictive} from '~/components/SearchResultsPredictive';
import {config} from '~/lib/theme';

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
        {/* All drawers rendered here so they're inside .tob and get the CSS vars */}
        <MobileMenuAside />
        <CartAside cart={cart} />
        <SearchAside />
        <TrustBanner isLoggedIn={isLoggedIn} />
        <Header cart={cart} isLoggedIn={isLoggedIn} />
        <main>{children}</main>
        <Footer />
        <SignInPromo isLoggedIn={isLoggedIn} />
      </div>
    </Aside.Provider>
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

function MobileMenuAside() {
  return (
    <Aside type="mobile" heading="MENU">
      <MobileMenuNav />
    </Aside>
  );
}

/** Nav links inside the hamburger drawer — NavLink so active state works, close on click */
function MobileMenuNav() {
  const {close} = useAside();
  return (
    <nav className="tob-mob-nav" role="navigation" aria-label="Main navigation">
      {/* Cart + Account now live in the header next to the logo, not here. */}
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

/** @typedef {import('storefrontapi.generated').CartApiQueryFragment} CartApiQueryFragment */
