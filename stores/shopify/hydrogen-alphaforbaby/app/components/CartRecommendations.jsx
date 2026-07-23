import {Link} from 'react-router';
import {Money} from '@shopify/hydrogen';
import {Card, CardHeader, CardBody, CardFooter, Typography} from '@material-tailwind/react';
import {AddToCartButton} from './AddToCartButton';

/**
 * "Complete the look" upsell row on the cart page — Shopify's own
 * COMPLEMENTARY (falls back to RELATED) product-recommendation intent, based
 * on what's already in the cart. Renders nothing if there are no
 * recommendations (empty cart, or Shopify has none for this product).
 *
 * Uses Material Tailwind's Card so every card is uniform regardless of each
 * product's native photo aspect ratio — the image sits in a fixed-height
 * CardHeader with object-cover, not a natural-size <img>.
 * @param {{products: Array<any>}}
 */
export function CartRecommendations({products}) {
  if (!products?.length) return null;

  return (
    <div className="cart-recommendations">
      <Typography variant="h5" className="cart-recommendations-heading">
        You might also like
      </Typography>
      <div className="cart-recommendations-grid">
        {products.slice(0, 4).map((product) => {
          const variant = product.selectedOrFirstAvailableVariant;
          return (
            <Card key={product.id} shadow={false} className="h-full flex flex-col border border-gray-200">
              <CardHeader floated={false} shadow={false} className="m-0 h-36 rounded-b-none shrink-0">
                <Link to={`/products/${product.handle}`} prefetch="intent">
                  {product.featuredImage && (
                    <img
                      src={product.featuredImage.url}
                      alt={product.featuredImage.altText || product.title}
                      className="h-36 w-full object-cover"
                      loading="lazy"
                    />
                  )}
                </Link>
              </CardHeader>
              <CardBody className="flex-1 p-3">
                <Link to={`/products/${product.handle}`} prefetch="intent">
                  <Typography variant="small" className="font-semibold text-gray-900 line-clamp-2 min-h-[2.5em]">
                    {product.title}
                  </Typography>
                </Link>
                <Typography variant="small" className="mt-1 font-bold text-gray-900">
                  <Money data={product.priceRange.minVariantPrice} />
                </Typography>
              </CardBody>
              {variant?.availableForSale && (
                <CardFooter className="pt-0 p-3 shrink-0">
                  {/* AddToCartButton renders its own <button> — can't nest MT's <Button>
                      (also a <button>) inside it, so apply the site's black-filled CTA
                      classes directly to it instead, matching Add to Cart/Buy it now. */}
                  <AddToCartButton
                    className="w-full cursor-pointer rounded-lg border border-gray-900 bg-gray-900 py-2 text-sm font-bold text-white transition-colors hover:bg-black"
                    lines={[{merchandiseId: variant.id, quantity: 1}]}
                  >
                    Add
                  </AddToCartButton>
                </CardFooter>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
