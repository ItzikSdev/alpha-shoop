import {redirect, useLoaderData} from 'react-router';
import {Money, Image} from '@shopify/hydrogen';
import {CUSTOMER_ORDER_QUERY} from '~/graphql/customer/CustomerOrderQuery';
import {requireCustomer, getCustomerAccessToken} from '~/lib/customer';

/**
 * @type {Route.MetaFunction}
 */
export const meta = ({data}) => {
  return [{title: `Order ${data?.order?.name}`}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, params, context}) {
  await requireCustomer(context, request);
  if (!params.id) {
    return redirect('/account/orders');
  }

  const orderId = atob(params.id);
  const customerAccessToken = getCustomerAccessToken(context.session);
  const data = await context.storefront.query(CUSTOMER_ORDER_QUERY, {
    variables: {
      customerAccessToken,
      language: context.storefront.i18n?.language,
    },
  });

  // The classic Storefront API has no "order by id" query — orders are only
  // reachable through the authenticated customer's own order list, which is
  // what we fetched above. Find the match here.
  const order = data?.customer?.orders?.nodes?.find((o) => o.id === orderId);

  if (!order) {
    throw new Error('Order not found');
  }

  // Extract line items directly from nodes array
  const lineItems = order.lineItems.nodes;

  const fulfillmentStatus = order.fulfillmentStatus ?? 'N/A';

  return {
    order,
    lineItems,
    fulfillmentStatus,
  };
}

export default function OrderRoute() {
  /** @type {LoaderReturnData} */
  const {order, lineItems, fulfillmentStatus} = useLoaderData();
  return (
    <div className="account-order">
      <h2>Order {order.name}</h2>
      <p>Placed on {new Date(order.processedAt).toDateString()}</p>
      <br />
      <div>
        <table>
          <thead>
            <tr>
              <th scope="col">Product</th>
              <th scope="col">Price</th>
              <th scope="col">Quantity</th>
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {lineItems.map((lineItem, lineItemIndex) => (
              // eslint-disable-next-line react/no-array-index-key
              <OrderLineRow key={lineItemIndex} lineItem={lineItem} />
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={3}>
                <p>Subtotal</p>
              </th>
              <th scope="row">
                <p>Subtotal</p>
              </th>
              <td>
                <Money data={order.currentSubtotalPrice} />
              </td>
            </tr>
            <tr>
              <th scope="row" colSpan={3}>
                Tax
              </th>
              <th scope="row">
                <p>Tax</p>
              </th>
              <td>
                <Money data={order.currentTotalTax} />
              </td>
            </tr>
            <tr>
              <th scope="row" colSpan={3}>
                Total
              </th>
              <th scope="row">
                <p>Total</p>
              </th>
              <td>
                <Money data={order.currentTotalPrice} />
              </td>
            </tr>
          </tfoot>
        </table>
        <div>
          <h3>Shipping Address</h3>
          {order?.shippingAddress ? (
            <address>
              <p>{order.shippingAddress.name}</p>
              {order.shippingAddress.formatted ? (
                <p>{order.shippingAddress.formatted}</p>
              ) : (
                ''
              )}
              {order.shippingAddress.formattedArea ? (
                <p>{order.shippingAddress.formattedArea}</p>
              ) : (
                ''
              )}
            </address>
          ) : (
            <p>No shipping address defined</p>
          )}
          <h3>Status</h3>
          <div>
            <p>{fulfillmentStatus}</p>
          </div>
        </div>
      </div>
      <br />
      <p>
        <a target="_blank" href={order.statusUrl} rel="noreferrer">
          View Order Status →
        </a>
      </p>
    </div>
  );
}

/**
 * @param {{lineItem: OrderLineItemFullFragment}}
 */
function OrderLineRow({lineItem}) {
  return (
    <tr>
      <td>
        <div>
          {lineItem?.variant?.image && (
            <div>
              <Image data={lineItem.variant.image} width={96} height={96} />
            </div>
          )}
          <div>
            <p>{lineItem.title}</p>
            <small>{lineItem.variant?.title}</small>
          </div>
        </div>
      </td>
      <td>
        <Money data={lineItem.originalTotalPrice} />
      </td>
      <td>{lineItem.quantity}</td>
      <td>
        <Money data={lineItem.discountedTotalPrice} />
      </td>
    </tr>
  );
}

/** @typedef {import('./+types/account.orders.$id').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
