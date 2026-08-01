import {useLoaderData, Link} from 'react-router';

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({context}) {
  const data = await context.storefront.query(POLICIES_QUERY);

  const shopPolicies = data.shop;
  const policies = [
    shopPolicies?.privacyPolicy,
    shopPolicies?.shippingPolicy,
    shopPolicies?.termsOfService,
    shopPolicies?.refundPolicy,
    shopPolicies?.subscriptionPolicy,
  ].filter((policy) => policy != null);

  if (!policies.length) {
    throw new Response('No policies found', {status: 404});
  }

  return {policies};
}

export default function Policies() {
  /** @type {LoaderReturnData} */
  const {policies} = useLoaderData();

  return (
    <div className="policies-page">
      <h1>Policies</h1>
      <ul className="policies-list">
        {policies.map((policy) => (
          <li key={policy.id}>
            <Link to={`/policies/${policy.handle}`}>{policy.title}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

const POLICIES_QUERY = `#graphql
  fragment PolicyItem on ShopPolicy {
    id
    title
    handle
  }
  query Policies ($country: CountryCode, $language: LanguageCode)
    @inContext(country: $country, language: $language) {
    shop {
      privacyPolicy {
        ...PolicyItem
      }
      shippingPolicy {
        ...PolicyItem
      }
      termsOfService {
        ...PolicyItem
      }
      refundPolicy {
        ...PolicyItem
      }
      subscriptionPolicy {
        id
        title
        handle
      }
    }
  }
`;

/** @typedef {import('./+types/policies._index').Route} Route */
/** @typedef {import('storefrontapi.generated').PoliciesQuery} PoliciesQuery */
/** @typedef {import('storefrontapi.generated').PolicyItemFragment} PolicyItemFragment */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
