import {redirect, useLoaderData} from 'react-router';
import {Money, Image} from '@shopify/hydrogen';
import {requireCustomer, getOrderById} from '~/lib/customer';

/**
 * @type {Route.MetaFunction}
 */
export const meta = ({data}) => {
  return [{title: `Order ${data?.order?.name ?? ''}`}];
};

/**
 * @param {Route.LoaderArgs}
 */
export async function loader({request, params, context}) {
  const customer = await requireCustomer(context, request);
  if (!params.id) {
    return redirect('/account/orders');
  }

  const orderId = atob(params.id);
  // getOrderById fetches by Admin GID directly (Admin API has a top-level
  // `order(id:)` query, unlike the classic Storefront API which only ever
  // exposed orders through the authenticated customer's own order list) and
  // internally verifies order.customer.id === customer.id, so one signed-in
  // customer can never view another's order by editing this URL.
  const order = await getOrderById(context.env, orderId, customer.id);

  if (!order) {
    throw new Response('Order not found', {status: 404});
  }

  return {
    order,
    lineItems: order.lineItems.nodes,
    fulfillmentStatus: order.displayFulfillmentStatus ?? 'N/A',
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
              <td>
                <Money data={order.currentSubtotalPriceSet.shopMoney} />
              </td>
            </tr>
            <tr>
              <th scope="row" colSpan={3}>
                Tax
              </th>
              <td>
                <Money data={order.currentTotalTaxSet.shopMoney} />
              </td>
            </tr>
            <tr>
              <th scope="row" colSpan={3}>
                Total
              </th>
              <td>
                <Money data={order.currentTotalPriceSet.shopMoney} />
              </td>
            </tr>
          </tfoot>
        </table>
        <div>
          <h3>Shipping Address</h3>
          {order?.shippingAddress ? (
            <address>
              <p>{order.shippingAddress.name}</p>
              {order.shippingAddress.formatted?.length ? (
                order.shippingAddress.formatted.map((line, i) => (
                  // eslint-disable-next-line react/no-array-index-key
                  <p key={i}>{line}</p>
                ))
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
        <a target="_blank" href={order.statusPageUrl} rel="noreferrer">
          View Order Status →
        </a>
      </p>
    </div>
  );
}

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
        <Money data={lineItem.originalTotalSet.shopMoney} />
      </td>
      <td>{lineItem.quantity}</td>
      <td>
        <Money data={lineItem.discountedTotalSet.shopMoney} />
      </td>
    </tr>
  );
}

/** @typedef {import('./+types/account.orders.$id').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
