import {Truck, RotateCcw, Tag} from 'lucide-react';

/**
 * Slim site-wide announcement bar, above the header. Only verified-true
 * facts (TKT-68b77b1e item 1) — no countdown, no fake stock/urgency:
 * free shipping (config.brand.copyright), 30-day returns
 * (theme.config.json legal.returns.windowDays), and the live ALPHA10
 * discount code (already used at checkout — see CartSummary.jsx).
 */
export function TrustBanner() {
  return (
    <div className="flex w-full flex-wrap items-center justify-center gap-x-5 gap-y-1 bg-accent-900 px-4 py-2 text-[11px] font-medium uppercase tracking-[.06em] text-white">
      <span className="flex items-center gap-1.5">
        <Truck size={13} aria-hidden="true" />
        Free shipping
      </span>
      <span className="flex items-center gap-1.5">
        <RotateCcw size={13} aria-hidden="true" />
        30-day returns
      </span>
      <span className="flex items-center gap-1.5">
        <Tag size={13} aria-hidden="true" />
        10% off with code <strong className="font-bold tracking-normal normal-case">ALPHA10</strong>
      </span>
    </div>
  );
}
