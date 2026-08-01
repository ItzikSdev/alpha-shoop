// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerAddressUpdate
export const UPDATE_ADDRESS_MUTATION = `#graphql
  mutation customerAddressUpdate(
    $customerAccessToken: String!
    $address: MailingAddressInput!
    $id: ID!
    $language: LanguageCode
  ) @inContext(language: $language) {
    customerAddressUpdate(
      customerAccessToken: $customerAccessToken
      address: $address
      id: $id
    ) {
      customerAddress {
        id
      }
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerAddressDelete
export const DELETE_ADDRESS_MUTATION = `#graphql
  mutation customerAddressDelete(
    $customerAccessToken: String!
    $id: ID!
    $language: LanguageCode
  ) @inContext(language: $language) {
    customerAddressDelete(customerAccessToken: $customerAccessToken, id: $id) {
      deletedCustomerAddressId
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerAddressCreate
export const CREATE_ADDRESS_MUTATION = `#graphql
  mutation customerAddressCreate(
    $customerAccessToken: String!
    $address: MailingAddressInput!
    $language: LanguageCode
  ) @inContext(language: $language) {
    customerAddressCreate(
      customerAccessToken: $customerAccessToken
      address: $address
    ) {
      customerAddress {
        id
      }
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;

// NOTE: https://shopify.dev/docs/api/storefront/latest/mutations/customerDefaultAddressUpdate
export const UPDATE_DEFAULT_ADDRESS_MUTATION = `#graphql
  mutation customerDefaultAddressUpdate(
    $customerAccessToken: String!
    $addressId: ID!
    $language: LanguageCode
  ) @inContext(language: $language) {
    customerDefaultAddressUpdate(
      customerAccessToken: $customerAccessToken
      addressId: $addressId
    ) {
      customer {
        id
      }
      customerUserErrors {
        code
        field
        message
      }
    }
  }
`;
