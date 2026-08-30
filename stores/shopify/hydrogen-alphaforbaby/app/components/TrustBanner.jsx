import {Suspense} from 'react';
import {Await} from 'react-router';
import {Truck, RotateCcw, Tag} from 'lucide-react';

/**
 * Slim site-wide announcement bar, above the header. Only verified-true
 * facts (TKT-68b77b1e item 1) — no countdown, no fake stock/urgency:
 * free shipping (config.brand.copyright) and 30-day returns
 * (theme.config.json legal.returns.windowDays) for everyone. The ALPHA10
 * code is sign-in-gated (see SignInPromo.jsx) — it must NOT be
 * publicly visible here, so it's only added once `isLoggedIn` resolves
 * true, same as the header's AccountLinkResolved and the checkout
 * `?discount=` logic in CartSummary.jsx.
 *
 * `isLoggedIn` is a deferred Promise<boolean> from the root loader, so
 * it's resolved via Await/Suspense rather than read directly — a raw
 * Promise is always truthy, which would show the code to every guest.
 */
export function TrustBanner({isLoggedIn}) {
  return (
    <Suspense fallback={<TrustBannerInner showCode={false} />}>
      <Await resolve={isLoggedIn}>
        {(loggedIn) => <TrustBannerInner showCode={!!loggedIn} />}
      </Await>
    </Suspense>
  );
}

function TrustBannerInner({showCode}) {
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
      {showCode && (
        <span className="flex items-center gap-1.5">
          <Tag size={13} aria-hidden="true" />
          10% off with code <strong className="font-bold tracking-normal normal-case">ALPHA10</strong>
        </span>
      )}
    </div>
  );
}
