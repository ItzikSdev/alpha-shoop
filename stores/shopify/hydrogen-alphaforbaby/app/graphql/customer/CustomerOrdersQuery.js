// NOTE: https://shopify.dev/docs/api/storefront/latest/objects/Order
export const ORDER_ITEM_FRAGMENT = `#graphql
  fragment OrderItem on Order {
    id
    name
    orderNumber
    processedAt
    financialStatus
    fulfillmentStatus
    currentTotalPrice {
      amount
      currencyCode
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/queries/customer
export const CUSTOMER_ORDERS_QUERY = `#graphql
  query CustomerOrders(
    $customerAccessToken: String!
    $endCursor: String
    $first: Int
    $last: Int
    $startCursor: String
    $query: String
    $language: LanguageCode
  ) @inContext(language: $language) {
    customer(customerAccessToken: $customerAccessToken) {
      orders(
        sortKey: PROCESSED_AT
        reverse: true
        first: $first
        last: $last
        before: $startCursor
        after: $endCursor
        query: $query
      ) {
        nodes {
          ...OrderItem
        }
        pageInfo {
          hasPreviousPage
          hasNextPage
          endCursor
          startCursor
        }
      }
    }
  }
  ${ORDER_ITEM_FRAGMENT}
`;
