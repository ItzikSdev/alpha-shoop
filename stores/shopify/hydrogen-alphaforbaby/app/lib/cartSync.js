import {getSessionCustomerId, saveCustomerCartId} from './customer';

// Only the line-item essentials needed to re-add saved items onto another
// cart — deliberately NOT the full CART_QUERY_FRAGMENT (app/lib/fragments.js),
// which is bound to the current session's OWN cart id via context.cart. This
// reads an arbitrary (saved) cart id directly via the Storefront API.
const CART_LINES_FOR_MERGE_QUERY = `#graphql
  query CartLinesForMerge($cartId: ID!, $country: CountryCode, $language: LanguageCode)
    @inContext(country: $country, language: $language) {
    cart(id: $cartId) {
      id
      lines(first: 250) {
        nodes {
          quantity
          merchandise {
            ... on ProductVariant {
              id
            }
          }
        }
      }
    }
  }
`;

/**
 * Combines multiple Headers objects (e.g. a cart-id cookie + an unrelated
 * auth cookie) into one, preserving multiple `Set-Cookie` entries rather
 * than clobbering one with the other — a plain object literal can't hold two
 * `Set-Cookie` keys, but `Headers.append` can.
 * @param {...(Headers | undefined | null)} headersList
 */
export function mergeHeaders(...headersList) {
  const merged = new Headers();
  for (const headers of headersList) {
    if (!headers) continue;
    for (const [key, value] of headers.entries()) {
      merged.append(key, value);
    }
  }
  return merged;
}

/**
 * Reconciles the CURRENT browser's cart with a customer's saved (canonical)
 * cart from another device, so the same account always sees the same cart —
 * "add on phone, see it on computer" — not just right after logging in, but
 * on every /cart page load too (see cart.jsx's loader). This matters because
 * a login-only sync misses the common case where BOTH devices already have
 * an active session: nothing re-triggers a sync until something calls this.
 *
 * Deliberately does NOT rely on `cart.setCartId()` alone to make the merged
 * cart visible in the SAME response — Hydrogen's cart handler resolves
 * `cart.get()` against the cart id captured at request start; changing the
 * cookie via `setCartId` only takes effect on the browser's NEXT request.
 * Instead this always folds the saved cart's lines onto the current cart via
 * `cart.addLines()` (a no-op add when there's nothing new) and returns that
 * call's own fresh result to render immediately, whether the current cart
 * started empty (adopts the saved items) or already had guest items (merges
 * instead of discarding either side).
 *
 * Best-effort throughout: any failure here just means cross-device cart sync
 * silently doesn't happen for this request — never a broken cart/login.
 * @param {{context: {cart: object, storefront: object, env: object}, customer: {id: string, savedCartId?: string | null}}} params
 * @returns {Promise<{headers: Headers, cart: object | null}>}
 */
export async function reconcileCustomerCart({context, customer}) {
  const savedCartId = customer?.savedCartId;
  if (!savedCartId) return {headers: new Headers(), cart: null};

  const {cart} = context;

  try {
    const current = await cart.get();
    if (current?.id === savedCartId) {
      return {headers: new Headers(), cart: current};
    }

    const {cart: savedCart} = await context.storefront.query(CART_LINES_FOR_MERGE_QUERY, {
      variables: {cartId: savedCartId},
    });
    const linesToAdd = (savedCart?.lines?.nodes ?? [])
      .map((line) => ({merchandiseId: line.merchandise?.id, quantity: line.quantity}))
      .filter((line) => line.merchandiseId);

    if (!linesToAdd.length) {
      // Saved cart is empty/expired — nothing to bring over, but the
      // current cart (if any) should still become the customer's canonical
      // one so future devices sync to it instead of the stale saved id.
      if (current?.id) await saveCustomerCartId(context.env, customer.id, current.id);
      return {headers: new Headers(), cart: current ?? null};
    }

    const result = await cart.addLines(linesToAdd);
    const mergedId = result?.cart?.id;
    if (!mergedId) return {headers: new Headers(), cart: current ?? null};

    // Deliberately re-fetch via cart.get() instead of using result.cart
    // directly: Hydrogen mutation responses use a smaller, differently-
    // shaped default fragment (lines.edges[].node) than our custom query
    // fragment (lines.nodes[]) used everywhere else in this app — using the
    // mutation result as-is silently rendered line items with no title/
    // image/product data (totalQuantity was still right, since that's a
    // plain scalar present in both shapes, which is what made this subtle).
    const refetched = await cart.get();

    await saveCustomerCartId(context.env, customer.id, mergedId);
    return {headers: cart.setCartId(mergedId), cart: refetched ?? current ?? null};
  } catch (error) {
    console.error('[reconcileCustomerCart] failed', error);
    return {headers: new Headers(), cart: null};
  }
}

/**
 * Best-effort: after any cart mutation, remembers which cart belongs to the
 * logged-in customer (if any) so reconcileCustomerCart can restore/merge it
 * on their next device. No-ops silently when nobody's logged in.
 * @param {{session: object, env: object}} context
 * @param {string} [cartId]
 */
export async function persistCartForLoggedInCustomer(context, cartId) {
  if (!cartId) return;
  const customerId = getSessionCustomerId(context.session);
  if (!customerId) return;
  await saveCustomerCartId(context.env, customerId, cartId);
}
