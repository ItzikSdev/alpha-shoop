import {useNavigate} from 'react-router';

/**
 * Variant selector as real native `<select>` elements (§5 item 3, v1.30 —
 * confirmed on littlesnugg's live DOM, which uses actual `<select>`s).
 *
 * Deliberately native, not a styled listbox: a `<div>` that looks like a
 * dropdown fails the DOM check, loses the OS picker on mobile, and loses
 * keyboard/AT behaviour for free. Also free of garment sizing logic — this
 * catalog's options are colours, styles and set sizes.
 *
 * @param {{productOptions: Array<object>, idPrefix?: string}}
 */
export function PdpVariants({productOptions = [], idPrefix = 'opt'}) {
  const navigate = useNavigate();
  const selectable = productOptions.filter((o) => o.optionValues?.length > 1);
  if (!selectable.length) return null;

  return (
    <div className="flex flex-col gap-3">
      {selectable.map((option) => {
        const current = option.optionValues.find((v) => v.selected);
        const id = `${idPrefix}-${option.name.toLowerCase().replace(/\s+/g, '-')}`;
        return (
          <div key={option.name}>
            <label
              htmlFor={id}
              className="mb-1 block text-kicker uppercase tracking-[.08em] text-accent-700"
            >
              {option.name}
            </label>
            <select
              id={id}
              name={option.name}
              value={current?.name ?? ''}
              onChange={(e) => {
                const picked = option.optionValues.find((v) => v.name === e.target.value);
                if (!picked) return;
                // A value belonging to another product is a real navigation;
                // values within this product only swap the URL's option params.
                if (picked.isDifferentProduct) {
                  navigate(`/products/${picked.handle}?${picked.variantUriQuery}`);
                } else {
                  navigate(`?${picked.variantUriQuery}`, {replace: true, preventScrollReset: true});
                }
              }}
              className="min-h-[44px] w-full rounded-md border border-divider bg-white px-3 text-[14px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {option.optionValues.map((v) => (
                <option key={v.name} value={v.name} disabled={!v.exists}>
                  {v.name}
                  {v.exists && !v.available ? ' — sold out' : ''}
                </option>
              ))}
            </select>
          </div>
        );
      })}
    </div>
  );
}
