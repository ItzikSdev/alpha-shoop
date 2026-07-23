import {Link, useNavigate} from 'react-router';
import {AddToCartButton} from './AddToCartButton';
import {SizeGuide} from './SizeGuide';
import {getDisplaySizeLabels} from '~/lib/sizeLabels';

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
    <div className="product-form">
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
        const isCmSize = (raw) => /^\d+cm$/i.test(raw);
        const sizeOptionIsActuallyColor =
          isSizeOption && !hasRealColorOption && !option.optionValues.some((v) => isCmSize(v.name));
        const sizeLabels = isSizeOption && !sizeOptionIsActuallyColor
          ? getDisplaySizeLabels(option.optionValues.map((v) => v.name))
          : null;

        return (
          <div className="product-options" key={option.name}>
            <h5>
              {sizeOptionIsActuallyColor ? 'Color' : option.name}
              {isSizeOption && !sizeOptionIsActuallyColor && <SizeGuide />}
            </h5>
            <div className="product-options-grid">
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

                if (isDifferentProduct && isSizeButtonOutOfRange) {
                  // Out-of-age-range combined-listing child — never link to it.
                  return (
                    <span
                      className="product-options-item"
                      key={option.name + name}
                      title="Not available — outside this store's age range (up to 4 years)"
                      style={{border: '1px solid transparent', opacity: 0.3, cursor: 'not-allowed'}}
                    >
                      <ProductOptionSwatch swatch={swatch} name={displayName} image={variantImage} />
                    </span>
                  );
                } else if (isDifferentProduct) {
                  // SEO
                  // When the variant is a combined listing child product
                  // that leads to a different url, we need to render it
                  // as an anchor tag
                  return (
                    <Link
                      className="product-options-item"
                      key={option.name + name}
                      prefetch="intent"
                      preventScrollReset
                      replace
                      to={`/products/${handle}?${variantUriQuery}`}
                      style={{
                        border: selected
                          ? '1px solid black'
                          : '1px solid transparent',
                        opacity: available ? 1 : 0.3,
                      }}
                    >
                      <ProductOptionSwatch swatch={swatch} name={displayName} image={variantImage} />
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
                      className={`product-options-item${exists && !selected ? ' link' : ''}`}
                      key={option.name + name}
                      title={isSizeButtonOutOfRange ? "Not available — outside this store's age range (up to 4 years)" : undefined}
                      style={{
                        border: selected
                          ? '1px solid black'
                          : '1px solid transparent',
                        opacity: canPick ? 1 : 0.3,
                        cursor: isSizeButtonOutOfRange ? 'not-allowed' : undefined,
                      }}
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
                      <ProductOptionSwatch swatch={swatch} name={displayName} image={variantImage} />
                    </button>
                  );
                }
              })}
            </div>
            <br />
          </div>
        );
      })}
      <AddToCartButton
        disabled={!selectedVariant || !selectedVariant.availableForSale}
        redirectTo="/cart"
        className="tob-atc-btn"
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
        {selectedVariant?.availableForSale ? 'Add to cart' : 'Sold out'}
      </AddToCartButton>

      {/* Express / accelerated checkout — adds the selected variant and jumps
          straight to Shopify checkout, where PayPal + dynamic checkout buttons
          appear once enabled in admin (Settings → Payments). */}
      {selectedVariant?.availableForSale && (
        <div className="tob-buynow">
          <AddToCartButton
            disabled={!selectedVariant || !selectedVariant.availableForSale}
            redirectTo="checkout"
            className="tob-buynow-btn"
            lines={[
              {
                merchandiseId: selectedVariant.id,
                quantity: 1,
                selectedVariant,
              },
            ]}
          >
            Buy it now
          </AddToCartButton>
          <p className="tob-buynow-note">Express checkout · secure payment</p>
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
function ProductOptionSwatch({swatch, name, image}) {
  // Prefer a native Shopify swatch image; fall back to the option value's own
  // variant photo (CJ-style color thumbnails). Only text if neither exists.
  const swatchImage = swatch?.image?.previewImage?.url;
  const color = swatch?.color;
  const thumb = swatchImage || image;

  if (!thumb && !color) {
    return <span className="tob-swatch-text">{name}</span>;
  }

  return (
    <div
      aria-label={name}
      title={name}
      className={`product-option-label-swatch${thumb ? ' has-image' : ''}`}
      style={{
        backgroundColor: color || 'transparent',
      }}
    >
      {!!thumb && <img src={thumb} alt={name} loading="lazy" />}
    </div>
  );
}

/** @typedef {import('@shopify/hydrogen').MappedProductOptions} MappedProductOptions */
/** @typedef {import('@shopify/hydrogen/storefront-api-types').Maybe} Maybe */
/** @typedef {import('@shopify/hydrogen/storefront-api-types').ProductOptionValueSwatch} ProductOptionValueSwatch */
/** @typedef {import('storefrontapi.generated').ProductFragment} ProductFragment */
