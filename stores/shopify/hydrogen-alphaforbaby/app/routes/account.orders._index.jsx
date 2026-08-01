import {
  Link,
  useLoaderData,
  useNavigation,
  useSearchParams,
} from 'react-router';
import {useRef} from 'react';
import {Money, getPaginationVariables} from '@shopify/hydrogen';
import {Card, CardBody, Input, Button, Typography, Chip} from '@material-tailwind/react';
import {
  buildOrderSearchQuery,
  parseOrderFilters,
} from '~/lib/orderFilters';
import {PaginatedResourceSection} from '~/components/PaginatedResourceSection';
import {requireCustomer, getCustomerOrders} from '~/lib/customer';

const ORDER_FILTER_FIELDS = {NAME: 'name', CONFIRMATION_NUMBER: 'confirmation_number'};

/**
 * @type {Route.MetaFunction}
 */
export const meta = () => {
  return [{title: 'Orders'}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, context}) {
  const customer = await requireCustomer(context, request);
  const paginationVariables = getPaginationVariables(request, {pageBy: 20});

  const url = new URL(request.url);
  const filters = parseOrderFilters(url.searchParams);
  const searchQuery = buildOrderSearchQuery(filters);

  const orders = await getCustomerOrders(context.env, customer.id, {
    searchQuery,
    paginationVariables,
  });

  return {orders: orders ?? {nodes: [], pageInfo: {}}, filters};
}

export default function Orders() {
  /** @type {LoaderReturnData} */
  const {orders, filters} = useLoaderData();

  return (
    <div className="flex flex-col gap-6">
      <OrderSearchForm currentFilters={filters} />
      <OrdersTable orders={orders} filters={filters} />
    </div>
  );
}

function OrdersTable({orders, filters}) {
  const hasFilters = !!(filters.name || filters.confirmationNumber);

  return (
    <div aria-live="polite">
      {orders?.nodes?.length ? (
        <PaginatedResourceSection connection={orders}>
          {({node: order}) => <OrderItem key={order.id} order={order} />}
        </PaginatedResourceSection>
      ) : (
        <EmptyOrders hasFilters={hasFilters} />
      )}
    </div>
  );
}

function EmptyOrders({hasFilters = false}) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      {hasFilters ? (
        <>
          <Typography color="gray">No orders found matching your search.</Typography>
          <Link to="/account/orders" className="login-underline-link">
            Clear filters →
          </Link>
        </>
      ) : (
        <>
          <Typography color="gray">You haven&apos;t placed any orders yet.</Typography>
          <Link to="/collections" className="login-underline-link">
            Start Shopping →
          </Link>
        </>
      )}
    </div>
  );
}

function OrderSearchForm({currentFilters}) {
  const [, setSearchParams] = useSearchParams();
  const navigation = useNavigation();
  const isSearching =
    navigation.state !== 'idle' &&
    navigation.location?.pathname?.includes('orders');
  const formRef = useRef(null);

  const handleSubmit = (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const params = new URLSearchParams();

    const name = formData.get(ORDER_FILTER_FIELDS.NAME)?.toString().trim();
    const confirmationNumber = formData
      .get(ORDER_FILTER_FIELDS.CONFIRMATION_NUMBER)
      ?.toString()
      .trim();

    if (name) params.set(ORDER_FILTER_FIELDS.NAME, name);
    if (confirmationNumber)
      params.set(ORDER_FILTER_FIELDS.CONFIRMATION_NUMBER, confirmationNumber);

    setSearchParams(params);
  };

  const hasFilters = currentFilters.name || currentFilters.confirmationNumber;

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      aria-label="Search orders"
      className="flex flex-col gap-4 max-w-md"
    >
      <Typography variant="h6" color="blue-gray">
        Filter Orders
      </Typography>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="w-full">
          <Input
            type="search"
            name={ORDER_FILTER_FIELDS.NAME}
            label="Order #"
            aria-label="Order number"
            defaultValue={currentFilters.name || ''}
            crossOrigin=""
          />
        </div>
        <div className="w-full">
          <Input
            type="search"
            name={ORDER_FILTER_FIELDS.CONFIRMATION_NUMBER}
            label="Confirmation #"
            aria-label="Confirmation number"
            defaultValue={currentFilters.confirmationNumber || ''}
            crossOrigin=""
          />
        </div>
      </div>

      <div className="flex gap-3">
        <Button type="submit" size="sm" disabled={isSearching}>
          {isSearching ? 'Searching…' : 'Search'}
        </Button>
        {hasFilters && (
          <Button
            type="button"
            size="sm"
            variant="outlined"
            disabled={isSearching}
            onClick={() => {
              setSearchParams(new URLSearchParams());
              formRef.current?.reset();
            }}
          >
            Clear
          </Button>
        )}
      </div>
    </form>
  );
}

function formatStatus(value) {
  if (!value) return null;
  return value
    .toLowerCase()
    .split('_')
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(' ');
}

function OrderItem({order}) {
  return (
    <>
      <fieldset>
        <Link to={`/account/orders/${btoa(order.id)}`}>
          <strong>{order.name}</strong>
        </Link>
        <p>{new Date(order.processedAt).toDateString()}</p>
        <p>{formatStatus(order.displayFinancialStatus)}</p>
        {order.displayFulfillmentStatus && <p>{formatStatus(order.displayFulfillmentStatus)}</p>}
        <Money data={order.currentTotalPriceSet.shopMoney} />
        <Link to={`/account/orders/${btoa(order.id)}`}>View Order →</Link>
      </fieldset>
      <br />
    </>
  );
}

/** @typedef {import('./+types/account.orders._index').Route} Route */
/** @typedef {import('~/lib/orderFilters').OrderFilterParams} OrderFilterParams */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
