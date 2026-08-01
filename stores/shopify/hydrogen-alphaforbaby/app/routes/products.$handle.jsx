import {useLoaderData} from 'react-router';
import {data as jsonData} from 'react-router';
import {
  getSelectedProductOptions,
  getSeoMeta,
  Analytics,
  useOptimisticVariant,
  getProductOptions,
  getAdjacentAndFirstAvailableVariants,
  useSelectedOptionInUrlParam,
} from '@shopify/hydrogen';
import {ProductPrice} from '~/components/ProductPrice';
import {ProductGallery} from '~/components/ProductGallery';
import {ProductForm} from '~/components/ProductForm';
import {FrequentlyBoughtTogether} from '~/components/FrequentlyBoughtTogether';
import {ProductReviews, parseReviews} from '~/components/ProductReviews';
import {redirectIfHandleIsLocalized} from '~/lib/redirect';
import {config} from '~/lib/theme';
import {normalizeSizeLabel} from '~/lib/sizeLabels';
import {shopifyAdminQuery} from '~/lib/shopifyAdmin';

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

  const {title, descriptionHtml, vendor} = product;

  return (
    <div className="tobp product">
      <div className="tobp-gallery">
        <ProductGallery
          images={product.images?.nodes}
          selectedVariantImage={selectedVariant?.image}
        />
      </div>
      <div className="product-main">
        <div className="tobp-brand">{vendor || config.brand.name}</div>
        <h1 className="tobp-title">{title}</h1>
        <ProductPrice
          price={selectedVariant?.price}
          compareAtPrice={selectedVariant?.compareAtPrice}
        />
        <ProductForm
          productOptions={productOptions}
          selectedVariant={selectedVariant}
        />
        <FrequentlyBoughtTogether
          mainProduct={{title, handle: product.handle, image: selectedVariant?.image, variant: selectedVariant}}
          extras={boughtTogether}
        />
        <div className="tobp-trust">
          {config.productPage.trustBadges.map((b) => (
            <span key={b}>{b}</span>
          ))}
        </div>
      </div>
      <div
        className="tobp-desc"
        dangerouslySetInnerHTML={{__html: descriptionHtml}}
      />
      <ProductReviews productId={product.id} reviews={reviews} />
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
