import {getSchema} from '@shopify/hydrogen-codegen';

/**
 * GraphQL Config
 * @see https://the-guild.dev/graphql/config/docs/user/usage
 * @type {IGraphQLConfig}
 */
const graphqlConfig = {
  projects: {
    default: {
      schema: getSchema('storefront'),
      documents: [
        './*.{ts,tsx,js,jsx}',
        './app/**/*.{ts,tsx,js,jsx}',
        '!./app/graphql/**/*.{ts,tsx,js,jsx}',
      ],
    },

    customer: {
      // Classic Storefront API customer auth (customerAccessTokenCreate),
      // not the OAuth Customer Account API — see app/lib/customer.js.
      schema: getSchema('storefront'),
      documents: ['./app/graphql/customer/*.{ts,tsx,js,jsx}'],
    },

    // Add your own GraphQL projects here for CMS, Shopify Admin API, etc.
  },
};

export default graphqlConfig;

/** @typedef {import('graphql-config').IGraphQLConfig} IGraphQLConfig */
