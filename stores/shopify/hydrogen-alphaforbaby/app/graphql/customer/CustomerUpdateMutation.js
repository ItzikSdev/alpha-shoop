// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerUpdate
export const CUSTOMER_UPDATE_MUTATION = `#graphql
  mutation customerUpdate(
    $customerAccessToken: String!
    $customer: CustomerUpdateInput!
    $language: LanguageCode
  ) @inContext(language: $language) {
    customerUpdate(customerAccessToken: $customerAccessToken, customer: $customer) {
      customer {
        firstName
        lastName
        email
        phone
      }
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;
