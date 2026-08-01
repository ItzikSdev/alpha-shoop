// NOTE: https://shopify.dev/docs/api/storefront/latest/objects/OrderLineItem
export const ORDER_LINE_ITEM_FRAGMENT = `#graphql
  fragment OrderLineItemFull on OrderLineItem {
    title
    quantity
    originalTotalPrice {
      amount
      currencyCode
    }
    discountedTotalPrice {
      amount
      currencyCode
    }
    variant {
      title
      image {
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
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/objects/Order
export const ORDER_FRAGMENT = `#graphql
  fragment OrderFull on Order {
    id
    name
    processedAt
    statusUrl
    financialStatus
    fulfillmentStatus
    currentSubtotalPrice {
      amount
      currencyCode
    }
    currentTotalTax {
      amount
      currencyCode
    }
    currentTotalPrice {
      amount
      currencyCode
    }
    shippingAddress {
      name
      formatted(withName: true)
      formattedArea
    }
    lineItems(first: 100) {
      nodes {
        ...OrderLineItemFull
      }
    }
  }
  ${ORDER_LINE_ITEM_FRAGMENT}
`;

// The classic Storefront API has no "fetch one order by id" root query — an
// order is only reachable through the authenticated customer's own order
// list (`customer(customerAccessToken) { orders { ... } }`), which is exactly
// what keeps this scoped to the signed-in customer. We fetch a generous page
// and the route finds the matching id. Revisit with real pagination if a
// customer ever has 250+ orders.
export const CUSTOMER_ORDER_QUERY = `#graphql
  query CustomerOrder(
    $customerAccessToken: String!
    $language: LanguageCode
  ) @inContext(language: $language) {
    customer(customerAccessToken: $customerAccessToken) {
      orders(first: 250, sortKey: PROCESSED_AT, reverse: true) {
        nodes {
          ...OrderFull
        }
      }
    }
  }
  ${ORDER_FRAGMENT}
`;
