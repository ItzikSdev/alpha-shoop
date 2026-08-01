// Classic Storefront API customer auth (customerAccessTokenCreate) — NOT the
// OAuth Customer Account API. This is the replacement for the hosted OAuth
// login, which redirects through `shop.primaryDomain` (the Online Store
// channel's domain, not this Hydrogen channel's alphaforbaby.com) — a
// Shopify platform quirk for headless/multi-channel setups with no
// config-level fix. `customerAccessTokenCreate` never leaves this site.
// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerAccessTokenCreate
export const CUSTOMER_ACCESS_TOKEN_CREATE_MUTATION = `#graphql
  mutation customerAccessTokenCreate($input: CustomerAccessTokenCreateInput!) {
    customerAccessTokenCreate(input: $input) {
      customerAccessToken {
        accessToken
        expiresAt
      }
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerCreate
export const CUSTOMER_CREATE_MUTATION = `#graphql
  mutation customerCreate($input: CustomerCreateInput!) {
    customerCreate(input: $input) {
      customer {
        id
        email
      }
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerAccessTokenDelete
export const CUSTOMER_ACCESS_TOKEN_DELETE_MUTATION = `#graphql
  mutation customerAccessTokenDelete($customerAccessToken: String!) {
    customerAccessTokenDelete(customerAccessToken: $customerAccessToken) {
      deletedAccessToken
      deletedCustomerAccessTokenId
      userErrors {
        field
        message
      }
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/objects/MailingAddress
export const CUSTOMER_ADDRESS_FRAGMENT = `#graphql
  fragment CustomerAddress on MailingAddress {
    id
    formatted
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
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/objects/Customer
export const CUSTOMER_FRAGMENT = `#graphql
  fragment Customer on Customer {
    id
    firstName
    lastName
    email
    phone
    defaultAddress {
      ...CustomerAddress
    }
    addresses(first: 10) {
      nodes {
        ...CustomerAddress
      }
    }
  }
  ${CUSTOMER_ADDRESS_FRAGMENT}
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/queries/customer
export const CUSTOMER_QUERY = `#graphql
  query CustomerDetails($customerAccessToken: String!, $language: LanguageCode)
    @inContext(language: $language) {
    customer(customerAccessToken: $customerAccessToken) {
      ...Customer
    }
  }
  ${CUSTOMER_FRAGMENT}
`;
