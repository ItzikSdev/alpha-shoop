// Admin API documents for the independent (non-Shopify-hosted) customer
// identity system. See app/lib/customer.js for how these are used.
//
// NOTE: no leading `#graphql` pragma on any of these — they're Admin API
// documents, and the `#graphql` comment makes graphql-codegen validate the
// string against the Storefront schema (see .graphqlrc.js), which doesn't
// have these Admin-only types/fields. Same convention as
// products.$handle.jsx's review metafield queries and
// admin.fix-collections.jsx.
//
// Auth data model: we do NOT use Shopify's own customer login/activation
// system at all. Shopify Customer records (via this Admin API) are used
// purely as CRM/order-linking data. Our own password hash and any OAuth
// provider identity are stored as private Admin-only metafields under the
// `custom_auth` namespace:
//   custom_auth.password_hash        — "pbkdf2$<iterations>$<salt>$<hash>" (see app/lib/password.js)
//   custom_auth.google_sub            — Google's `sub` claim, informational (see app/lib/customer.js for why lookup is by email, not this field)
//   custom_auth.apple_sub             — Apple's `sub` claim, informational
//   custom_auth.reset_token_hash      — sha256 hex digest of a one-time forgot-password token (never store the raw token — see app/lib/customer.js)
//   custom_auth.reset_token_expires   — ISO timestamp; token is rejected once past this

export const CUSTOMER_AUTH_METAFIELDS_FRAGMENT = `
  fragment CustomerAuthMetafields on Customer {
    passwordHash: metafield(namespace: "custom_auth", key: "password_hash") { value }
    googleSub: metafield(namespace: "custom_auth", key: "google_sub") { value }
    appleSub: metafield(namespace: "custom_auth", key: "apple_sub") { value }
    resetTokenHash: metafield(namespace: "custom_auth", key: "reset_token_hash") { value }
    resetTokenExpires: metafield(namespace: "custom_auth", key: "reset_token_expires") { value }
  }
`;

// custom_cart.cart_id — the Storefront API cart id this customer's cart
// currently lives under; used to restore/merge their cart across devices at
// login (see app/lib/cartSync.js). App state, not a secret — kept in its own
// namespace separate from custom_auth for clarity.
export const CUSTOMER_CART_METAFIELD_FRAGMENT = `
  fragment CustomerCartMetafield on Customer {
    cartId: metafield(namespace: "custom_cart", key: "cart_id") { value }
  }
`;

export const CUSTOMER_ADDRESS_ADMIN_FRAGMENT = `
  fragment CustomerAddressAdmin on MailingAddress {
    id
    firstName
    lastName
    company
    address1
    address2
    city
    province
    provinceCode
    country
    countryCodeV2
    zip
    phone
    formatted(withName: true)
  }
`;

export const CUSTOMER_PROFILE_FRAGMENT = `
  fragment CustomerProfileAdmin on Customer {
    id
    email
    firstName
    lastName
    phone
    defaultAddress {
      ...CustomerAddressAdmin
    }
    addressesV2(first: 20) {
      nodes {
        ...CustomerAddressAdmin
      }
    }
    ...CustomerAuthMetafields
    ...CustomerCartMetafield
  }
  ${CUSTOMER_ADDRESS_ADMIN_FRAGMENT}
  ${CUSTOMER_AUTH_METAFIELDS_FRAGMENT}
  ${CUSTOMER_CART_METAFIELD_FRAGMENT}
`;

// `customerByIdentifier` is an exact-match lookup (unlike the fuzzy
// `customers(query:)` search), which is what we want for "does an account
// with this email already exist" checks during login/register/OAuth.
export const CUSTOMER_BY_EMAIL_QUERY = `
  query CustomerByEmail($identifier: CustomerIdentifierInput!) {
    customerByIdentifier(identifier: $identifier) {
      ...CustomerProfileAdmin
    }
  }
  ${CUSTOMER_PROFILE_FRAGMENT}
`;

export const CUSTOMER_BY_ID_QUERY = `
  query CustomerById($id: ID!) {
    customer(id: $id) {
      ...CustomerProfileAdmin
    }
  }
  ${CUSTOMER_PROFILE_FRAGMENT}
`;

// Admin API's `customerCreate` does not send any activation/invite email —
// that only happens via the separate, never-called
// `customerSendAccountInviteEmail` mutation. `metafields` can be set inline
// on creation, so the password hash is written atomically with the customer.
export const CUSTOMER_CREATE_ADMIN_MUTATION = `
  mutation CustomerCreateAdmin($input: CustomerInput!) {
    customerCreate(input: $input) {
      customer {
        ...CustomerProfileAdmin
      }
      userErrors {
        field
        message
      }
    }
  }
  ${CUSTOMER_PROFILE_FRAGMENT}
`;

export const CUSTOMER_UPDATE_ADMIN_MUTATION = `
  mutation CustomerUpdateAdmin($input: CustomerInput!) {
    customerUpdate(input: $input) {
      customer {
        ...CustomerProfileAdmin
      }
      userErrors {
        field
        message
      }
    }
  }
  ${CUSTOMER_PROFILE_FRAGMENT}
`;

export const METAFIELDS_SET_MUTATION = `
  mutation SetCustomAuthMetafields($metafields: [MetafieldsSetInput!]!) {
    metafieldsSet(metafields: $metafields) {
      metafields { id key namespace }
      userErrors { field message }
    }
  }
`;

// NOTE: verified against a live introspection query against this shop's own
// Admin API (2025-01) — the payload field is \`address\`, not \`customerAddress\`
// (the name graphql-codegen's Storefront-schema-derived naming convention
// would suggest). There is also no separate "set as default" mutation in
// this API version; both create and update take a \`setAsDefault\` arg
// directly instead of the classic Storefront API's dedicated
// customerDefaultAddressUpdate mutation.
export const CUSTOMER_ADDRESS_CREATE_MUTATION = `
  mutation CustomerAddressCreateAdmin($customerId: ID!, $address: MailingAddressInput!, $setAsDefault: Boolean) {
    customerAddressCreate(customerId: $customerId, address: $address, setAsDefault: $setAsDefault) {
      address {
        ...CustomerAddressAdmin
      }
      userErrors { field message }
    }
  }
  ${CUSTOMER_ADDRESS_ADMIN_FRAGMENT}
`;

export const CUSTOMER_ADDRESS_UPDATE_MUTATION = `
  mutation CustomerAddressUpdateAdmin($customerId: ID!, $addressId: ID!, $address: MailingAddressInput!, $setAsDefault: Boolean) {
    customerAddressUpdate(customerId: $customerId, addressId: $addressId, address: $address, setAsDefault: $setAsDefault) {
      address {
        ...CustomerAddressAdmin
      }
      userErrors { field message }
    }
  }
  ${CUSTOMER_ADDRESS_ADMIN_FRAGMENT}
`;

export const CUSTOMER_ADDRESS_DELETE_MUTATION = `
  mutation CustomerAddressDeleteAdmin($customerId: ID!, $addressId: ID!) {
    customerAddressDelete(customerId: $customerId, addressId: $addressId) {
      deletedAddressId
      userErrors { field message }
    }
  }
`;

// Top-level `orders(query:)` (rather than `customer.orders`) so the same
// `name:`/`confirmation_number:` search syntax the store already used
// (app/lib/orderFilters.js) keeps working — just scoped with an extra
// `customer_id:<id>` clause so a customer can only ever search their own
// orders.
export const CUSTOMER_ORDERS_ADMIN_QUERY = `
  query CustomerOrdersAdmin($query: String, $first: Int, $last: Int, $after: String, $before: String) {
    orders(query: $query, first: $first, last: $last, after: $after, before: $before, sortKey: PROCESSED_AT, reverse: true) {
      nodes {
        id
        name
        processedAt
        displayFinancialStatus
        displayFulfillmentStatus
        statusPageUrl
        currentTotalPriceSet { shopMoney { amount currencyCode } }
      }
      pageInfo { hasNextPage hasPreviousPage startCursor endCursor }
    }
  }
`;

export const ORDER_BY_ID_ADMIN_QUERY = `
  query OrderByIdAdmin($id: ID!) {
    order(id: $id) {
      id
      name
      processedAt
      displayFinancialStatus
      displayFulfillmentStatus
      statusPageUrl
      customer { id }
      currentSubtotalPriceSet { shopMoney { amount currencyCode } }
      currentTotalTaxSet { shopMoney { amount currencyCode } }
      currentTotalPriceSet { shopMoney { amount currencyCode } }
      shippingAddress {
        name
        formatted(withName: true)
      }
      lineItems(first: 100) {
        nodes {
          title
          quantity
          variant { id title image { url altText } }
          originalTotalSet { shopMoney { amount currencyCode } }
          discountedTotalSet { shopMoney { amount currencyCode } }
        }
      }
    }
  }
`;
