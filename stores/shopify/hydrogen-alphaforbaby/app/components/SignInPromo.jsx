import {Suspense, useEffect, useState} from 'react';
import {Await} from 'react-router';

const DISMISS_KEY = 'afb_signin_promo_dismissed';
const SHOW_DELAY_MS = 4000;

/**
 * Sign-in incentive popup — replaces the old publicly-visible ALPHA10 banner.
 * The discount code itself is never shown here; it's revealed only after the
 * shopper actually signs in (see Header's account link + AccountRevealCode).
 * Guests never see the code, only the offer to sign in for it.
 *
 * `isLoggedIn` is a deferred Promise<boolean> from the root loader (same as
 * Header's), so it must be resolved via Await/Suspense, not read directly —
 * a raw Promise is always truthy, which would have hidden the popup for
 * every visitor including guests.
 */
export function SignInPromo({isLoggedIn}) {
  return (
    <Suspense fallback={null}>
      <Await resolve={isLoggedIn}>
        {(loggedIn) => <SignInPromoInner isLoggedIn={!!loggedIn} />}
      </Await>
    </Suspense>
  );
}

function SignInPromoInner({isLoggedIn}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isLoggedIn) return; // already signed in — nothing to promo
    try {
      if (localStorage.getItem(DISMISS_KEY)) return;
    } catch {
      /* localStorage unavailable — just skip persistence, still show once */
    }
    const t = setTimeout(() => setVisible(true), SHOW_DELAY_MS);
    return () => clearTimeout(t);
  }, [isLoggedIn]);

  if (!visible || isLoggedIn) return null;

  const dismiss = () => {
    setVisible(false);
    try {
      localStorage.setItem(DISMISS_KEY, '1');
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      role="dialog"
      aria-label="Sign in for 10% off"
      style={{
        position: 'fixed', bottom: 20, right: 20, zIndex: 60, maxWidth: 320,
        background: '#fff', border: '1px solid #e5e0da', borderRadius: 8,
        boxShadow: '0 8px 24px rgba(0,0,0,.12)', padding: '18px 20px',
        fontFamily: '-apple-system,Helvetica,Arial,sans-serif',
      }}
    >
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        style={{position: 'absolute', top: 8, right: 10, border: 'none', background: 'none', fontSize: 16, cursor: 'pointer', color: '#888'}}
      >
        ×
      </button>
      <p style={{margin: '0 0 10px', fontSize: 14, lineHeight: 1.4, color: '#2b2b2b'}}>
        Sign in or create an account to get <strong>10% off</strong> your order.
      </p>
      <a
        href="/account/login"
        style={{display: 'inline-block', padding: '10px 18px', background: '#2b2b2b', color: '#fff', textDecoration: 'none', borderRadius: 4, fontSize: 13, letterSpacing: '.03em'}}
      >
        Sign in
      </a>
    </div>
  );
}
