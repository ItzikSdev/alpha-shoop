import {
  data,
  Form,
  useActionData,
  useNavigation,
  useOutletContext,
} from 'react-router';
import {Input, Button, Checkbox, Typography, Alert} from '@material-tailwind/react';
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
    <div className="flex flex-col gap-8">
      <Typography variant="h4" color="blue-gray">
        Addresses
      </Typography>
      <div className="flex flex-col gap-8">
        <div className="max-w-xl flex flex-col gap-4">
          <Typography variant="h6" color="blue-gray">
            Create address
          </Typography>
          <NewAddressForm key={addresses.length} />
        </div>
        {!addresses.length ? (
          <Typography color="gray">You have no addresses saved.</Typography>
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
        <Button disabled={stateForMethod('POST') !== 'idle'} formMethod="POST" type="submit" className="self-start">
          {stateForMethod('POST') !== 'idle' ? 'Creating…' : 'Create'}
        </Button>
      )}
    </AddressForm>
  );
}

function ExistingAddresses({addresses, defaultAddress}) {
  return (
    <div className="flex flex-col gap-6">
      <Typography variant="h6" color="blue-gray">
        Existing addresses
      </Typography>
      <div className="grid sm:grid-cols-2 gap-6">
        {addresses.map((address) => (
          <div key={address.id} className="border border-blue-gray-100 rounded-xl p-5">
            <AddressForm
              addressId={address.id}
              address={address}
              defaultAddress={defaultAddress}
            >
              {({stateForMethod}) => (
                <div className="flex gap-3">
                  <Button disabled={stateForMethod('PUT') !== 'idle'} formMethod="PUT" type="submit" size="sm">
                    {stateForMethod('PUT') !== 'idle' ? 'Saving…' : 'Save'}
                  </Button>
                  <Button
                    disabled={stateForMethod('DELETE') !== 'idle'}
                    formMethod="DELETE"
                    type="submit"
                    size="sm"
                    variant="outlined"
                    color="red"
                  >
                    {stateForMethod('DELETE') !== 'idle' ? 'Deleting…' : 'Delete'}
                  </Button>
                </div>
              )}
            </AddressForm>
          </div>
        ))}
      </div>
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
    <Form id={addressId} className="flex flex-col gap-4">
      <input type="hidden" name="addressId" defaultValue={addressId} />
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="w-full">
          <Input
            aria-label="First name"
            autoComplete="given-name"
            defaultValue={address?.firstName ?? ''}
            id="firstName"
            name="firstName"
            label="First name"
            required
            type="text"
            crossOrigin=""
          />
        </div>
        <div className="w-full">
          <Input
            aria-label="Last name"
            autoComplete="family-name"
            defaultValue={address?.lastName ?? ''}
            id="lastName"
            name="lastName"
            label="Last name"
            required
            type="text"
            crossOrigin=""
          />
        </div>
      </div>
      <Input
        aria-label="Company"
        autoComplete="organization"
        defaultValue={address?.company ?? ''}
        id="company"
        name="company"
        label="Company"
        type="text"
        crossOrigin=""
      />
      <Input
        aria-label="Address line 1"
        autoComplete="address-line1"
        defaultValue={address?.address1 ?? ''}
        id="address1"
        name="address1"
        label="Address line 1"
        required
        type="text"
        crossOrigin=""
      />
      <Input
        aria-label="Address line 2"
        autoComplete="address-line2"
        defaultValue={address?.address2 ?? ''}
        id="address2"
        name="address2"
        label="Address line 2"
        type="text"
        crossOrigin=""
      />
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="w-full">
          <Input
            aria-label="City"
            autoComplete="address-level2"
            defaultValue={address?.city ?? ''}
            id="city"
            name="city"
            label="City"
            required
            type="text"
            crossOrigin=""
          />
        </div>
        <div className="w-full">
          <Input
            aria-label="State/Province"
            autoComplete="address-level1"
            defaultValue={address?.province ?? ''}
            id="zoneCode"
            name="zoneCode"
            label="State / Province"
            required
            type="text"
            crossOrigin=""
          />
        </div>
      </div>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="w-full">
          <Input
            aria-label="Zip"
            autoComplete="postal-code"
            defaultValue={address?.zip ?? ''}
            id="zip"
            name="zip"
            label="Zip / Postal Code"
            required
            type="text"
            crossOrigin=""
          />
        </div>
        <div className="w-full">
          <Input
            aria-label="Country"
            autoComplete="country-name"
            defaultValue={address?.country ?? ''}
            id="territoryCode"
            name="territoryCode"
            label="Country"
            required
            type="text"
            crossOrigin=""
          />
        </div>
      </div>
      <Input
        aria-label="Phone Number"
        autoComplete="tel"
        defaultValue={address?.phone ?? ''}
        id="phoneNumber"
        name="phoneNumber"
        label="Phone"
        pattern="^\+?[1-9]\d{3,14}$"
        type="tel"
        crossOrigin=""
      />
      <Checkbox
        defaultChecked={isDefaultAddress}
        id="defaultAddress"
        name="defaultAddress"
        label="Set as default address"
        crossOrigin=""
      />
      {error ? (
        <Alert color="red" variant="ghost">
          {error}
        </Alert>
      ) : null}
      {children({
        stateForMethod: (method) => (formMethod === method ? state : 'idle'),
      })}
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
