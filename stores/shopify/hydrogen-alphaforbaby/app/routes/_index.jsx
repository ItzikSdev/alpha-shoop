import {useLoaderData, Link} from 'react-router';
import {config} from '~/lib/theme';
import {ProductItem} from '~/components/ProductItem';

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => [
  {title: `${config.brand.name} — ${config.hero.eyebrow}`},
  {name: 'description', content: config.hero.sub},
];

/**
 * @param {Route.LoaderArgs} args
 */
export async function loader(args) {
  return {...(await loadCriticalData(args))};
}

async function loadCriticalData({context}) {
  const products = [];
  let cursor = null;
  let hasNextPage = true;
  while (hasNextPage) {
    const {products: page} = await context.storefront.query(HOMEPAGE_PRODUCTS_QUERY, {
      cache: context.storefront.CacheShort(),
      variables: {first: 250, after: cursor},
    });
    products.push(...page.nodes);
    hasNextPage = page.pageInfo.hasNextPage;
    cursor = page.pageInfo.endCursor;
  }
  return {products};
}

export default function Homepage() {
  /** @type {LoaderReturnData} */
  const {products = []} = useLoaderData();
  return (
    <div className="tob-home">
      <Hero />
      <HomeCatalogGrid products={products} />
    </div>
  );
}

/**
 * The store's live catalog, straight after the hero (v1.43 §5B).
 *
 * Reuses ProductItem — the same card the collection pages render — instead of a
 * second bespoke grid, and reads from the storefront query, so newly published
 * products appear here with no manual edit.
 *
 * Two columns on mobile is the literal spec and holds there; desktop widens to
 * three purely so cards don't stretch on a large screen.
 */
function HomeCatalogGrid({products = []}) {
  if (!products.length) return null;
  return (
    <section className="tob-wrap" aria-label="All products">
      <div className="grid grid-cols-2 gap-3 py-3 md:grid-cols-3 md:gap-5">
        {products.map((product, i) => (
          <ProductItem key={product.id} product={product} loading={i < 4 ? 'eager' : undefined} />
        ))}
      </div>
    </section>
  );
}

function Hero() {
  const {hero} = config;
  return (
    <section className="tob-eh" aria-label="Featured">
      <div className="tob-eh-copy">
        <span className="tob-eh-eyebrow">
          <i className="tob-eh-rule" /> {hero.eyebrow}
        </span>
        <h1 className="tob-eh-title">
          {hero.headline}
          <br />
          <em>{hero.headlineEm}</em>
        </h1>
        <p className="tob-eh-sub">{hero.sub}</p>
        <div className="tob-eh-actions">
          <Link className="tob-eh-btn" to={hero.ctaLink} prefetch="intent">
            {hero.ctaText}
          </Link>
          {hero.secondaryText && (
            <Link className="tob-eh-link" to={hero.secondaryLink}>
              {hero.secondaryText}
            </Link>
          )}
        </div>
        {hero.stats?.length ? (
          <div className="tob-eh-stats">
            {hero.stats.map((s, i) => (
              <div key={s.label} style={{display: 'contents'}}>
                {i > 0 && <div className="tob-eh-statdiv" />}
                <div>
                  <div className="tob-eh-statnum">{s.num}</div>
                  <div className="tob-eh-statlabel">{s.label}</div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/* ─── GraphQL queries ────────────────────────────────────────────────────── */

const PRODUCT_FRAGMENT = `#graphql
  fragment HomeProduct on Product {
    id
    title
    handle
    availableForSale
    featuredImage { url altText width height }
    images(first: 2) { nodes { url altText width height } }
    media(first: 20) {
      nodes {
        ... on Video {
          id
          sources { url mimeType }
        }
      }
    }
    priceRange { minVariantPrice { amount currencyCode } }
  }
`;

const HOMEPAGE_PRODUCTS_QUERY = `#graphql
  ${PRODUCT_FRAGMENT}
  query HomepageProducts($first: Int!, $after: String) {
    products(first: $first, after: $after, sortKey: BEST_SELLING) {
      nodes { ...HomeProduct }
      pageInfo { hasNextPage endCursor }
    }
  }
`;
