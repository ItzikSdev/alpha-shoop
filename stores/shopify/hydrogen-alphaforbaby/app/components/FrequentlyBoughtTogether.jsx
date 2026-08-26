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
    <div className="card mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="m-0 text-ch3 font-normal">Build the set</h3>
        <span className="tag tag-accent tnum">{lines.length} items</span>
      </div>
      <div className="flex flex-col">
        <div className="flex w-full items-center gap-3 border-b border-divider py-2">
          <span className="flex h-[18px] w-[18px] flex-none items-center justify-center rounded-sm border border-accent text-accent">
            ✓
          </span>
          <Link
            to={mainProduct.handle ? `/products/${mainProduct.handle}` : '#'}
            prefetch="intent"
            className="plate plate-sm block h-[46px] w-[46px] flex-none overflow-hidden rounded-sm"
          >
            {mainProduct.image && (
              <img src={mainProduct.image.url} alt={mainProduct.image.altText || mainProduct.title} className="h-full w-full object-cover" />
            )}
          </Link>
          <Link
            to={mainProduct.handle ? `/products/${mainProduct.handle}` : '#'}
            prefetch="intent"
            className="flex-1 text-[13px] leading-snug text-ink"
          >
            This item: {mainProduct.title}
          </Link>
          <span className="tnum text-[13px]">
            <Money data={mainProduct.variant.price} />
          </span>
        </div>
        {items.map((p, i) => (
          <div
            key={p.id}
            className="flex w-full items-center gap-3 border-b border-divider py-2 last:border-b-0"
          >
            {/* Toggle stays its own control (was the whole row before — that
                meant clicking the title/image also toggled it off, with no
                way to actually visit the product). */}
            <button
              type="button"
              onClick={() => toggle(i)}
              aria-label={checked.has(i) ? `Remove ${p.title} from the set` : `Add ${p.title} to the set`}
              className={`flex h-[18px] w-[18px] flex-none items-center justify-center rounded-sm border text-accent ${
                checked.has(i) ? 'border-accent' : 'border-divider'
              }`}
            >
              {checked.has(i) ? '✓' : ''}
            </button>
            <Link
              to={p.handle ? `/products/${p.handle}` : '#'}
              prefetch="intent"
              className="plate plate-sm block h-[46px] w-[46px] flex-none overflow-hidden rounded-sm"
            >
              {p.featuredImage && (
                <img src={p.featuredImage.url} alt={p.featuredImage.altText || p.title} className="h-full w-full object-cover" />
              )}
            </Link>
            <Link
              to={p.handle ? `/products/${p.handle}` : '#'}
              prefetch="intent"
              className="flex-1 text-[13px] leading-snug text-ink"
            >
              {p.title}
            </Link>
            <span className="tnum text-[13px]">
              <Money data={p.selectedOrFirstAvailableVariant.price} />
            </span>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[.1em] text-accent">Total</div>
          <div className="tnum text-[24px] leading-tight">
            <Money data={{amount: String(total), currencyCode: currency}} />
          </div>
        </div>
        <AddToCartButton
          className="btn btn-primary min-h-[44px] px-4 tracking-[.08em]"
          lines={lines}
          redirectTo="/cart"
        >
          ADD {lines.length} TO CART
        </AddToCartButton>
      </div>
    </div>
  );
}
