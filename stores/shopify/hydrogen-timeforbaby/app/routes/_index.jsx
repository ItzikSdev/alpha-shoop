import {useLoaderData, Link} from 'react-router';
import {useEffect, useState} from 'react';
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
  const [{products}] = await Promise.all([
    context.storefront.query(HOMEPAGE_PRODUCTS_QUERY, {
      cache: context.storefront.CacheShort(),
      variables: {first: config.productGridLimit ?? 12},
    }),
  ]);
  return {products};
}

export default function Homepage() {
  /** @type {LoaderReturnData} */
  const data = useLoaderData();
  const products = data.products?.nodes ?? [];
  return (
    <div className="tob-home">
      <Hero />
      <Pills />
      <div className="tob-wrap">
        <CategoryTiles />
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

function CategoryTiles() {
  return (
    <>
      <div className="tob-sec-head">
        <h2>{config.categoryHeading}</h2>
      </div>
      <div className="tob-tiles">
        {config.tiles.map((t) => (
          <Link key={t.link} to={t.link} className="tob-tile" prefetch="intent">
            <img className="tob-tile-img" src={t.image} alt={t.label} loading="lazy" />
            <span>{t.label}</span>
          </Link>
        ))}
      </div>
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
        {config.testimonials.map((r) => (
          <div className="tob-tcard" key={r.name}>
            <div className="tob-stars">★★★★★</div>
            <p>{r.text}</p>
            <div className="tob-tname">
              {r.name} · {r.location}{' '}
              <span className="tob-verified">✔ verified buyer</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

const HOMEPAGE_PRODUCTS_QUERY = `#graphql
  fragment HomeProduct on Product {
    id
    title
    handle
    availableForSale
    priceRange { minVariantPrice { amount currencyCode } }
    featuredImage { id url altText width height }
  }
  query HomepageProducts ($country: CountryCode, $language: LanguageCode, $first: Int)
    @inContext(country: $country, language: $language) {
    products(first: $first, sortKey: UPDATED_AT, reverse: true) {
      nodes { ...HomeProduct }
    }
  }
`;

/** @typedef {import('./+types/_index').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
