import {
  data,
  Form,
  useActionData,
  useNavigation,
  useOutletContext,
} from 'react-router';
import {
  UPDATE_ADDRESS_MUTATION,
  DELETE_ADDRESS_MUTATION,
  CREATE_ADDRESS_MUTATION,
  UPDATE_DEFAULT_ADDRESS_MUTATION,
} from '~/graphql/customer/CustomerAddressMutations';
import {requireCustomer, getCustomerAccessToken} from '~/lib/customer';

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Addresses'}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  await requireCustomer(context, request);

  return {};
}

/**
 * @param {Route.ActionArgs}
 */
export async function action({request, context}) {
  const {storefront, session} = context;

  try {
    const form = await request.formData();

    const addressId = form.has('addressId')
      ? String(form.get('addressId'))
      : null;
    if (!addressId) {
      throw new Error('You must provide an address id.');
    }

    // this will ensure redirecting to login never happen for mutatation
    const customerAccessToken = getCustomerAccessToken(session);
    if (!customerAccessToken) {
      return data(
        {error: {[addressId]: 'Unauthorized'}},
        {
          status: 401,
        },
      );
    }

    const defaultAddress = form.has('defaultAddress')
      ? String(form.get('defaultAddress')) === 'on'
      : false;
    // Classic Storefront API's MailingAddressInput uses `country`/`province`/
    // `phone` (free-text country/province name, not the territoryCode/
    // zoneCode 2-letter codes the old Customer Account API input used).
    const address = {};
    const fieldMap = {
      address1: 'address1',
      address2: 'address2',
      city: 'city',
      company: 'company',
      territoryCode: 'country',
      firstName: 'firstName',
      lastName: 'lastName',
      phoneNumber: 'phone',
      zoneCode: 'province',
      zip: 'zip',
    };

    for (const [formKey, inputKey] of Object.entries(fieldMap)) {
      const value = form.get(formKey);
      if (typeof value === 'string') {
        address[inputKey] = value;
      }
    }

    // Sets the given address as the customer's default address, if requested.
    // (Classic Storefront API doesn't accept `defaultAddress` on create/update
    // mutations — it's a separate mutation.)
    async function applyDefaultAddress(resolvedAddressId) {
      if (!defaultAddress || !resolvedAddressId) return;
      const result = await storefront.mutate(UPDATE_DEFAULT_ADDRESS_MUTATION, {
        variables: {
          customerAccessToken,
          addressId: resolvedAddressId,
          language: storefront.i18n?.language,
        },
      });
      const userErrors = result?.customerDefaultAddressUpdate?.customerUserErrors;
      if (userErrors?.length) {
        throw new Error(userErrors[0].message);
      }
    }

    switch (request.method) {
      case 'POST': {
        // handle new address creation
        try {
          const result = await storefront.mutate(CREATE_ADDRESS_MUTATION, {
            variables: {
              customerAccessToken,
              address,
              language: storefront.i18n?.language,
            },
          });

          const userErrors = result?.customerAddressCreate?.customerUserErrors;
          if (userErrors?.length) {
            throw new Error(userErrors[0].message);
          }

          const createdAddress = result?.customerAddressCreate?.customerAddress;
          if (!createdAddress) {
            throw new Error('Customer address create failed.');
          }

          await applyDefaultAddress(createdAddress.id);

          return {
            error: null,
            createdAddress,
            defaultAddress,
          };
        } catch (error) {
          if (error instanceof Error) {
            return data(
              {error: {[addressId]: error.message}},
              {
                status: 400,
              },
            );
          }
          return data(
            {error: {[addressId]: error}},
            {
              status: 400,
            },
          );
        }
      }

      case 'PUT': {
        // handle address updates
        try {
          const result = await storefront.mutate(UPDATE_ADDRESS_MUTATION, {
            variables: {
              customerAccessToken,
              address,
              id: decodeURIComponent(addressId),
              language: storefront.i18n?.language,
            },
          });

          const userErrors = result?.customerAddressUpdate?.customerUserErrors;
          if (userErrors?.length) {
            throw new Error(userErrors[0].message);
          }

          if (!result?.customerAddressUpdate?.customerAddress) {
            throw new Error('Customer address update failed.');
          }

          await applyDefaultAddress(decodeURIComponent(addressId));

          return {
            error: null,
            updatedAddress: address,
            defaultAddress,
          };
        } catch (error) {
          if (error instanceof Error) {
            return data(
              {error: {[addressId]: error.message}},
              {
                status: 400,
              },
            );
          }
          return data(
            {error: {[addressId]: error}},
            {
              status: 400,
            },
          );
        }
      }

      case 'DELETE': {
        // handles address deletion
        try {
          const result = await storefront.mutate(DELETE_ADDRESS_MUTATION, {
            variables: {
              customerAccessToken,
              id: decodeURIComponent(addressId),
              language: storefront.i18n?.language,
            },
          });

          const userErrors = result?.customerAddressDelete?.customerUserErrors;
          if (userErrors?.length) {
            throw new Error(userErrors[0].message);
          }

          if (!result?.customerAddressDelete?.deletedCustomerAddressId) {
            throw new Error('Customer address delete failed.');
          }

          return {error: null, deletedAddress: addressId};
        } catch (error) {
          if (error instanceof Error) {
            return data(
              {error: {[addressId]: error.message}},
              {
                status: 400,
              },
            );
          }
          return data(
            {error: {[addressId]: error}},
            {
              status: 400,
            },
          );
        }
      }

      default: {
        return data(
          {error: {[addressId]: 'Method not allowed'}},
          {
            status: 405,
          },
        );
      }
    }
  } catch (error) {
    if (error instanceof Error) {
      return data(
        {error: error.message},
        {
          status: 400,
        },
      );
    }
    return data(
      {error},
      {
        status: 400,
      },
    );
  }
}

export default function Addresses() {
  const {customer} = useOutletContext();
  const {defaultAddress, addresses} = customer;

  return (
    <div className="account-addresses">
      <h2>Addresses</h2>
      <br />
      <div>
        <div>
          <legend>Create address</legend>
          <NewAddressForm key={addresses.nodes.length} />
        </div>
        <br />
        <hr />
        <br />
        {!addresses.nodes.length ? (
          <p>You have no addresses saved.</p>
        ) : (
          <ExistingAddresses
            addresses={addresses}
            defaultAddress={defaultAddress}
          />
        )}
      </div>
    </div>
  );
}

function NewAddressForm() {
  const newAddress = {
    address1: '',
    address2: '',
    city: '',
    company: '',
    country: '',
    firstName: '',
    id: 'new',
    lastName: '',
    phone: '',
    province: '',
    zip: '',
  };

  return (
    <AddressForm
      addressId={'NEW_ADDRESS_ID'}
      address={newAddress}
      defaultAddress={null}
    >
      {({stateForMethod}) => (
        <div>
          <button
            disabled={stateForMethod('POST') !== 'idle'}
            formMethod="POST"
            type="submit"
          >
            {stateForMethod('POST') !== 'idle' ? 'Creating' : 'Create'}
          </button>
        </div>
      )}
    </AddressForm>
  );
}

/**
 * @param {Pick<CustomerFragment, 'addresses' | 'defaultAddress'>}
 */
function ExistingAddresses({addresses, defaultAddress}) {
  return (
    <div>
      <legend>Existing addresses</legend>
      {addresses.nodes.map((address) => (
        <AddressForm
          key={address.id}
          addressId={address.id}
          address={address}
          defaultAddress={defaultAddress}
        >
          {({stateForMethod}) => (
            <div>
              <button
                disabled={stateForMethod('PUT') !== 'idle'}
                formMethod="PUT"
                type="submit"
              >
                {stateForMethod('PUT') !== 'idle' ? 'Saving' : 'Save'}
              </button>
              <button
                disabled={stateForMethod('DELETE') !== 'idle'}
                formMethod="DELETE"
                type="submit"
              >
                {stateForMethod('DELETE') !== 'idle' ? 'Deleting' : 'Delete'}
              </button>
            </div>
          )}
        </AddressForm>
      ))}
    </div>
  );
}

/**
 * @param {{
 *   addressId: AddressFragment['id'];
 *   address: CustomerAddressInput;
 *   defaultAddress: CustomerFragment['defaultAddress'];
 *   children: (props: {
 *     stateForMethod: (method: 'PUT' | 'POST' | 'DELETE') => Fetcher['state'];
 *   }) => React.ReactNode;
 * }}
 */
export function AddressForm({addressId, address, defaultAddress, children}) {
  const {state, formMethod} = useNavigation();
  /** @type {ActionReturnData} */
  const action = useActionData();
  const error = action?.error?.[addressId];
  const isDefaultAddress = defaultAddress?.id === addressId;
  return (
    <Form id={addressId}>
      <fieldset>
        <input type="hidden" name="addressId" defaultValue={addressId} />
        <label htmlFor="firstName">First name*</label>
        <input
          aria-label="First name"
          autoComplete="given-name"
          defaultValue={address?.firstName ?? ''}
          id="firstName"
          name="firstName"
          placeholder="First name"
          required
          type="text"
        />
        <label htmlFor="lastName">Last name*</label>
        <input
          aria-label="Last name"
          autoComplete="family-name"
          defaultValue={address?.lastName ?? ''}
          id="lastName"
          name="lastName"
          placeholder="Last name"
          required
          type="text"
        />
        <label htmlFor="company">Company</label>
        <input
          aria-label="Company"
          autoComplete="organization"
          defaultValue={address?.company ?? ''}
          id="company"
          name="company"
          placeholder="Company"
          type="text"
        />
        <label htmlFor="address1">Address line*</label>
        <input
          aria-label="Address line 1"
          autoComplete="address-line1"
          defaultValue={address?.address1 ?? ''}
          id="address1"
          name="address1"
          placeholder="Address line 1*"
          required
          type="text"
        />
        <label htmlFor="address2">Address line 2</label>
        <input
          aria-label="Address line 2"
          autoComplete="address-line2"
          defaultValue={address?.address2 ?? ''}
          id="address2"
          name="address2"
          placeholder="Address line 2"
          type="text"
        />
        <label htmlFor="city">City*</label>
        <input
          aria-label="City"
          autoComplete="address-level2"
          defaultValue={address?.city ?? ''}
          id="city"
          name="city"
          placeholder="City"
          required
          type="text"
        />
        <label htmlFor="zoneCode">State / Province*</label>
        <input
          aria-label="State/Province"
          autoComplete="address-level1"
          defaultValue={address?.province ?? ''}
          id="zoneCode"
          name="zoneCode"
          placeholder="State / Province"
          required
          type="text"
        />
        <label htmlFor="zip">Zip / Postal Code*</label>
        <input
          aria-label="Zip"
          autoComplete="postal-code"
          defaultValue={address?.zip ?? ''}
          id="zip"
          name="zip"
          placeholder="Zip / Postal Code"
          required
          type="text"
        />
        <label htmlFor="territoryCode">Country*</label>
        <input
          aria-label="Country"
          autoComplete="country-name"
          defaultValue={address?.country ?? ''}
          id="territoryCode"
          name="territoryCode"
          placeholder="Country (e.g. United States)"
          required
          type="text"
        />
        <label htmlFor="phoneNumber">Phone</label>
        <input
          aria-label="Phone Number"
          autoComplete="tel"
          defaultValue={address?.phone ?? ''}
          id="phoneNumber"
          name="phoneNumber"
          placeholder="+16135551111"
          pattern="^\+?[1-9]\d{3,14}$"
          type="tel"
        />
        <div>
          <input
            defaultChecked={isDefaultAddress}
            id="defaultAddress"
            name="defaultAddress"
            type="checkbox"
          />
          <label htmlFor="defaultAddress">Set as default address</label>
        </div>
        {error ? (
          <p>
            <mark>
              <small>{error}</small>
            </mark>
          </p>
        ) : (
          <br />
        )}
        {children({
          stateForMethod: (method) => (formMethod === method ? state : 'idle'),
        })}
      </fieldset>
    </Form>
  );
}

/**
 * @typedef {{
 *   addressId?: string | null;
 *   createdAddress?: AddressFragment;
 *   defaultAddress?: string | null;
 *   deletedAddress?: string | null;
 *   error: Record<AddressFragment['id'], string> | null;
 *   updatedAddress?: AddressFragment;
 * }} ActionResponse
 */

/** @typedef {import('@shopify/hydrogen/customer-account-api-types').CustomerAddressInput} CustomerAddressInput */
/** @typedef {import('customer-accountapi.generated').AddressFragment} AddressFragment */
/** @typedef {import('customer-accountapi.generated').CustomerFragment} CustomerFragment */
/** @template T @typedef {import('react-router').Fetcher<T>} Fetcher */
/** @typedef {import('./+types/account.addresses').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
