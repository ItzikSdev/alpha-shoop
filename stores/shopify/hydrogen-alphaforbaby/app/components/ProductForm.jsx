import {Link, useNavigate} from 'react-router';
import {Lock, ChevronDown} from 'lucide-react';
import {AddToCartButton} from './AddToCartButton';
import {getDisplaySizeLabels} from '~/lib/sizeLabels';
import {config} from '~/lib/theme';

// Real "Classical" component classes (app.css) — .btn/.btn-primary/.btn-secondary
// are the design system's actual button component, not a Tailwind approximation.
const BTN_PRIMARY = 'btn btn-primary btn-block w-full min-h-[52px] text-[15px] tracking-[.08em]';
const BTN_SECONDARY = 'btn btn-secondary btn-block w-full min-h-[52px] text-[15px] tracking-[.08em]';

/**
 * @param {{
 *   productOptions: MappedProductOptions[];
 *   selectedVariant: ProductFragment['selectedOrFirstAvailableVariant'];
 * }}
 */
export function ProductForm({productOptions, selectedVariant}) {
  const navigate = useNavigate();
  // A product only ever has ONE real color axis. If it already has a genuine
  // "Color" option, a separate "Size" option is a real size (even if its values
  // aren't cm-formatted, e.g. "S"/"M"/"L") — never relabel it too, or the form
  // renders two "Color" sections.
  const hasRealColorOption = productOptions.some((o) => o.name.toLowerCase() === 'color');
  return (
    <div className="flex min-w-0 flex-col gap-1">
      {productOptions.map((option) => {
        // If there is only a single value in the option values, don't display the option
        if (option.optionValues.length === 1) return null;

        // Only Color gets CJ's per-variant photo as its button thumbnail. Size (and any
        // other option) is always a plain text button — a variant photo doesn't tell a
        // shopper anything about "3-6M" vs "6-12M", it just repeats the color image.
        //
        // CJ's variantKey isn't always "{Color}-{Size}" — some products only have a
        // color axis, and the pipeline falls back to naming that lone option "Size"
        // even though its values are color SKU codes (e.g. "WW942"), not cm sizes.
        // So a "Size"-named option whose values AREN'T cm-pattern sizes, AND the
        // product has no separate real "Color" option, is a mislabeled color axis —
        // treat it like one (image swatch instead of raw code).
        const isColorOption = option.name.toLowerCase() === 'color';
        const isSizeOption = option.name.toLowerCase() === 'size';
        // "Looks like a real size" must cover every size SHAPE this catalog
        // actually uses, not just cm — a bug found live (Duck Print Baby
        // Bodysuit, 2026-08-26): its real Size values are age labels
        // ("NEWBORN", "0 To 3M", "3 To 6M"), none of which are cm-formatted,
        // so the old cm-only check misclassified this genuine Size axis as a
        // mislabeled color axis and rendered age labels as "Color" swatches
        // — a customer thought they were picking a color but were picking a
        // size. Only values that DON'T match any known size shape (i.e. look
        // like a raw color SKU code, e.g. "WW942") should still be treated
        // as a mislabeled color axis.
        const isRealSizeLabel = (raw) =>
          /^\d+cm$/i.test(raw) ||                      // "52cm"
          /^newborn$/i.test(raw) ||                     // "NEWBORN"
          /^\d+\s*(to|-)\s*\d+\s*[myMY]$/i.test(raw) ||  // "0 To 3M", "3-6M"
          /^\d+\s*[myMY]$/i.test(raw) ||                 // "6M", "2Y"
          /^(xxs|xs|s|m|l|xl|xxl|xxxl)$/i.test(raw);     // letter sizes
        const sizeOptionIsActuallyColor =
          isSizeOption && !hasRealColorOption && !option.optionValues.some((v) => isRealSizeLabel(v.name));
        const sizeLabels = isSizeOption && !sizeOptionIsActuallyColor
          ? getDisplaySizeLabels(option.optionValues.map((v) => v.name))
          : null;
        const isColorLike = isColorOption || sizeOptionIsActuallyColor;
        // Real cm-based Size options render as a dropdown (age + cm per row)
        // instead of a button grid — Color (or a mislabeled color axis) keeps
        // the swatch buttons.
        const isDropdownSize = isSizeOption && !sizeOptionIsActuallyColor;

        if (isDropdownSize) {
          const selectedValue = option.optionValues.find((v) => v.selected) || option.optionValues[0];
          return (
            <div className="min-w-0 pt-4" key={option.name}>
              <h6 className="m-0 text-kicker uppercase tracking-[.08em] text-accent-700">{option.name}</h6>
              <div className="relative mt-2 w-full min-w-0">
                <select
                  value={selectedValue?.name}
                  style={{width: '100%', maxWidth: '100%', boxSizing: 'border-box'}}
                  className="block w-full appearance-none rounded border border-divider bg-transparent py-3 pl-[10px] pr-[38px] text-[14px] min-h-[50px] text-ink hover:border-ink/45 focus-visible:border-accent"
                  onChange={(e) => {
                    const value = option.optionValues.find((v) => v.name === e.target.value);
                    if (!value || value.selected) return;
                    if (value.isDifferentProduct) {
                      void navigate(`/products/${value.handle}?${value.variantUriQuery}`, {
                        preventScrollReset: true,
                      });
                    } else {
                      void navigate(`?${value.variantUriQuery}`, {
                        replace: true,
                        preventScrollReset: true,
                      });
                    }
                  }}
                >
                  {option.optionValues.map((value) => {
                    const displayName = sizeLabels?.get(value.name) || value.name;
                    const cmMatch = value.name.match(/^(\d+)cm$/i);
                    const isOutOfRange = !!cmMatch && parseInt(cmMatch[1], 10) > 104;
                    const label = cmMatch ? `${displayName} · ${value.name}` : displayName;
                    return (
                      <option
                        key={option.name + value.name}
                        value={value.name}
                        disabled={!value.exists || !value.available || isOutOfRange}
                      >
                        {label}
                        {isOutOfRange ? ' — unavailable' : !value.available ? ' — sold out' : ''}
                      </option>
                    );
                  })}
                </select>
                <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-classical-600" />
              </div>
            </div>
          );
        }

        return (
          <div className="pt-4" key={option.name}>
            <h6 className="m-0 text-kicker uppercase tracking-[.08em] text-accent-700">
              {sizeOptionIsActuallyColor ? 'Color' : option.name}
            </h6>
            <div className="mt-2 flex flex-wrap gap-2">
              {option.optionValues.map((value) => {
                const {
                  name,
                  handle,
                  variantUriQuery,
                  selected,
                  available,
                  exists,
                  isDifferentProduct,
                  swatch,
                  firstSelectableVariant,
                } = value;
                // CJ-style: use this option value's variant photo as its button
                // thumbnail (so colors show as pictures, not text) — Color, or a
                // "Size" option that's actually color codes in disguise.
                const variantImage = (isColorOption || sizeOptionIsActuallyColor)
                  ? firstSelectableVariant?.image?.url
                  : undefined;
                const displayName = sizeLabels ? sizeLabels.get(name) : name;

                // STANDING RULE (docs/STORE_MEMORY.md): this store is for kids up to
                // age 4 (~104cm / "3-4 Years") only. A genuine cm-based Size option
                // whose value is bigger than that is never purchasable here, no
                // matter what CJ/Shopify says is in stock.
                const cmMatch = isSizeOption && !sizeOptionIsActuallyColor ? name.match(/^(\d+)cm$/i) : null;
                const isSizeButtonOutOfRange = !!cmMatch && parseInt(cmMatch[1], 10) > 104;
                const canPick = available && !isSizeButtonOutOfRange;

                const shapeClass = isColorLike
                  ? 'h-[58px] w-[58px] overflow-hidden rounded p-[3px]'
                  : 'min-w-[60px] rounded px-[15px] py-[11px] text-center text-[14px]';

                if (isDifferentProduct && isSizeButtonOutOfRange) {
                  // Out-of-age-range combined-listing child — never link to it.
                  return (
                    <span
                      className={`${shapeClass} border border-divider opacity-30 cursor-not-allowed transition-colors`}
                      key={option.name + name}
                      title="Not available — outside this store's age range (up to 4 years)"
                    >
                      <ProductOptionSwatch swatch={swatch} name={displayName} image={variantImage} isColorLike={isColorLike} />
                    </span>
                  );
                } else if (isDifferentProduct) {
                  // SEO
                  // When the variant is a combined listing child product
                  // that leads to a different url, we need to render it
                  // as an anchor tag
                  return (
                    <Link
                      className={`${shapeClass} border transition-colors ${
                        selected
                          ? 'border-accent ring-2 ring-accent ring-offset-2 ring-offset-bg'
                          : 'border-divider hover:border-ink/45'
                      } ${available ? '' : 'opacity-30'}`}
                      key={option.name + name}
                      prefetch="intent"
                      preventScrollReset
                      replace
                      to={`/products/${handle}?${variantUriQuery}`}
                    >
                      <ProductOptionSwatch swatch={swatch} name={displayName} image={variantImage} isColorLike={isColorLike} />
                    </Link>
                  );
                } else {
                  // SEO
                  // When the variant is an update to the search param,
                  // render it as a button with javascript navigating to
                  // the variant so that SEO bots do not index these as
                  // duplicated links
                  return (
                    <button
                      type="button"
                      className={`${shapeClass} border transition-colors ${
                        selected
                          ? isColorLike
                            ? 'border-accent ring-2 ring-accent ring-offset-2 ring-offset-bg'
                            : 'border-accent text-accent'
                          : 'border-divider text-ink hover:border-ink/45'
                      } ${canPick ? '' : 'opacity-30'} ${isSizeButtonOutOfRange ? 'cursor-not-allowed' : ''}`}
                      key={option.name + name}
                      title={isSizeButtonOutOfRange ? "Not available — outside this store's age range (up to 4 years)" : undefined}
                      disabled={!exists || isSizeButtonOutOfRange}
                      onClick={() => {
                        if (!selected) {
                          void navigate(`?${variantUriQuery}`, {
                            replace: true,
                            preventScrollReset: true,
                          });
                        }
                      }}
                    >
                      <ProductOptionSwatch swatch={swatch} name={displayName} image={variantImage} isColorLike={isColorLike} />
                    </button>
                  );
                }
              })}
            </div>
          </div>
        );
      })}
      <AddToCartButton
        disabled={!selectedVariant || !selectedVariant.availableForSale}
        redirectTo="/cart"
        className={`${BTN_PRIMARY} mt-4`}
        lines={
          selectedVariant
            ? [
                {
                  merchandiseId: selectedVariant.id,
                  quantity: 1,
                  selectedVariant,
                },
              ]
            : []
        }
      >
        {selectedVariant?.availableForSale ? 'ADD TO CART' : 'SOLD OUT'}
      </AddToCartButton>

      {/* Both buttons add the selected variant and jump straight to Shopify
          checkout. PayPal isn't a separate bypass flow — there's no custom
          PayPal integration wired up (that needs a PayPal Business account,
          which this store doesn't have). Enable PayPal in Shopify admin →
          Settings → Payments and it appears automatically on that checkout
          screen; this button is just a shortcut labeled for shoppers who
          look for it specifically. */}
      {selectedVariant?.availableForSale && (
        <div className="mt-2 flex flex-col gap-2">
          <AddToCartButton
            disabled={!selectedVariant || !selectedVariant.availableForSale}
            redirectTo="checkout"
            className={BTN_SECONDARY}
            lines={[
              {
                merchandiseId: selectedVariant.id,
                quantity: 1,
                selectedVariant,
              },
            ]}
          >
            BUY IT NOW
          </AddToCartButton>
          <AddToCartButton
            disabled={!selectedVariant || !selectedVariant.availableForSale}
            redirectTo="checkout"
            className={BTN_SECONDARY}
            lines={[
              {
                merchandiseId: selectedVariant.id,
                quantity: 1,
                selectedVariant,
              },
            ]}
          >
            PayPal
          </AddToCartButton>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-[11px] text-ink/50">
            <Lock size={13} />
            {/* Real accepted-payment-method logos (same assets as the header
                marquee) — legitimate trust signal, not a fabricated security
                certification badge. */}
            {config.paymentIcons?.map((p) => (
              <img key={p.src} src={p.src} alt={p.alt} loading="lazy" width="28" height="18" className="rounded-sm border border-divider" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * @param {{
 *   swatch?: Maybe<ProductOptionValueSwatch> | undefined;
 *   name: string;
 * }}
 */
function ProductOptionSwatch({swatch, name, image, isColorLike}) {
  // Prefer a native Shopify swatch image; fall back to the option value's own
  // variant photo (CJ-style color thumbnails). Only text if neither exists.
  const swatchImage = swatch?.image?.previewImage?.url;
  const color = swatch?.color;
  const thumb = swatchImage || image;

  if (!thumb && !color) {
    return <span className="text-[13px]">{name}</span>;
  }

  return (
    <div
      aria-label={name}
      title={name}
      className={isColorLike ? 'h-full w-full overflow-hidden rounded-sm' : 'inline-block h-[18px] w-[18px] rounded-full align-middle'}
      style={{backgroundColor: color || 'transparent'}}
    >
      {!!thumb && <img src={thumb} alt={name} loading="lazy" className="h-full w-full object-cover" />}
    </div>
  );
}

/** @typedef {import('@shopify/hydrogen').MappedProductOptions} MappedProductOptions */
/** @typedef {import('@shopify/hydrogen/storefront-api-types').Maybe} Maybe */
/** @typedef {import('@shopify/hydrogen/storefront-api-types').ProductOptionValueSwatch} ProductOptionValueSwatch */
/** @typedef {import('storefrontapi.generated').ProductFragment} ProductFragment */
