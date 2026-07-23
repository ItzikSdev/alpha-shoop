import {useLoaderData, data} from 'react-router';
import {CartForm} from '@shopify/hydrogen';
import {CartMain} from '~/components/CartMain';
import {CartRecommendations} from '~/components/CartRecommendations';

// COMPLEMENTARY needs Shopify's ML/sales-history data a newer store may not have
// yet, so it can come back empty even when there are perfectly good products to
// suggest — RELATED (tag/type based) always has something. Ask for both, prefer
// COMPLEMENTARY, fall back to RELATED.
const RECOMMENDATIONS_QUERY = `#graphql
  fragment CartRecProduct on Product {
    id
    handle
    title
    featuredImage { url altText width height }
    priceRange { minVariantPrice { amount currencyCode } }
    selectedOrFirstAvailableVariant(ignoreUnknownOptions: true, selectedOptions: []) {
      id
      availableForSale
    }
  }
  query CartRecommendations($productId: ID!, $country: CountryCode, $language: LanguageCode)
    @inContext(country: $country, language: $language) {
    complementary: productRecommendations(productId: $productId, intent: COMPLEMENTARY) {
      ...CartRecProduct
    }
    related: productRecommendations(productId: $productId, intent: RELATED) {
      ...CartRecProduct
    }
  }
`;

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: `ALPHA FOR BABY — Cart`}];
};

/**
 * @type {HeadersFunction}
 */
export const headers = ({actionHeaders}) => actionHeaders;

/**
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  const {cart} = context;

  const formData = await request.formData();

  const {action, inputs} = CartForm.getFormInput(formData);

  if (!action) {
    throw new Error('No action provided');
  }

  let status = 200;
  let result;

  switch (action) {
    case CartForm.ACTIONS.LinesAdd:
      result = await cart.addLines(inputs.lines);
      break;
    case CartForm.ACTIONS.LinesUpdate:
      result = await cart.updateLines(inputs.lines);
      break;
    case CartForm.ACTIONS.LinesRemove:
      result = await cart.removeLines(inputs.lineIds);
      break;
    case CartForm.ACTIONS.DiscountCodesUpdate: {
      const formDiscountCode = inputs.discountCode;

      // User inputted discount code
      const discountCodes = formDiscountCode ? [formDiscountCode] : [];

      // Combine discount codes already applied on cart
      discountCodes.push(...inputs.discountCodes);

      result = await cart.updateDiscountCodes(discountCodes);
      break;
    }
    case CartForm.ACTIONS.GiftCardCodesAdd: {
      const formGiftCardCode = inputs.giftCardCode;

      const giftCardCodes = formGiftCardCode ? [formGiftCardCode] : [];

      result = await cart.addGiftCardCodes(giftCardCodes);
      break;
    }
    case CartForm.ACTIONS.GiftCardCodesRemove: {
      const appliedGiftCardIds = inputs.giftCardCodes;
      result = await cart.removeGiftCardCodes(appliedGiftCardIds);
      break;
    }
    case CartForm.ACTIONS.BuyerIdentityUpdate: {
      result = await cart.updateBuyerIdentity({
        ...inputs.buyerIdentity,
      });
      break;
    }
    default:
      throw new Error(`${action} cart action is not defined`);
  }

  const cartId = result?.cart?.id;
  const headers = cartId ? cart.setCartId(result.cart.id) : new Headers();
  const {cart: cartResult, errors, warnings} = result;

  let redirectTo = formData.get('redirectTo') ?? null;
  if (typeof redirectTo === 'string') {
    // Sentinel: "checkout" → send the shopper straight to Shopify checkout
    // (where accelerated / PayPal buttons appear once enabled in admin).
    if (redirectTo === 'checkout' && cartResult?.checkoutUrl) {
      redirectTo = cartResult.checkoutUrl;
    }
    if (redirectTo !== 'checkout') {
      status = 303;
      headers.set('Location', redirectTo);
    }
  }

  return data(
    {
      cart: cartResult,
      errors,
      warnings,
      analytics: {
        cartId,
      },
    },
    {status, headers},
  );
}

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({context}) {
  const {cart, storefront} = context;
  const cartResult = await cart.get();

  // Complementary-product upsell — Shopify's own recommendation intent, based
  // on whatever's already in the cart. Best-effort: an empty cart or a query
  // hiccup just means no recommendations row, never a broken cart page.
  let recommendations = [];
  const firstProductId = cartResult?.lines?.nodes?.[0]?.merchandise?.product?.id;
  if (firstProductId) {
    try {
      const {complementary, related} = await storefront.query(RECOMMENDATIONS_QUERY, {
        variables: {productId: firstProductId},
      });
      recommendations = complementary?.length ? complementary : related || [];
    } catch {
      recommendations = [];
    }
  }

  return {...cartResult, recommendations};
}

export default function Cart() {
  /** @type {LoaderReturnData} */
  const {recommendations, ...cart} = useLoaderData();

  return (
    <div className="cart">
      <h1>Cart</h1>
      <CartMain layout="page" cart={cart} />
      <CartRecommendations products={recommendations} />
    </div>
  );
}

/** @typedef {import('react-router').HeadersFunction} HeadersFunction */
/** @typedef {import('./+types/cart').Route} Route */
/** @typedef {import('@shopify/hydrogen').CartQueryDataReturn} CartQueryDataReturn */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
