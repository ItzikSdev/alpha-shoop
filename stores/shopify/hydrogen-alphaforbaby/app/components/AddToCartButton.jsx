import {CartForm} from '@shopify/hydrogen';
import {Loader2} from 'lucide-react';

/**
 * @param {{
 *   analytics?: unknown;
 *   children: React.ReactNode;
 *   disabled?: boolean;
 *   lines: Array<OptimisticCartLineInput>;
 *   onClick?: () => void;
 * }}
 */
export function AddToCartButton({
  analytics,
  children,
  className,
  disabled,
  lines,
  onClick,
  redirectTo,
}) {
  return (
    <CartForm route="/cart" inputs={{lines}} action={CartForm.ACTIONS.LinesAdd}>
      {(fetcher) => (
        <>
          <input
            name="analytics"
            type="hidden"
            value={JSON.stringify(analytics)}
          />
          {/* When set, the cart action 303-redirects here after adding — sends the
              shopper to the full /cart page (like a Liquid storefront). */}
          {redirectTo && (
            <input name="redirectTo" type="hidden" value={redirectTo} />
          )}
          <button
            type="submit"
            className={className}
            onClick={onClick}
            disabled={disabled || fetcher.state !== 'idle'}
            aria-busy={fetcher.state !== 'idle'}
          >
            {fetcher.state !== 'idle' ? (
              <>
                <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                {/* redirectTo is what's actually navigating away (to /cart or
                    /checkout) — everything else is just the cart mutation,
                    which resolves almost instantly. */}
                <span>{redirectTo ? 'Redirecting…' : 'Adding…'}</span>
              </>
            ) : (
              children
            )}
          </button>
        </>
      )}
    </CartForm>
  );
}

/** @typedef {import('react-router').FetcherWithComponents} FetcherWithComponents */
/** @typedef {import('@shopify/hydrogen').OptimisticCartLineInput} OptimisticCartLineInput */
