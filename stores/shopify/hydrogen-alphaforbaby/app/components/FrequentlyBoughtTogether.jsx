import {useState} from 'react';
import {Link} from 'react-router';
import {Money} from '@shopify/hydrogen';
import {AddToCartButton} from './AddToCartButton';

/**
 * Amazon-style "Frequently bought together" bundle: current product (always
 * included) + up to 2 recommended items, each toggleable via checkbox, with a
 * running total and a single "Add N to Cart" button for whatever's checked.
 * Renders nothing if there are no recommendations to bundle.
 * @param {{mainProduct: {title: string, image: any, variant: any}, extras: Array<any>}}
 */
export function FrequentlyBoughtTogether({mainProduct, extras}) {
  const items = (extras || []).filter((p) => p.selectedOrFirstAvailableVariant?.availableForSale);
  const [checked, setChecked] = useState(() => new Set(items.map((_, i) => i)));

  if (!items.length || !mainProduct.variant) return null;

  const toggle = (i) => {
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  const selectedExtras = items.filter((_, i) => checked.has(i));
  const total =
    Number(mainProduct.variant.price?.amount || 0) +
    selectedExtras.reduce((sum, p) => sum + Number(p.selectedOrFirstAvailableVariant.price.amount), 0);
  const currency = mainProduct.variant.price?.currencyCode || 'USD';
  const lines = [
    {merchandiseId: mainProduct.variant.id, quantity: 1},
    ...selectedExtras.map((p) => ({merchandiseId: p.selectedOrFirstAvailableVariant.id, quantity: 1})),
  ];

  return (
    <div className="fbt">
      <h4 className="fbt-heading">Frequently bought together</h4>
      <div className="fbt-row">
        <div className="fbt-item">
          <Link to={mainProduct.handle ? `/products/${mainProduct.handle}` : '#'} prefetch="intent">
            {mainProduct.image && <img src={mainProduct.image.url} alt={mainProduct.image.altText || mainProduct.title} />}
            <p className="fbt-item-label">This item: {mainProduct.title}</p>
          </Link>
          <Money data={mainProduct.variant.price} />
        </div>
        {items.map((p, i) => (
          <div className="fbt-item" key={p.id}>
            <span className="fbt-plus">+</span>
            <label className="fbt-checkbox">
              <input type="checkbox" checked={checked.has(i)} onChange={() => toggle(i)} />
              {p.featuredImage && <img src={p.featuredImage.url} alt={p.featuredImage.altText || p.title} />}
            </label>
            <Link to={`/products/${p.handle}`} prefetch="intent">
              <p className="fbt-item-label">{p.title}</p>
            </Link>
            <Money data={p.selectedOrFirstAvailableVariant.price} />
          </div>
        ))}
      </div>
      <div className="fbt-summary">
        <p className="fbt-total">
          Total: <Money data={{amount: String(total), currencyCode: currency}} />
        </p>
        <AddToCartButton className="fbt-add-btn" lines={lines} redirectTo="/cart">
          Add {lines.length} to Cart
        </AddToCartButton>
      </div>
    </div>
  );
}
