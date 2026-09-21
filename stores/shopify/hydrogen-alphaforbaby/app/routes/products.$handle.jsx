import {useLoaderData} from 'react-router';
import {Star} from 'lucide-react';
import {
  getSelectedProductOptions,
  getSeoMeta,
  Analytics,
  useOptimisticVariant,
  getProductOptions,
  getAdjacentAndFirstAvailableVariants,
  useSelectedOptionInUrlParam,
} from '@shopify/hydrogen';
import {discountPercent} from '~/components/ProductPrice';
import {PdpGallery} from '~/components/pdp/PdpGallery';
import {PdpSpecs, parseSpecs} from '~/components/pdp/PdpSpecs';
import {PdpReviews, parseReviews} from '~/components/pdp/PdpReviews';
import {PdpHowToUse} from '~/components/pdp/PdpHowToUse';
import {PdpAccordion} from '~/components/pdp/PdpAccordion';
import {PdpMiniReviews} from '~/components/pdp/PdpMiniReviews';
import {PdpUrgencyStrip} from '~/components/pdp/PdpUrgencyStrip';
import {PdpQuantityTiers} from '~/components/pdp/PdpQuantityTiers';
import {StarRating} from '~/components/pdp/StarRating';
import {
  PdpBenefits,
  PdpWhyItWorks,
  PdpLifestyle,
  PdpComparison,
  PdpGuarantee,
} from '~/components/pdp/PdpSections';
import {redirectIfHandleIsLocalized} from '~/lib/redirect';
import {config} from '~/lib/theme';

/**
 * @type {Route.MetaFunction}
 */
export const meta = ({data}) => {
  if (!data?.product) return [{title: config.brand.name}];
  const {product, url} = data;
  const firstImage = product.images?.nodes?.[0];

  return getSeoMeta({
    title: product.seo?.title || product.title,
    titleTemplate: `${config.brand.name} — %s`,
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
      brand: {'@type': 'Brand', name: config.brand.name},
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
  const criticalData = await loadCriticalData(args);
  return {...criticalData};
}

/** Parse a JSON metafield into an object; never throws. */
function safeJson(value) {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

/**
 * @param {Route.LoaderArgs}
 */
async function loadCriticalData({context, params, request}) {
  const {handle} = params;
  const {storefront} = context;

  if (!handle) throw new Error('Expected product handle to be defined');

  const {product} = await storefront.query(PRODUCT_QUERY, {
    variables: {handle, selectedOptions: getSelectedProductOptions(request)},
  });

  if (!product?.id) throw new Response(null, {status: 404});

  redirectIfHandleIsLocalized(request, {handle, data: product});

  // 7.D #6/#35: the AG Product Reviews blob carries the supplier's own CDN
  // hostnames inside its review images. Only its approved-count summary is
  // used, so compute that here and keep the raw blob out of the serialized
  // loader payload — otherwise the supplier's domain ships in the DOM of every
  // product page even though no <img> ever points at it.
  const {agReviews, ...productPublic} = product;
  const reviews = parseReviews(product.reviews?.value);

  return {
    product: productPublic,
    url: `${config.brand.canonicalDomain}/products/${product.handle}`,
    reviews,
    specs: parseSpecs(product.specs?.value),
    // Structured page content (benefits, usage steps, FAQ…) for THIS product.
    // Same best-effort JSON-metafield pattern: absent means those sections
    // simply don't render, rather than the page failing.
    content: safeJson(product.pdpContent?.value),
    // Real review total from the AG Product Reviews app (5-star approved count)
    // — used for the buyer strip so the number is never invented.
    agBuyerCount: (() => {
      const sum = safeJson(agReviews?.value)?.reviewSummary;
      const fromApp = sum
        ? Object.values(sum)
            .filter((v) => v && typeof v === 'object' && 'approved' in v)
            .reduce((a, v) => a + (v.approved || 0), 0)
        : 0;
      // Only the carrier has the AG app's data. Every other product's real
      // count lives in the imported `custom.reviews` metafield — also a real
      // count of real reviews, so the strip stays honest (Rule 1) instead of
      // silently disappearing on 8 of 9 pages (§5C row 5).
      return fromApp || reviews.length;
    })(),
  };
}

export default function Product() {
  /** @type {LoaderReturnData} */
  const {product, reviews, specs, content, agBuyerCount} = useLoaderData();

  const selectedVariant = useOptimisticVariant(
    product.selectedOrFirstAvailableVariant,
    getAdjacentAndFirstAvailableVariants(product),
  );

  useSelectedOptionInUrlParam(selectedVariant.selectedOptions);

  const productOptions = getProductOptions({
    ...product,
    selectedOrFirstAvailableVariant: selectedVariant,
  });

  const {title, descriptionHtml} = product;
  const price = selectedVariant?.price;
  const compareAtPrice = selectedVariant?.compareAtPrice;
  const off = discountPercent(price, compareAtPrice);
  const kicker = product.collections?.nodes?.[0]?.title || config.brand.name;
  const inStock = !!selectedVariant?.availableForSale;
  const avgRating = reviews.length
    ? reviews.reduce((a, r) => a + (r.rating || 0), 0) / reviews.length
    : 0;

  const images = product.images?.nodes ?? [];
  const video = (product.media?.nodes ?? [])
    .flatMap((n) => n.sources ?? [])
    .find((s) => s.mimeType === 'video/mp4');

  return (
    <div className="pdp bg-surface font-classical text-ink text-cbody">
      <div className="relative mx-auto w-full max-w-phone bg-bg shadow-cmd md:max-w-[1320px]">
        <div className="md:grid md:grid-cols-[715px_minmax(0,1fr)] md:items-start md:gap-12 md:px-8 md:pt-6">
          <div className="px-4 md:sticky md:top-24 md:px-0">
            <PdpGallery
              images={images}
              selectedVariantImage={selectedVariant?.image}
              title={title}
            />
          </div>

          <div className="md:min-w-0">
            <PdpUrgencyStrip
              line={content?.urgencyLine}
              avatars={reviews.flatMap((r) => r.photos || []).slice(0, 5)}
              buyerCount={agBuyerCount}
            />

            <section className="px-4 pt-1.5 md:px-0">
              <h1 className="m-0 text-ch1 font-normal">{title}</h1>
              {reviews.length > 0 && (
                <div className="mt-0.5 flex items-center gap-1.5">
                  <StarRating value={avgRating} size={20} />
                  <a href="#reviews" className="text-[13px] text-ink/70 hover:underline">
                    ({reviews.length} Reviews)
                  </a>
                </div>
              )}
            </section>

            <section className="px-4 pt-2 md:px-0">
              <PdpQuantityTiers
                tiers={content?.quantityTiers || []}
                variant={selectedVariant}
                inStock={inStock}
                variants={product.allVariants?.nodes ?? []}
                benefits={content?.tierBenefits || {}}
                optionName={productOptions?.[0]?.name || 'Option'}
              />
            </section>

            {(config.paymentIcons || []).length > 0 && (
              <div className="flex flex-wrap items-center justify-center gap-2 px-4 pt-4 md:px-0">
                {config.paymentIcons.map((pi) => (
                  <img key={pi.src} src={pi.src} alt={pi.alt} width="34" height="23" loading="lazy" />
                ))}
              </div>
            )}

          </div>
        </div>

        <div className="px-4 md:mt-6 md:px-6">
          <hr className="hr" />
        </div>

        {/* §5 item 4 (v1.36): mini review carousel sits AFTER the entire buy-box
            block — past the CTA, payment row and trust row — and immediately
            before the benefit bullets. The old price/bundle gap stays closed. */}
        <div className="px-4 md:px-8">
          <PdpMiniReviews reviews={reviews} />
        </div>

        {/* v1.44 #10: the one real demo clip is primary content and now sits
            directly after the mini reviews. "Three ways to wear it" keeps its
            own explanatory steps lower down, without a second player. */}
        {video && (
          <div className="px-4 pt-3 md:px-8">
            {/* eslint-disable-next-line jsx-a11y/media-has-caption -- supplier clip has no caption track */}
            <video
              className="w-full rounded-lg bg-black"
              src={video.url}
              autoPlay
              muted
              loop
              playsInline
              preload="auto"
              style={{pointerEvents: 'none'}}
            />
          </div>
        )}

        {/* Skill §5C v1.53, Itzik's explicit order: the full "Ratings & Reviews"
            block sits IMMEDIATELY after the product video, before the benefit
            sections — it is no longer the last section on the page. id="reviews"
            stays here so the star row's "(N Reviews)" anchor still lands on it. */}
        <div id="reviews" className="mx-auto max-w-4xl px-4 md:px-6">
          <PdpReviews reviews={reviews} />
        </div>

        {/* Section order per skill §5C v1.53: mini carousel → video → Ratings &
            Reviews → benefits → size/shipping → how-to-use → why it works →
            lifestyle → comparison → full description/specs → FAQ → guarantee.
            pb-[100px] moved here: this block is now what the mobile sticky bar
            overlaps at the bottom of the page. */}
        <div className="mx-auto max-w-4xl px-4 pb-[100px] md:px-6">
          <PdpBenefits items={content?.benefits} />

          <PdpAccordion heading="Size guide & shipping" items={content?.sizeAndShipping}
            sectionId="size-and-shipping" />

          <PdpHowToUse content={content?.howToUse} images={images} video={null} title={title} />

          <PdpWhyItWorks content={content?.whyItWorks} />

          <PdpLifestyle content={content?.lifestyle} images={images} title={title} />

          <PdpComparison content={content?.comparison} />

          <section className="pt-10">
            <h2 className="m-0 text-ch2 font-normal">Full description</h2>
            <div
              className="mt-2 text-[15.5px] leading-[1.55] [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-[17px] [&_h2]:font-semibold [&_li]:mb-1 [&_p:last-child]:mb-0 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5"
              dangerouslySetInnerHTML={{__html: descriptionHtml}}
            />
          </section>

          <PdpSpecs specs={specs} />

          <PdpAccordion heading="Frequently asked questions" items={content?.faq} />

          <PdpGuarantee content={content?.guarantee} />
        </div>

        {/* Mobile-only sticky buy bar; the desktop two-column layout keeps the
            buy box on screen without one. */}
      </div>

      <Analytics.ProductView
        data={{
          products: [
            {
              id: product.id,
              title: product.title,
              price: selectedVariant?.price?.amount || '0',
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
    compareAtPrice { amount currencyCode }
    id
    image { __typename id url altText width height }
    price { amount currencyCode }
    product { title handle }
    selectedOptions { name value }
    sku
    title
    unitPrice { amount currencyCode }
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
    collections(first: 3) { nodes { handle title } }
    images(first: 50) { nodes { __typename id url altText width height } }
    media(first: 50) {
      nodes {
        ... on Video { id sources { url mimeType } }
      }
    }
    options {
      name
      optionValues {
        name
        firstSelectableVariant { ...ProductVariant }
        swatch { color image { previewImage { url } } }
      }
    }
    selectedOrFirstAvailableVariant(selectedOptions: $selectedOptions, ignoreUnknownOptions: true, caseInsensitiveMatch: true) {
      ...ProductVariant
    }
    adjacentVariants(selectedOptions: $selectedOptions) { ...ProductVariant }
    allVariants: variants(first: 100) { nodes { id title availableForSale price { amount currencyCode } image { url altText } } }
    seo { description title }
    reviews: metafield(namespace: "custom", key: "reviews") { value }
    specs: metafield(namespace: "custom", key: "specs") { value }
    pdpContent: metafield(namespace: "custom", key: "pdp_content") { value }
    agReviews: metafield(namespace: "air_reviews_product", key: "data") { value }
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
    product(handle: $handle) { ...Product }
  }
  ${PRODUCT_FRAGMENT}
`;

/** @typedef {import('./+types/products.$handle').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
