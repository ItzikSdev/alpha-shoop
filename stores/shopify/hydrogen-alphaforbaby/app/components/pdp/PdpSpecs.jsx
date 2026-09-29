/** Parse the product's `custom.specs` JSON metafield into [{label, value}].
 * Never throws — a missing/malformed value just means no spec table. */
export function parseSpecs(metafieldValue) {
  if (!metafieldValue) return [];
  try {
    const parsed = JSON.parse(metafieldValue);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s) => s && s.label && s.value);
  } catch {
    return [];
  }
}

/**
 * Per-product specification table, populated from real supplier data for THIS
 * product (see custom.specs). Nothing here is templated or inferred: every row
 * is a value stated by the supplier for this exact item.
 * @param {{specs: Array<{label: string, value: string}>}}
 */
export function PdpSpecs({specs = []}) {
  if (!specs.length) return null;
  return (
    <section className="pt-6">
      <h2 className="m-0 text-ch2 font-normal">Product details</h2>
      <dl className="mt-3 grid grid-cols-1 gap-x-8 border-t border-divider sm:grid-cols-2">
        {specs.map(({label, value}) => (
          <div key={label} className="flex gap-3 border-b border-divider py-2.5">
            <dt className="w-[42%] flex-none text-[13px] font-semibold text-ink/60">{label}</dt>
            <dd className="m-0 text-[13.5px] text-ink/90">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
