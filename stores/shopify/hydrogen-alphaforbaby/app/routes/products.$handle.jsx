import {useEffect, useState} from 'react';
import {useLoaderData} from 'react-router';
import {data as jsonData} from 'react-router';
import {Package, RotateCcw, Lock} from 'lucide-react';
import {
  Money,
  getSelectedProductOptions,
  getSeoMeta,
  Analytics,
  useOptimisticVariant,
  getProductOptions,
  getAdjacentAndFirstAvailableVariants,
  useSelectedOptionInUrlParam,
} from '@shopify/hydrogen';
import {ProductPrice, discountPercent} from '~/components/ProductPrice';
import {ProductGallery} from '~/components/ProductGallery';
import {ProductForm} from '~/components/ProductForm';
import {AddToCartButton} from '~/components/AddToCartButton';
import {FrequentlyBoughtTogether} from '~/components/FrequentlyBoughtTogether';
import {ProductReviews, parseReviews} from '~/components/ProductReviews';
import {ProductFAQ} from '~/components/ProductFAQ';
import {redirectIfHandleIsLocalized} from '~/lib/redirect';
import {config} from '~/lib/theme';
import {normalizeSizeLabel} from '~/lib/sizeLabels';
import {shopifyAdminQuery} from '~/lib/shopifyAdmin';

// Evergreen, product-agnostic value props (no per-product material/fit claims —
// this store's catalog is too varied across CJ suppliers for a single blanket
// "100% cotton" style claim to be true for every product).
const BENEFITS = [
  ['Gentle by design', 'Fabrics and fits chosen with sensitive baby skin in mind.'],
  ['Easy to dress', 'Simple closures made for wriggly mornings, not fights.'],
  ['Room to grow', 'A relaxed cut that keeps up with the next growth spurt.'],
  ['Built for play', 'Machine washable and made to survive a busy day.'],
];

const TRUST_ICONS = [Package, RotateCcw, Lock];

/** Counts down to local midnight — the daily sale-price reset shown under the price. */
function useMidnightCountdown(active) {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (!active) return;
    const tick = () => {
      const end = new Date();
      end.setHours(24, 0, 0, 0);
      setLeft(Math.max(0, Math.floor((end - Date.now()) / 1000)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [active]);
  const p = (n) => String(n).padStart(2, '0');
  return `${p(Math.floor(left / 3600))}:${p(Math.floor(left / 60) % 60)}:${p(left % 60)}`;
}

// Same COMPLEMENTARY→RELATED fallback pattern as the cart page (see cart.jsx) —
// COMPLEMENTARY needs Shopify ML/sales-history data this store doesn't have yet.
const PRODUCT_RECOMMENDATIONS_QUERY = `#graphql
  fragment FBTProduct on Product {
    id
    handle
    title
    featuredImage { url altText width height }
    selectedOrFirstAvailableVariant(ignoreUnknownOptions: true, selectedOptions: []) {
      id
      availableForSale
      price { amount currencyCode }
    }
  }
  query ProductRecommendations($productId: ID!, $country: CountryCode, $language: LanguageCode)
    @inContext(country: $country, language: $language) {
    complementary: productRecommendations(productId: $productId, intent: COMPLEMENTARY) {
      ...FBTProduct
    }
    related: productRecommendations(productId: $productId, intent: RELATED) {
      ...FBTProduct
    }
  }
`;

// Same category (Baby Boys / Baby Girls / Unisex, via the product's own collection)
// + same age bucket (via the Size option's cm value, using the exact bucketing the
// size buttons and size guide already use — see lib/sizeLabels.js) as the product
// being viewed. Only falls back to Shopify's generic productRecommendations (above)
// when nothing in-collection matches the age bucket.
const PRODUCTS_BY_COLLECTION_FOR_FBT_QUERY = `#graphql
  query ProductsByCollectionForFBT($handle: String!, $first: Int!, $country: CountryCode, $language: LanguageCode)
    @inContext(country: $country, language: $language) {
    collection(handle: $handle) {
      products(first: $first) {
        nodes {
          id
          handle
          title
          featuredImage { url altText width height }
          variants(first: 50) {
            nodes {
              id
              availableForSale
              price { amount currencyCode }
              selectedOptions { name value }
            }
          }
        }
      }
    }
  }
`;

/** The age bucket (e.g. "3-6 Months") for a variant's Size option, or null if this
 * product has no real cm-based Size option (e.g. a color-only product). */
function ageBucketFromOptions(selectedOptions) {
  const sizeOpt = (selectedOptions || []).find((o) => o.name.toLowerCase() === 'size');
  if (!sizeOpt) return null;
  const label = normalizeSizeLabel(sizeOpt.value);
  // normalizeSizeLabel returns the raw value unchanged when it isn't an "NNcm"
  // pattern — treat that as "no real age bucket" rather than a false match.
  return label !== sizeOpt.value ? label : null;
}

/** Same-collection, same-age-bucket picks for "Frequently bought together" — the
 * whole point being a Baby Boys 3-6 Months product recommends OTHER Baby Boys
 * 3-6 Months products (and a Baby Girls 6-9 Months product recommends other Baby
 * Girls 6-9 Months products), not Shopify's generic co-purchase guess. */
async function attributeMatchedBoughtTogether(storefront, product) {
  const ageBucket = ageBucketFromOptions(product.selectedOrFirstAvailableVariant?.selectedOptions);
  const collectionHandle = product.collections?.nodes?.[0]?.handle;
  if (!ageBucket || !collectionHandle) return [];

  const {collection} = await storefront.query(PRODUCTS_BY_COLLECTION_FOR_FBT_QUERY, {
    variables: {handle: collectionHandle, first: 20},
  });
  const candidates = collection?.products?.nodes || [];

  return candidates
    .filter((p) => p.id !== product.id)
    .map((p) => {
      const match = (p.variants?.nodes || []).find(
        (v) => v.availableForSale && ageBucketFromOptions(v.selectedOptions) === ageBucket,
      );
      if (!match) return null;
      return {
        id: p.id,
        handle: p.handle,
        title: p.title,
        featuredImage: p.featuredImage,
        selectedOrFirstAvailableVariant: {
          id: match.id,
          availableForSale: match.availableForSale,
          price: match.price,
        },
      };
    })
    .filter(Boolean)
    .slice(0, 2);
}

/**
 * @type {Route.MetaFunction}
 */
export const meta = ({data}) => {
  if (!data?.product) return [{title: 'ALPHA FOR BABY'}];
  const {product, url} = data;
  const firstImage = product.images?.nodes?.[0];

  return getSeoMeta({
    title: product.seo?.title || product.title,
    titleTemplate: 'ALPHA FOR BABY — %s',
    description: product.seo?.description || product.description,
    url,
    media: firstImage && {
      type: 'image',
      url: firstImage.url,
      width: firstImage.width,
      height: firstImage.height,
      altText: firstImage.altText,
    },
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'Product',
      name: product.title,
      description: product.seo?.description || product.description,
      image: firstImage?.url,
      brand: {
        '@type': 'Brand',
        name: config.brand.name,
      },
      offers: product.selectedOrFirstAvailableVariant?.price
        ? {
            '@type': 'Offer',
            priceCurrency: product.selectedOrFirstAvailableVariant.price.currencyCode,
            price: product.selectedOrFirstAvailableVariant.price.amount,
            availability: product.selectedOrFirstAvailableVariant.availableForSale
              ? 'https://schema.org/InStock'
              : 'https://schema.org/OutOfStock',
          }
        : undefined,
    },
  });
};

/**
 * @param {Route.LoaderArgs} args
 */
export async function loader(args) {
  // Start fetching non-critical data without blocking time to first byte
  const deferredData = loadDeferredData(args);

  // Await the critical data required to render initial state of the page
  const criticalData = await loadCriticalData(args);

  return {...deferredData, ...criticalData};
}

/**
 * Load data necessary for rendering content above the fold. This is the critical data
 * needed to render the page. If it's unavailable, the whole page should 400 or 500 error.
 * @param {Route.LoaderArgs}
 */
async function loadCriticalData({context, params, request}) {
  const {handle} = params;
  const {storefront} = context;

  if (!handle) {
    throw new Error('Expected product handle to be defined');
  }

  const [{product}] = await Promise.all([
    storefront.query(PRODUCT_QUERY, {
      variables: {handle, selectedOptions: getSelectedProductOptions(request)},
    }),
    // Add other queries here, so that they are loaded in parallel
  ]);

  if (!product?.id) {
    throw new Response(null, {status: 404});
  }

  // The API handle might be localized, so redirect to the localized handle
  redirectIfHandleIsLocalized(request, {handle, data: product});

  // "Frequently bought together" — best-effort, never breaks the page. Prefer
  // same-collection + same-age-bucket picks (e.g. Baby Boys 3-6 Months → other Baby
  // Boys 3-6 Months products); only fall back to Shopify's generic
  // productRecommendations when this product has no real Size option or nothing in
  // its own collection matches its age bucket.
  let boughtTogether = [];
  try {
    boughtTogether = await attributeMatchedBoughtTogether(storefront, product);
  } catch {
    boughtTogether = [];
  }
  if (!boughtTogether.length) {
    try {
      const {complementary, related} = await storefront.query(PRODUCT_RECOMMENDATIONS_QUERY, {
        variables: {productId: product.id},
      });
      boughtTogether = (complementary?.length ? complementary : related || []).slice(0, 2);
    } catch {
      boughtTogether = [];
    }
  }

  return {
    product,
    url: `${config.brand.canonicalDomain}/products/${product.handle}`,
    boughtTogether,
    reviews: parseReviews(product.reviews?.value),
  };
}

// NOTE: no leading `#graphql` pragma on these two — they're Admin API
// documents (MetafieldsSetInput, metafieldsSet), and the `#graphql` comment
// makes graphql-codegen validate the string against the Storefront schema
// (see .graphqlrc.js), which doesn't have these Admin-only types. Same reason
// admin.fix-collections.jsx's queries skip the pragma too.
const REVIEWS_METAFIELD_QUERY = `
  query ProductReviewsMetafield($id: ID!) {
    product(id: $id) {
      metafield(namespace: "custom", key: "reviews") { value }
    }
  }
`;

const REVIEWS_METAFIELD_SET_MUTATION = `
  mutation SetProductReviews($metafields: [MetafieldsSetInput!]!) {
    metafieldsSet(metafields: $metafields) {
      userErrors { field message }
    }
  }
`;

// Reviews are appended into a single JSON metafield rather than a real reviews
// app/table (this store has no reviews app installed) — cap the array so a
// popular product's metafield never approaches Shopify's per-metafield size
// limit. Newest reviews are kept; oldest are dropped once the cap is hit.
const MAX_STORED_REVIEWS = 100;

/**
 * Handles the "Write a review" form submission (see ProductReviews.jsx).
 * Writes directly to Shopify's Admin API using a private (non-PUBLIC_) env
 * var — this never touches the local orchestrator backend, so it works the
 * same in production (Oxygen) as in local dev.
 * @param {Route.ActionArgs} args
 */
export async function action({request, context}) {
  if (request.method !== 'POST') {
    return jsonData({error: 'Method not allowed'}, {status: 405});
  }

  const form = await request.formData();

  // Honeypot: real customers never see or fill this field.
  if (String(form.get('website') || '').length > 0) {
    return jsonData({ok: true});
  }

  const productId = String(form.get('productId') || '');
  const name = String(form.get('name') || '').trim().slice(0, 80);
  const comment = String(form.get('comment') || '').trim().slice(0, 1000);
  const rating = Math.round(Number(form.get('rating')));

  if (!productId || !name || !comment || !Number.isFinite(rating) || rating < 1 || rating > 5) {
    return jsonData({error: 'Please add your name, a rating, and a review.'}, {status: 400});
  }

  try {
    const existing = await shopifyAdminQuery(context.env, REVIEWS_METAFIELD_QUERY, {id: productId});
    const reviews = parseReviews(existing?.product?.metafield?.value);

    reviews.unshift({
      id: crypto.randomUUID(),
      name,
      rating,
      comment,
      createdAt: new Date().toISOString(),
    });

    await shopifyAdminQuery(context.env, REVIEWS_METAFIELD_SET_MUTATION, {
      metafields: [{
        ownerId: productId,
        namespace: 'custom',
        key: 'reviews',
        type: 'json',
        value: JSON.stringify(reviews.slice(0, MAX_STORED_REVIEWS)),
      }],
    });

    return jsonData({ok: true});
  } catch (error) {
    console.error('[ProductReviews] failed to save review', error);
    return jsonData({error: "Sorry, we couldn't save your review — please try again."}, {status: 500});
  }
}

/**
 * Load data for rendering content below the fold. This data is deferred and will be
 * fetched after the initial page load. If it's unavailable, the page should still 200.
 * Make sure to not throw any errors here, as it will cause the page to 500.
 * @param {Route.LoaderArgs}
 */
function loadDeferredData({context, params}) {
  // Put any API calls that is not critical to be available on first page render
  // For example: product reviews, product recommendations, social feeds.

  return {};
}

export default function Product() {
  /** @type {LoaderReturnData} */
  const {product, boughtTogether, reviews} = useLoaderData();

  // Optimistically selects a variant with given available variant information
  const selectedVariant = useOptimisticVariant(
    product.selectedOrFirstAvailableVariant,
    getAdjacentAndFirstAvailableVariants(product),
  );

  // Sets the search param to the selected variant without navigation
  // only when no search params are set in the url
  useSelectedOptionInUrlParam(selectedVariant.selectedOptions);

  // Get the product options array
  const productOptions = getProductOptions({
    ...product,
    selectedOrFirstAvailableVariant: selectedVariant,
  });

  const {title, descriptionHtml} = product;
  const price = selectedVariant?.price;
  const compareAtPrice = selectedVariant?.compareAtPrice;
  const off = discountPercent(price, compareAtPrice);
  const timer = useMidnightCountdown(!!compareAtPrice);
  const kicker = product.collections?.nodes?.[0]?.title || product.vendor || config.brand.name;
  const trustBadges = config.productPage?.trustBadges || [];

  const captionParts = (selectedVariant?.selectedOptions || []).map((o) =>
    /^\d+cm$/i.test(o.value) ? normalizeSizeLabel(o.value) : o.value,
  );

  // Reel's generated lifestyle photo is always uploaded to gallery position 1
  // (position 0 stays the supplier's own photo, tied to color selection — see
  // src/mcp_tools/shopify.py's attach_local_image_to_product). Lead the
  // carousel with it so shoppers see the AI baby photo first.
  const rawImages = product.images?.nodes ?? [];
  const galleryImages =
    rawImages.length > 1
      ? [rawImages[1], ...rawImages.filter((_, i) => i !== 1)]
      : rawImages;
  const videoSource = (product.media?.nodes ?? [])
    .flatMap((n) => n.sources ?? [])
    .find((s) => s.mimeType === 'video/mp4');

  return (
    <div className="pdp bg-surface font-classical text-ink text-cbody">
      <div className="relative mx-auto w-full max-w-phone md:max-w-5xl bg-bg shadow-cmd">
        {/* promise strip — verified brand-level facts only (no fabricated claims) */}
        <div className="flex flex-wrap items-center justify-center gap-2 border-b border-divider px-4 py-2 text-[11px] uppercase tracking-[.08em] text-accent-700">
          <span>Free shipping</span>
          <span className="opacity-40">·</span>
          <span>30-day returns</span>
          <span className="opacity-40">·</span>
          <span>Secure checkout</span>
        </div>

        {/* Mobile: single column, phone-width (the approved handoff spec).
            Tablet/desktop (md+): gallery and buy-box sit side by side instead
            of staying pinned to a 430px column on a wide viewport. */}
        <div className="md:grid md:grid-cols-2 md:gap-10 md:px-6 md:pt-6 md:items-start">
          <div className="md:sticky md:top-24">
            <ProductGallery
              images={galleryImages}
              selectedVariantImage={selectedVariant?.image}
              discountPercent={off}
              videoSource={videoSource}
            />
          </div>

          <div className="md:min-w-0">
            <section className="px-4 md:px-0">
              <h6 className="m-0 text-kicker uppercase tracking-[.08em] text-accent-700">{kicker}</h6>
              <h1 className="mt-2 text-ch1 font-normal">{title}</h1>
              <ProductPrice price={price} compareAtPrice={compareAtPrice} />
              {compareAtPrice && (
                <div className="tnum mt-[5px] text-[11.5px] text-ink/55">Sale price ends in {timer}</div>
              )}
            </section>

            <section className="px-4 md:px-0 pt-6">
              <ProductForm productOptions={productOptions} selectedVariant={selectedVariant} />
            </section>

            <div className="mt-6 px-4 md:px-0">
            </div>

            {trustBadges.length > 0 && (
              <section className="flex flex-col gap-4 px-4 md:px-0 pt-6">
                {trustBadges.map((badge, i) => {
                  const Icon = TRUST_ICONS[i % TRUST_ICONS.length];
                  return (
                    <div key={badge} className="flex items-start gap-3">
                      <Icon size={18} className="mt-[2px] flex-none text-accent" />
                      <p className="m-0 text-[13px] text-ink/70">{badge.replace(/^✓\s*/, '')}</p>
                    </div>
                  );
                })}
              </section>
            )}
          </div>
        </div>

        <div className="px-4 md:px-6 md:mt-6">
          <hr className="hr" />
        </div>

        <section className="px-4 md:px-6">
          <h6 className="m-0 text-kicker uppercase tracking-[.08em] text-accent-700">Description</h6>
          <div
            className="mt-2 text-[15.5px] leading-[1.55] [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5"
            dangerouslySetInnerHTML={{__html: descriptionHtml}}
          />
        </section>

        <section className="px-4 md:px-6 pt-6">
          <h2 className="m-0 text-ch2 font-normal">Why parents pick us</h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {BENEFITS.map(([heading, body]) => (
              <div key={heading} className="card">
                <span className="card-title">{heading}</span>
                <p className="card-body">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="px-4 md:px-6">
          <FrequentlyBoughtTogether
            mainProduct={{title, handle: product.handle, image: selectedVariant?.image, variant: selectedVariant}}
            extras={boughtTogether}
          />
        </div>

        <section className="px-4 md:px-6 pt-6 pb-6">
          <ProductReviews productId={product.id} reviews={reviews} />
        </section>

        <ProductFAQ />

        {/* sticky add-to-cart — mobile only; the desktop 2-col layout already
            keeps the buy box on screen without scrolling. */}
        <div className="sticky bottom-0 z-40 flex items-center gap-3 border-t border-divider bg-bg px-4 py-2 md:hidden">
          <div className="flex-none">
            <div className="tnum text-[16px] leading-snug">{price ? <Money data={price} /> : null}</div>
            <div className="text-[10.5px] text-ink/50">{captionParts.join(' · ')}</div>
          </div>
          <AddToCartButton
            disabled={!selectedVariant || !selectedVariant.availableForSale}
            redirectTo="/cart"
            className="btn btn-primary flex-1 min-w-0 min-h-[48px] tracking-[.08em]"
            lines={
              selectedVariant
                ? [{merchandiseId: selectedVariant.id, quantity: 1, selectedVariant}]
                : []
            }
          >
            {selectedVariant?.availableForSale ? 'ADD TO CART' : 'SOLD OUT'}
          </AddToCartButton>
          {/* PayPal express shortcut removed here too (2026-08-26) — this is
              a SEPARATE mobile-only sticky bar from ProductForm.jsx's
              buttons, missed in the first pass. Same reasoning: shortcut
              button only, not the actual PayPal payment method. */}
        </div>
      </div>
      <Analytics.ProductView
        data={{
          products: [
            {
              id: product.id,
              title: product.title,
              price: selectedVariant?.price.amount || '0',
              vendor: product.vendor,
              variantId: selectedVariant?.id || '',
              variantTitle: selectedVariant?.title || '',
              quantity: 1,
            },
          ],
        }}
      />
    </div>
  );
}

const PRODUCT_VARIANT_FRAGMENT = `#graphql
  fragment ProductVariant on ProductVariant {
    availableForSale
    compareAtPrice {
      amount
      currencyCode
    }
    id
    image {
      __typename
      id
      url
      altText
      width
      height
    }
    price {
      amount
      currencyCode
    }
    product {
      title
      handle
    }
    selectedOptions {
      name
      value
    }
    sku
    title
    unitPrice {
      amount
      currencyCode
    }
  }
`;

const PRODUCT_FRAGMENT = `#graphql
  fragment Product on Product {
    id
    title
    vendor
    handle
    descriptionHtml
    description
    encodedVariantExistence
    encodedVariantAvailability
    collections(first: 3) {
      nodes {
        handle
        title
      }
    }
    images(first: 50) {
      nodes {
        __typename
        id
        url
        altText
        width
        height
      }
    }
    media(first: 50) {
      nodes {
        ... on Video {
          id
          sources { url mimeType }
        }
      }
    }
    options {
      name
      optionValues {
        name
        firstSelectableVariant {
          ...ProductVariant
        }
        swatch {
          color
          image {
            previewImage {
              url
            }
          }
        }
      }
    }
    selectedOrFirstAvailableVariant(selectedOptions: $selectedOptions, ignoreUnknownOptions: true, caseInsensitiveMatch: true) {
      ...ProductVariant
    }
    adjacentVariants (selectedOptions: $selectedOptions) {
      ...ProductVariant
    }
    seo {
      description
      title
    }
    sizeGuide: metafield(namespace: "custom", key: "size_guide") {
      value
    }
    reviews: metafield(namespace: "custom", key: "reviews") {
      value
    }
  }
  ${PRODUCT_VARIANT_FRAGMENT}
`;

const PRODUCT_QUERY = `#graphql
  query Product(
    $country: CountryCode
    $handle: String!
    $language: LanguageCode
    $selectedOptions: [SelectedOptionInput!]!
  ) @inContext(country: $country, language: $language) {
    product(handle: $handle) {
      ...Product
    }
  }
  ${PRODUCT_FRAGMENT}
`;

/** @typedef {import('./+types/products.$handle').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
