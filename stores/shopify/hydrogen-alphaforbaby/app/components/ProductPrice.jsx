import {Money} from '@shopify/hydrogen';

/**
 * @param {{
 *   price?: MoneyV2;
 *   compareAtPrice?: MoneyV2 | null;
 * }}
 */
export function ProductPrice({price, compareAtPrice}) {
  const saving =
    price && compareAtPrice ? Number(compareAtPrice.amount) - Number(price.amount) : 0;

  return (
    <div aria-label="Price" role="group" className="tnum mt-3 flex items-baseline gap-2 flex-wrap">
      {compareAtPrice ? (
        <>
          {price ? <span className="text-price"><Money data={price} /></span> : null}
          <s className="text-[15px] text-ink/55">
            <Money data={compareAtPrice} />
          </s>
          {saving > 0 && (
            <span className="text-[13px] text-accent-700">
              You save <Money data={{amount: String(saving), currencyCode: compareAtPrice.currencyCode}} />
            </span>
          )}
        </>
      ) : price ? (
        <span className="text-price">
          <Money data={price} />
        </span>
      ) : (
        <span>&nbsp;</span>
      )}
    </div>
  );
}

/** Discount percent (rounded), or 0 if there's no compare-at price. */
export function discountPercent(price, compareAtPrice) {
  if (!price || !compareAtPrice) return 0;
  const p = Number(price.amount);
  const c = Number(compareAtPrice.amount);
  if (!(c > p)) return 0;
  return Math.round(((c - p) / c) * 100);
}

/** @typedef {import('@shopify/hydrogen/storefront-api-types').MoneyV2} MoneyV2 */
