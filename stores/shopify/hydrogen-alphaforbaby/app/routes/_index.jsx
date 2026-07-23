import {useLoaderData, Link} from 'react-router';
import {useEffect, useState, useRef} from 'react';
import {Image, Money} from '@shopify/hydrogen';
import {config} from '~/lib/theme';

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [
    {title: `${config.brand.name} — ${config.hero.eyebrow}`},
    {name: 'description', content: config.hero.sub},
  ];
};

/**
 * @param {Route.LoaderArgs} args
 */
export async function loader(args) {
  const criticalData = await loadCriticalData(args);
  return {...criticalData};
}

async function loadCriticalData({context}) {
  // Load featured products + all 3 category collections in parallel
  const [
    {products},
    boysData,
    girlsData,
    unisexData,
  ] = await Promise.all([
    context.storefront.query(HOMEPAGE_PRODUCTS_QUERY, {
      cache: context.storefront.CacheShort(),
      variables: {first: config.productGridLimit ?? 12},
    }),
    context.storefront.query(COLLECTION_PRODUCTS_QUERY, {
      cache: context.storefront.CacheShort(),
      variables: {handle: 'baby-boys', first: 12},
    }),
    context.storefront.query(COLLECTION_PRODUCTS_QUERY, {
      cache: context.storefront.CacheShort(),
      variables: {handle: 'baby-girls', first: 12},
    }),
    context.storefront.query(COLLECTION_PRODUCTS_QUERY, {
      cache: context.storefront.CacheShort(),
      variables: {handle: 'unisex', first: 12},
    }),
  ]);

  return {
    products,
    collectionProducts: {
      'baby-boys':  boysData?.collection?.products?.nodes   ?? [],
      'baby-girls': girlsData?.collection?.products?.nodes  ?? [],
      'unisex':     unisexData?.collection?.products?.nodes ?? [],
    },
  };
}

export default function Homepage() {
  /** @type {LoaderReturnData} */
  const data = useLoaderData();
  const products = data.products?.nodes ?? [];
  const collectionProducts = data.collectionProducts ?? {};

  return (
    <div className="tob-home">
      <Hero />
      <Pills />
      <div className="tob-wrap">
        <CategoryTiles collectionProducts={collectionProducts} />
        <ProductGrid products={products} />
      </div>
      <Testimonials />
    </div>
  );
}

function Hero() {
  const {hero} = config;
  const images = hero.images ?? [];
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (images.length < 2) return;
    const id = setInterval(
      () => setActive((i) => (i + 1) % images.length),
      4000,
    );
    return () => clearInterval(id);
  }, [images.length]);
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
      <div className="tob-eh-media">
        {images.map((src, i) => (
          <img
            key={src}
            className={`tob-eh-slide${i === active ? ' active' : ''}`}
            src={src}
            alt=""
            loading={i === 0 ? 'eager' : 'lazy'}
          />
        ))}
        <div className="tob-eh-fade" />
        {images.length > 1 && (
          <div className="tob-eh-dots">
            {images.map((_, i) => (
              <button
                key={i}
                className={`tob-eh-dot${i === active ? ' active' : ''}`}
                aria-label={`Slide ${i + 1}`}
                onClick={() => setActive(i)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function Pills() {
  return (
    <div className="tob-pills">
      {config.pills.map((p) => (
        <div key={p}>{p}</div>
      ))}
    </div>
  );
}

/* ─── Category Tiles with inline product expand ─────────────────────────── */
function CategoryTiles({collectionProducts}) {
  const [openKey, setOpenKey] = useState(null); // handle of the open tile
  const panelRef = useRef(null);

  // derive the handle from the tile URL  e.g. "/collections/baby-boys" → "baby-boys"
  function handleFromUrl(url) {
    return url.split('/').pop();
  }

  function toggle(handle) {
    setOpenKey((prev) => (prev === handle ? null : handle));
  }

  // scroll the panel into view when it opens
  useEffect(() => {
    if (openKey && panelRef.current) {
      panelRef.current.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }
  }, [openKey]);

  return (
    <>
      <div className="tob-sec-head">
        <h2>{config.categoryHeading}</h2>
      </div>

      {/* Tiles row */}
      <div className="tob-tiles">
        {config.tiles.map((t) => {
          const handle = handleFromUrl(t.link);
          const isOpen = openKey === handle;
          return (
            <button
              key={t.link}
              className={`tob-tile tob-tile-btn${isOpen ? ' tob-tile-open' : ''}`}
              onClick={() => toggle(handle)}
              aria-expanded={isOpen}
              aria-controls={`tob-catpanel-${handle}`}
            >
              <img
                className="tob-tile-img"
                src={t.image}
                alt={t.label}
                loading="lazy"
              />
              <span>
                {t.label}
                <svg
                  className="tob-tile-chevron"
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M5 7.5L10 12.5L15 7.5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          );
        })}
      </div>

      {/* Inline product panel — renders BELOW the tiles row */}
      {config.tiles.map((t) => {
        const handle = handleFromUrl(t.link);
        const isOpen = openKey === handle;
        const items = collectionProducts[handle] ?? [];
        return (
          <div
            key={handle}
            id={`tob-catpanel-${handle}`}
            ref={isOpen ? panelRef : null}
            className={`tob-catpanel${isOpen ? ' tob-catpanel-open' : ''}`}
            aria-hidden={!isOpen}
          >
            {isOpen && (
              <>
                <div className="tob-catpanel-head">
                  <span>{t.label}</span>
                  <Link to={t.link} prefetch="intent" className="tob-catpanel-viewall">
                    View all →
                  </Link>
                </div>
                {items.length === 0 ? (
                  <p className="tob-catpanel-empty">No products found.</p>
                ) : (
                  <div className="tob-grid tob-catpanel-grid">
                    {items.map((product, i) => (
                      <HomeProductCard
                        key={product.id}
                        product={product}
                        index={i}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </>
  );
}

function ProductGrid({products}) {
  if (!products.length) return null;
  return (
    <>
      <div className="tob-sec-head">
        <h2>{config.productGridHeading}</h2>
        <Link to="/collections/all">View all</Link>
      </div>
      <div className="tob-grid">
        {products.map((product, i) => (
          <HomeProductCard key={product.id} product={product} index={i} />
        ))}
      </div>
    </>
  );
}

function HomeProductCard({product, index}) {
  const image = product.featuredImage;
  return (
    <Link
      to={`/products/${product.handle}`}
      className="tob-card"
      prefetch="intent"
      style={{animationDelay: `${Math.min(index, 8) * 60}ms`}}
    >
      <div className="tob-imgwrap">
        {image && (
          <Image
            data={image}
            alt={image.altText || product.title}
            aspectRatio="3/4"
            sizes="(min-width: 820px) 300px, 45vw"
            loading={index < 4 ? 'eager' : 'lazy'}
          />
        )}
      </div>
      <h3>{product.title}</h3>
      <div className="tob-price">
        <Money data={product.priceRange.minVariantPrice} />
        {!product.availableForSale && (
          <span className="tob-soldout">Sold out</span>
        )}
      </div>
    </Link>
  );
}

function Testimonials() {
  return (
    <section className="tob-wrap tob-testimonials">
      <div className="tob-sec-head">
        <h2>{config.testimonialsHeading}</h2>
      </div>
      <div className="tob-tgrid">
        {config.testimonials.map((t, i) => (
          <div key={t.author ?? i} className="tob-tcard">
            <div className="tob-tstars" aria-label={`${t.stars} stars`}>
              {'★'.repeat(t.stars)}
            </div>
            <p className="tob-ttext">"{t.text}"</p>
            <div className="tob-tauthor">
              <span className="tob-tname">{t.author}</span>
              {t.verified && (
                <span className="tob-tverified">✓ Verified buyer</span>
              )}
            </div>
          </div>
        ))}
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
    priceRange { minVariantPrice { amount currencyCode } }
  }
`;

const HOMEPAGE_PRODUCTS_QUERY = `#graphql
  ${PRODUCT_FRAGMENT}
  query HomepageProducts($first: Int!) {
    products(first: $first, sortKey: BEST_SELLING) {
      nodes { ...HomeProduct }
    }
  }
`;

const COLLECTION_PRODUCTS_QUERY = `#graphql
  ${PRODUCT_FRAGMENT}
  query CollectionProducts($handle: String!, $first: Int!) {
    collection(handle: $handle) {
      products(first: $first) {
        nodes { ...HomeProduct }
      }
    }
  }
`;
