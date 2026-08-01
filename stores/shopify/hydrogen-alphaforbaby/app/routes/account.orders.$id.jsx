import {redirect, useLoaderData} from 'react-router';
import {Money, Image} from '@shopify/hydrogen';
import {Typography, Chip} from '@material-tailwind/react';
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
    <div className="flex flex-col gap-6">
      <div>
        <Typography variant="h4" color="blue-gray">
          Order {order.name}
        </Typography>
        <Typography variant="small" color="gray">
          Placed on {new Date(order.processedAt).toDateString()}
        </Typography>
      </div>

      <div className="overflow-x-auto -mx-4 px-4">
        <table className="w-full text-left border-collapse min-w-[560px]">
          <thead>
            <tr className="border-b border-blue-gray-100">
              <th scope="col" className="py-3 pr-4 text-xs font-semibold text-blue-gray-500 uppercase tracking-wide">Product</th>
              <th scope="col" className="py-3 px-4 text-xs font-semibold text-blue-gray-500 uppercase tracking-wide">Price</th>
              <th scope="col" className="py-3 px-4 text-xs font-semibold text-blue-gray-500 uppercase tracking-wide">Quantity</th>
              <th scope="col" className="py-3 pl-4 text-xs font-semibold text-blue-gray-500 uppercase tracking-wide">Total</th>
            </tr>
          </thead>
          <tbody>
            {lineItems.map((lineItem, lineItemIndex) => (
              // eslint-disable-next-line react/no-array-index-key
              <OrderLineRow key={lineItemIndex} lineItem={lineItem} />
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-blue-gray-100">
              <th scope="row" colSpan={3} className="py-2 pr-4 text-left font-normal text-blue-gray-500">Subtotal</th>
              <td className="py-2 pl-4">
                <Money data={order.currentSubtotalPriceSet.shopMoney} />
              </td>
            </tr>
            <tr>
              <th scope="row" colSpan={3} className="py-2 pr-4 text-left font-normal text-blue-gray-500">Tax</th>
              <td className="py-2 pl-4">
                <Money data={order.currentTotalTaxSet.shopMoney} />
              </td>
            </tr>
            <tr>
              <th scope="row" colSpan={3} className="py-2 pr-4 text-left font-semibold text-blue-gray-900">Total</th>
              <td className="py-2 pl-4 font-semibold">
                <Money data={order.currentTotalPriceSet.shopMoney} />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="grid sm:grid-cols-2 gap-6 pt-2">
        <div>
          <Typography variant="h6" color="blue-gray" className="mb-2">
            Shipping Address
          </Typography>
          {order?.shippingAddress ? (
            <address className="not-italic text-sm text-blue-gray-600 flex flex-col">
              <span>{order.shippingAddress.name}</span>
              {order.shippingAddress.formatted?.length
                ? order.shippingAddress.formatted.map((line, i) => (
                    // eslint-disable-next-line react/no-array-index-key
                    <span key={i}>{line}</span>
                  ))
                : null}
            </address>
          ) : (
            <Typography variant="small" color="gray">No shipping address defined</Typography>
          )}
        </div>
        <div>
          <Typography variant="h6" color="blue-gray" className="mb-2">
            Status
          </Typography>
          <Chip value={fulfillmentStatus} size="sm" variant="ghost" className="w-fit" />
        </div>
      </div>

      <a
        target="_blank"
        href={order.statusPageUrl}
        rel="noreferrer"
        className="login-underline-link w-fit"
      >
        View Order Status →
      </a>
    </div>
  );
}

function OrderLineRow({lineItem}) {
  return (
    <tr className="border-b border-blue-gray-50">
      <td className="py-3 pr-4">
        <div className="flex items-center gap-3">
          {lineItem?.variant?.image && (
            <Image
              data={lineItem.variant.image}
              width={64}
              height={64}
              className="rounded-lg"
            />
          )}
          <div>
            <Typography variant="small" className="font-medium text-blue-gray-900">
              {lineItem.title}
            </Typography>
            {lineItem.variant?.title ? (
              <Typography variant="small" color="gray">
                {lineItem.variant.title}
              </Typography>
            ) : null}
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <Money data={lineItem.originalTotalSet.shopMoney} />
      </td>
      <td className="py-3 px-4">{lineItem.quantity}</td>
      <td className="py-3 pl-4">
        <Money data={lineItem.discountedTotalSet.shopMoney} />
      </td>
    </tr>
  );
}

/** @typedef {import('./+types/account.orders.$id').Route} Route */
/** @typedef {ReturnType<typeof useLoaderData<typeof loader>>} LoaderReturnData */
