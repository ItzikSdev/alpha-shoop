import {config} from '~/lib/theme';

/**
 * Product-page FAQ (TKT-68b77b1e item 3) — real catalog/policy data only,
 * sourced from theme.config.json's legal block (single source of truth for
 * shipping/returns) and the live ALPHA10 code already applied at checkout
 * (see CartSummary.jsx). No invented policies, no fabricated timelines.
 */
export function ProductFAQ() {
  const {shipping, returns} = config.legal || {};
  const regions = shipping?.regions || [];

  const items = [
    {
      q: 'How long does shipping take?',
      a: (
        <>
          Orders are processed in {shipping?.processingTime || '1–3 business days'} and
          then shipped. Delivery time depends on your region:
          <ul className="mt-1.5 list-none space-y-0.5">
            {regions.map((r) => (
              <li key={r.region}>
                <strong className="font-semibold">{r.region}:</strong> {r.time}
              </li>
            ))}
          </ul>
        </>
      ),
    },
    {
      q: 'What is your return policy?',
      a: (
        <>
          Returns are accepted within {returns?.windowDays || 30} days of delivery.
          Items must be {returns?.condition || 'unused, in original packaging, with tags attached'}.{' '}
          <a href="/policies/refund-policy" className="underline">
            Full return policy
          </a>
          .
        </>
      ),
    },
    {
      q: 'Is there a discount code?',
      a: (
        <>
          Yes — use code <strong className="font-bold">ALPHA10</strong> at checkout for 10%
          off your order.
        </>
      ),
    },
    {
      q: 'How do I track my order?',
      a: "You'll receive a tracking link by email as soon as your order ships.",
    },
  ];

  return (
    <section className="px-4 md:px-6 pb-[100px] md:pb-8">
      <h2 className="ch4 mb-3 font-classical">Frequently asked questions</h2>
      <div className="divide-y divide-divider border-t border-b border-divider">
        {items.map((item) => (
          <details key={item.q} className="group py-3">
            <summary className="flex cursor-pointer list-none items-center justify-between text-cbody font-medium text-ink">
              {item.q}
              <span className="ml-3 text-accent-700 transition-transform group-open:rotate-45">+</span>
            </summary>
            <div className="mt-2 text-[13.5px] leading-relaxed text-ink/70">{item.a}</div>
          </details>
        ))}
      </div>
    </section>
  );
}
