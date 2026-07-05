import {Await, NavLink, Link} from 'react-router';
import {Suspense, useId} from 'react';
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

/** The top-level chrome. Everything is wrapped in `.tob` so the ported design CSS applies. */
export function PageLayout({cart, children = null, isLoggedIn}) {
  return (
    <Aside.Provider>
      <div className="tob">
        <AnnouncementMarquee />
        {/* Mobile/hamburger nav drawer */}
        <MobileMenuAside />
        <Header cart={cart} isLoggedIn={isLoggedIn} />
        <main>{children}</main>
        <Footer />
      </div>
    </Aside.Provider>
  );
}

function AnnouncementMarquee() {
  // duplicate the items so the -50% translate loop is seamless
  const items = [...MARQUEE, ...MARQUEE];
  return (
    <div className="tob-ann" role="complementary" aria-label="Announcements">
      <div className="tob-ann-track">
        {items.map((t, i) => (
          <span key={i}>{t}</span>
        ))}
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
