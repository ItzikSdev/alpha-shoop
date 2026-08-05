import {useState} from 'react';

const OFFERS = [
  {code: 'ALPHA10', label: '10% off with code', hint: 'Enter at checkout'},
  {code: null, label: '5% off orders over $25', hint: 'Automatically applied'},
];

export function PromoBanner({full = false}) {
  const [copiedCode, setCopiedCode] = useState(null);

  function copyCode(code) {
    navigator.clipboard?.writeText(code).then(() => {
      setCopiedCode(code);
      setTimeout(() => setCopiedCode((c) => (c === code ? null : c)), 1800);
    });
  }

  return (
    <div
      className={`${full ? 'flex w-full' : 'inline-flex'} flex-col items-start gap-2 rounded-md border border-accent-300 bg-accent-100 px-4 py-3`}
    >
      {OFFERS.map((offer) => (
        <div
          key={offer.label}
          className="flex items-center gap-2 text-[12.5px] font-semibold uppercase tracking-[.06em] text-accent-800"
        >
          <span>{offer.label}</span>
          {offer.code && (
            <button
              type="button"
              onClick={() => copyCode(offer.code)}
              className="rounded-sm border border-accent-400 bg-white px-2 py-0.5 font-mono text-accent-700 tracking-normal normal-case cursor-pointer transition-colors hover:bg-accent-100"
              title="Click to copy"
            >
              {copiedCode === offer.code ? 'Copied!' : offer.code}
            </button>
          )}
          <span className="hidden font-normal normal-case text-accent-700/70 sm:inline">
            ({offer.hint})
          </span>
        </div>
      ))}
    </div>
  );
}
