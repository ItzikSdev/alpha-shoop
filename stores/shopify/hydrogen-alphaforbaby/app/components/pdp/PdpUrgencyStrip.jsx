/**
 * Urgency line + buyer avatar strip — §5 item 3 / 7.D #16.
 *
 * Sits between the gallery (and its dot pagination) and the product title.
 *
 * Honesty note (Rule 2): the reference store's line is "SELLING QUICK, LOW
 * STOCK". This product has ~40,000 units in stock, so a scarcity claim would be
 * fabricated urgency. The ticker therefore carries statements that are true for
 * this product; wire a real end-date or a real low-stock threshold in and the
 * line can say so.
 *
 * The buyer count comes from the real review total, never an invented "1000+".
 *
 * 2026-09-21, Itzik's call: the row of buyer avatar thumbnails that used to sit
 * directly under the first product image is GONE. It crowded the hero shot on
 * mobile, which is the first thing a shopper sees. The count itself stays —
 * it is the honest part of the signal and costs no vertical space.
 *
 * @param {{line?: string, buyerCount?: number}}
 */
export function PdpUrgencyStrip({line, buyerCount = 0}) {
  if (!line && !buyerCount) return null;
  return (
    <div className="px-4 pt-2 md:px-0" data-urgency-strip>
      {line && (
        <p className="m-0 inline-block whitespace-nowrap rounded border border-accent/40 bg-accent/5 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[.05em] text-accent-700">
          {line}
        </p>
      )}
      {buyerCount > 0 && (
        <div className="mt-1.5 flex items-center gap-2" data-buyer-count>
          <span className="whitespace-nowrap rounded-full bg-ink/5 px-2.5 py-1 text-[11.5px] font-semibold text-ink/75">
            Join {buyerCount} verified buyers
          </span>
        </div>
      )}
    </div>
  );
}
