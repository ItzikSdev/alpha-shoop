import {useState} from 'react';
import {Money} from '@shopify/hydrogen';
import {Check} from 'lucide-react';
import {AddToCartButton} from '~/components/AddToCartButton';

/**
 * Same-SKU quantity-tier block — the `single_hero_product` shape from §5 item 3,
 * applied here per Itzik's direct call after reviewing littlesnugg.store.
 *
 * Replaces the previous cross-sell "complete the set" bundle entirely.
 *
 * Each tier mirrors a real Shopify automatic discount scoped to THIS product
 * (qty>=2 → 10%, qty>=3 → 35%), both non-combining, verified against a real
 * Storefront cart — never a percentage checkout won't honor (Rule 1).
 *
 * No add-on checkboxes: littlesnugg shows "Priority Delivery" / "Shipping
 * Protection", but this store has no real priority-shipping rate and no
 * shipping-protection product, and a checkbox that charges for nothing is worse
 * than no checkbox. Add them when the real mechanism exists.
 *
 * @param {{tiers: Array<{qty:number,percentage:number,badge?:string}>,
 *          variant: object, inStock: boolean}}
 */
export function PdpQuantityTiers({
  tiers = [], variant, inStock, variants = [], benefits = {}, optionName = 'Option',
}) {
  // Real per-unit selection: each unit keeps its own variant id, and the cart
  // receives one line per distinct variant. A picker that didn't actually
  // change what ships would be decoration, same problem as a fake add-on.
  const [units, setUnits] = useState({});
  const unitVariant = (q, i) => units[`${q}-${i}`] || variant?.id;
  const unit = Number(variant?.price?.amount || 0);
  const currency = variant?.price?.currencyCode || 'USD';
  const [qty, setQty] = useState(() => {
    const top = [...tiers].sort((a, b) => b.qty - a.qty)[0];
    return top ? top.qty : 1;
  });

  if (!variant) return null;

  // Name the picker after the product's real option ("size", "color") rather
  // than a generic id, so the control is semantically what it actually selects.
  const optionSlug = String(optionName).toLowerCase().replace(/[^a-z0-9]+/g, '-');

  // No configured quantity tiers is the normal state for a product that hasn't
  // had its pdp_content written yet — it must NOT mean "no buy box". Gating the
  // price, the variant picker and Add to Cart behind the tier config shipped
  // the crib and Glow Whale as pages a shopper physically could not buy from,
  // which reads as finished and is worse than an obviously unbuilt page
  // (7.D #29). Fall back to a plain single-purchase box for any product.
  if (!tiers.length) {
    return (
      <section className="pt-2" data-quantity-tiers data-simple-buybox>
        <div className="flex items-baseline gap-2">
          <span className="tnum text-[22px] font-semibold">
            <Money as="span" data={variant.price} />
          </span>
          {variant.compareAtPrice && (
            <span className="tnum text-[15px] text-ink/45 line-through">
              <Money as="span" data={variant.compareAtPrice} />
            </span>
          )}
        </div>

        {variants.length > 1 && (
          <div className="mt-3">
            <label className="mb-1 block text-[11px] uppercase tracking-[.08em] text-ink/50"
              htmlFor={optionSlug}>
              {optionName}
            </label>
            <select
              id={optionSlug}
              name={optionSlug}
              value={unitVariant(1, 0)}
              onChange={(e) => setUnits((p) => ({...p, '1-0': e.target.value}))}
              className="min-h-[44px] w-full rounded-md border border-divider bg-white px-2 text-[14px]"
            >
              {variants.map((v) => (
                <option key={v.id} value={v.id} disabled={!v.availableForSale}>
                  {v.title}
                  {v.availableForSale ? '' : ' — sold out'}
                </option>
              ))}
            </select>
          </div>
        )}

        <AddToCartButton
          disabled={!inStock}
          redirectTo="/cart"
          className="btn btn-primary mt-3 min-h-[52px] w-full tracking-[.08em]"
          lines={[{merchandiseId: unitVariant(1, 0), quantity: 1}]}
        >
          {inStock ? 'ADD TO CART' : 'SOLD OUT'}
        </AddToCartButton>
      </section>
    );
  }

  const tierFor = (q) =>
    [...tiers].sort((a, b) => b.qty - a.qty).find((t) => q >= t.qty) || null;

  return (
    <section className="pt-2" data-quantity-tiers>
      <h2 className="m-0 text-ch2 font-normal">Buy more, save more</h2>

      <ul className="mt-3 list-none p-0">
        {[1, 2].map((q) => {
          const t = tierFor(q);
          const gross = unit * q;
          const pay = t?.amountOff != null ? gross - t.amountOff : gross * (1 - (t?.percentage || 0));
          const on = qty === q;
          const isBest = false;
          const isPopular = t && t.qty === 2;
          return (
            <li key={q} className="relative">
              <button
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setQty(q)}
                className={`mb-2 flex w-full cursor-pointer items-center gap-3 rounded-lg border-2 p-3 text-left transition hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                  on ? 'border-accent bg-accent/5' : 'border-divider bg-white'
                } ${isBest ? 'shadow-sm' : ''}`}
              >
                <span
                  className={`flex h-6 w-6 flex-none items-center justify-center rounded-full border-2 ${
                    on ? 'border-accent' : 'border-ink/30'
                  }`}
                >
                  {on && <span className="h-3 w-3 rounded-full bg-accent" />}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] font-semibold">
                    Buy {q}
                    {isPopular && (
                      <span className="ml-2 rounded bg-ink/80 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                        Most popular
                      </span>
                    )}
                    {isBest && (
                      <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                        Best value
                      </span>
                    )}
                  </span>
                  <span className="mt-0.5 block text-[12.5px] text-ink/60">
                    {t
                      ? `You save ${Math.floor(((gross - pay) / gross) * 100)}%`
                      : 'Full price'}
                  </span>
                  {benefits[q] && (
                    <span className="mt-1 block text-[12px] leading-snug text-ink/55">{benefits[q]}</span>
                  )}
                </span>

                <span className="flex-none text-right">
                  <span className="tnum block text-[15px] font-semibold">
                    <Money as="span" data={{amount: pay.toFixed(2), currencyCode: currency}} />
                  </span>
                  {t && (
                    <span className="tnum block text-[12px] text-ink/45 line-through">
                      <Money as="span" data={{amount: gross.toFixed(2), currencyCode: currency}} />
                    </span>
                  )}
                </span>
              </button>

              {on && q > 1 && variants.length > 1 && (
                <div className="mb-3 -mt-1 rounded-b-lg border-2 border-t-0 border-accent bg-accent/5 px-3 pb-3 pt-1">
                  <span className="mb-1 block text-[11px] uppercase tracking-[.08em] text-ink/50">
                    Choose each one
                  </span>
                  {Array.from({length: q}, (_, unit) => (
                    <div key={unit} className="mb-2 flex items-center gap-2 last:mb-0">
                      <span className="w-6 flex-none text-[12px] text-ink/50">#{unit + 1}</span>
                      {(() => {
                        const sel = variants.find((v) => v.id === unitVariant(q, unit));
                        return sel?.image?.url ? (
                          <img
                            src={sel.image.url}
                            alt={sel.title}
                            data-unit-preview
                            className="h-10 w-10 flex-none rounded border border-divider object-cover"
                          />
                        ) : (
                          <span className="h-10 w-10 flex-none rounded border border-divider bg-ink/5" />
                        );
                      })()}
                      <label className="sr-only" htmlFor={`tier${q}-u${unit}-color`}>
                        {optionName} for item {unit + 1}
                      </label>
                      <select
                        id={`tier${q}-u${unit}-color`}
                        name={`tier${q}-u${unit}-color`}
                        value={unitVariant(q, unit)}
                        onChange={(e) => setUnits((p) => ({...p, [`${q}-${unit}`]: e.target.value}))}
                        className="min-h-[40px] w-full min-w-0 flex-1 rounded-md border border-divider bg-white px-2 text-[13px]"
                      >
                        {variants.map((v) => (
                          <option key={v.id} value={v.id} disabled={!v.availableForSale}>
                            {v.title}
                            {v.availableForSale ? '' : ' — sold out'}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <AddToCartButton
        disabled={!inStock}
        redirectTo="/cart"
        className="btn btn-primary mt-2 min-h-[52px] w-full tracking-[.08em]"
        lines={
          variant
            ? Object.values(
                Array.from({length: qty}, (_, i) => unitVariant(qty, i)).reduce((acc, id) => {
                  acc[id] = acc[id] || {merchandiseId: id, quantity: 0};
                  acc[id].quantity += 1;
                  return acc;
                }, {}),
              )
            : []
        }
      >
        {inStock ? `ADD ${qty} TO CART` : 'SOLD OUT'}
      </AddToCartButton>
    </section>
  );
}
