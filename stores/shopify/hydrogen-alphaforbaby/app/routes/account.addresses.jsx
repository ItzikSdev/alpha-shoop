import {
  data,
  Form,
  useActionData,
  useNavigation,
  useOutletContext,
} from 'react-router';
import {
  requireCustomer,
  createCustomerAddress,
  updateCustomerAddress,
  deleteCustomerAddress,
} from '~/lib/customer';

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
  const customer = await requireCustomer(context, request);

  try {
    const form = await request.formData();

    const addressId = form.has('addressId')
      ? String(form.get('addressId'))
      : null;
    if (!addressId) {
      throw new Error('You must provide an address id.');
    }

    const defaultAddress = form.has('defaultAddress')
      ? String(form.get('defaultAddress')) === 'on'
      : false;

    // Admin API's MailingAddressInput uses `country`/`province`/`phone`
    // (free-text country/province name), same shape the form already uses.
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

    switch (request.method) {
      case 'POST': {
        try {
          const createdAddress = await createCustomerAddress(
            context.env,
            customer.id,
            address,
            defaultAddress,
          );
          if (!createdAddress) {
            throw new Error('Customer address create failed.');
          }
          return {error: null, createdAddress, defaultAddress};
        } catch (error) {
          return data(
            {error: {[addressId]: error instanceof Error ? error.message : String(error)}},
            {status: 400},
          );
        }
      }

      case 'PUT': {
        try {
          const decodedId = decodeURIComponent(addressId);
          const updatedAddress = await updateCustomerAddress(
            context.env,
            customer.id,
            decodedId,
            address,
            defaultAddress,
          );
          if (!updatedAddress) {
            throw new Error('Customer address update failed.');
          }
          return {error: null, updatedAddress, defaultAddress};
        } catch (error) {
          return data(
            {error: {[addressId]: error instanceof Error ? error.message : String(error)}},
            {status: 400},
          );
        }
      }

      case 'DELETE': {
        try {
          const decodedId = decodeURIComponent(addressId);
          const deletedId = await deleteCustomerAddress(context.env, customer.id, decodedId);
          if (!deletedId) {
            throw new Error('Customer address delete failed.');
          }
          return {error: null, deletedAddress: addressId};
        } catch (error) {
          return data(
            {error: {[addressId]: error instanceof Error ? error.message : String(error)}},
            {status: 400},
          );
        }
      }

      default: {
        return data({error: {[addressId]: 'Method not allowed'}}, {status: 405});
      }
    }
  } catch (error) {
    return data(
      {error: error instanceof Error ? error.message : String(error)},
      {status: 400},
    );
  }
}

export default function Addresses() {
  const {customer} = useOutletContext();
  const defaultAddress = customer?.defaultAddress ?? null;
  const addresses = customer?.addresses ?? [];

  return (
    <div className="account-addresses">
      <h2>Addresses</h2>
      <br />
      <div>
        <div>
          <legend>Create address</legend>
          <NewAddressForm key={addresses.length} />
        </div>
        <br />
        <hr />
        <br />
        {!addresses.length ? (
          <p>You have no addresses saved.</p>
        ) : (
          <ExistingAddresses addresses={addresses} defaultAddress={defaultAddress} />
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
    <AddressForm addressId={'NEW_ADDRESS_ID'} address={newAddress} defaultAddress={null}>
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

function ExistingAddresses({addresses, defaultAddress}) {
  return (
    <div>
      <legend>Existing addresses</legend>
      {addresses.map((address) => (
        <AddressForm
          key={address.id}
          addressId={address.id}
          address={address}
          defaultAddress={defaultAddress}
        >
          {({stateForMethod}) => (
            <div>
              <button disabled={stateForMethod('PUT') !== 'idle'} formMethod="PUT" type="submit">
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
 *   createdAddress?: object;
 *   defaultAddress?: boolean | null;
 *   deletedAddress?: string | null;
 *   error: Record<string, string> | string | null;
 *   updatedAddress?: object;
 * }} ActionResponse
 */

/** @typedef {import('./+types/account.addresses').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
/** @typedef {ReturnType<typeof useActionData<typeof action>>} ActionReturnData */
