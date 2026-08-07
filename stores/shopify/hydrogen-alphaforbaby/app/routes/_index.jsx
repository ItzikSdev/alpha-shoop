import {useLoaderData, Link} from 'react-router';
import {useEffect, useRef, useState} from 'react';
import {Image, Money} from '@shopify/hydrogen';
import {RotateCw} from 'lucide-react';
import {config} from '~/lib/theme';
import {PromoBanner} from '~/components/PromoBanner';

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
  const data = useLoaderData();
  const products = data.products ?? [];

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
  const [videoOpen, setVideoOpen] = useState(true);
  const [videoMuted, setVideoMuted] = useState(true);
  const videoRef = useRef(null);

  useEffect(() => {
    if (images.length < 2) return;
    const id = setInterval(
      () => setActive((i) => (i + 1) % images.length),
      4000,
    );
    return () => clearInterval(id);
  }, [images.length]);

  useEffect(() => {
    if (!videoOpen || !videoRef.current) return;
    videoRef.current.currentTime = 0;
    videoRef.current.play().catch(() => {});
  }, [videoOpen]);

  function closeVideo() {
    videoRef.current?.pause();
    setVideoOpen(false);
  }

  function playVideo() {
    // A real click is a user gesture, so audio is allowed to play.
    setVideoMuted(false);
    setVideoOpen(true);
  }

  function toggleMute() {
    setVideoMuted((m) => !m);
  }

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
        <div className="mt-6">
          <PromoBanner />
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

        <div className={`tob-eh-video${videoOpen ? ' tob-eh-video-open' : ''}`}>
          {/* eslint-disable-next-line jsx-a11y/media-has-caption -- no caption track available for this clip */}
          <video
            ref={videoRef}
            className="tob-eh-video-el"
            src="/videos/hero-showcase.mp4"
            muted={videoMuted}
            playsInline
            onEnded={closeVideo}
          />
          <button
            type="button"
            className="tob-eh-video-mute"
            onClick={toggleMute}
            aria-label={videoMuted ? 'Unmute video' : 'Mute video'}
          >
            {videoMuted ? (
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path
                  d="M3 8v4h3l4 3V5L6 8H3Z"
                  fill="currentColor"
                />
                <path
                  d="M13.5 7.5L17 11M17 7.5L13.5 11"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M3 8v4h3l4 3V5L6 8H3Z" fill="currentColor" />
                <path
                  d="M13 6.5a5 5 0 0 1 0 7M15 4.5a8 8 0 0 1 0 11"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            )}
          </button>
          <button
            type="button"
            className="tob-eh-video-close"
            onClick={closeVideo}
            aria-label="Close video"
          >
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M5 5L15 15M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        {!videoOpen && (
          <button
            type="button"
            className="tob-eh-video-play"
            onClick={playVideo}
            aria-label="Play video"
          >
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M7 5L15 10L7 15V5Z" fill="currentColor" />
            </svg>
          </button>
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

/* ─── Category Tiles ──────────────────────────────────────────────────────── */
function CategoryTiles() {
  return (
    <>
      <div className="tob-sec-head">
        <h2>{config.categoryHeading}</h2>
      </div>

      <div className="tob-tiles">
        {config.tiles.map((t) => (
          <Link key={t.link} to={t.link} prefetch="intent" className="tob-tile">
            <img
              className="tob-tile-img"
              src={t.image}
              alt={t.label}
              loading="lazy"
            />
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
  // Reel's generated lifestyle photo is uploaded to gallery position 1 (position
  // 0 stays the supplier's photo, tied to color selection) — see
  // src/mcp_tools/shopify.py's attach_local_image_to_product.
  const galleryImages = product.images?.nodes ?? [];
  const image = galleryImages[1] || product.featuredImage;
  const videoSource = (product.media?.nodes ?? [])
    .flatMap((n) => n.sources ?? []).find((s) => s.mimeType === 'video/mp4');
  const [playingVideo, setPlayingVideo] = useState(false);
  return (
    <Link
      to={`/products/${product.handle}`}
      className="tob-card"
      prefetch="intent"
      style={{animationDelay: `${Math.min(index, 8) * 60}ms`}}
    >
      <div className="tob-imgwrap relative">
        {image && (
          <Image
            data={image}
            alt={image.altText || product.title}
            aspectRatio="3/4"
            sizes="(min-width: 820px) 300px, 45vw"
            loading={index < 4 ? 'eager' : 'lazy'}
          />
        )}
        {videoSource && playingVideo && (
          <video
            src={videoSource.url}
            autoPlay
            muted
            loop
            playsInline
            className="absolute inset-0 h-full w-full object-cover"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setPlayingVideo(false);
            }}
          />
        )}
        {videoSource && (
          <button
            type="button"
            aria-label={playingVideo ? 'Show photo' : 'Play 360° video'}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setPlayingVideo((v) => !v);
            }}
            className="absolute bottom-2 right-2 z-10 flex items-center gap-1 rounded-full bg-white/90 px-2 py-1 text-[11px] font-semibold shadow"
          >
            <RotateCw size={12} />
            360°
          </button>
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
