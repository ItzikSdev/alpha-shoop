import {Link} from 'react-router';
import {Image, Money} from '@shopify/hydrogen';
import {useVariantUrl} from '~/lib/variants';

/**
 * A product card in the TIMEFOR BABY design (.tob-card, 3:4 image, hover zoom).
 * @param {{
 *   product:
 *     | CollectionItemFragment
 *     | ProductItemFragment
 *     | RecommendedProductFragment;
 *   loading?: 'eager' | 'lazy';
 * }}
 */
export function ProductItem({product, loading}) {
  const variantUrl = useVariantUrl(product.handle);
  const image = product.featuredImage;
  const available = product.availableForSale ?? true;
  return (
    <Link className="tob-card" key={product.id} prefetch="intent" to={variantUrl}>
      <div className="tob-imgwrap">
        {image && (
          <Image
            alt={image.altText || product.title}
            aspectRatio="3/4"
            data={image}
            loading={loading}
            sizes="(min-width: 820px) 300px, 45vw"
          />
        )}
      </div>
      <h3>{product.title}</h3>
      <div className="tob-price">
        <Money data={product.priceRange.minVariantPrice} />
        {!available && <span className="tob-soldout">Sold out</span>}
      </div>
    </Link>
  );
}

/** @typedef {import('storefrontapi.generated').ProductItemFragment} ProductItemFragment */
/** @typedef {import('storefrontapi.generated').CollectionItemFragment} CollectionItemFragment */
/** @typedef {import('storefrontapi.generated').RecommendedProductFragment} RecommendedProductFragment */
