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
 * Avatars are real buyer-submitted photos, and the count comes from the real
 * review total, never an invented "1000+".
 *
 * @param {{line?: string, avatars?: string[], buyerCount?: number}}
 */
export function PdpUrgencyStrip({line, avatars = [], buyerCount = 0}) {
  if (!line && !avatars.length) return null;
  return (
    <div className="px-4 pt-2 md:px-0" data-urgency-strip>
      {line && (
        <p className="m-0 inline-block whitespace-nowrap rounded border border-accent/40 bg-accent/5 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[.05em] text-accent-700">
          {line}
        </p>
      )}
      {avatars.length > 0 && (
        <div className="mt-1.5 flex items-center gap-2" data-avatar-strip>
          <span className="flex -space-x-2">
            {avatars.slice(0, 4).map((src, i) => (
              <span key={src} className="tob-avatar" style={{zIndex: 10 - i}}>
                <img
                  src={src}
                  alt=""
                  loading="lazy"
                  className="h-7 w-7 rounded-full border-2 border-white object-cover"
                />
              </span>
            ))}
          </span>
          {buyerCount > 0 && (
            <span className="whitespace-nowrap rounded-full bg-ink/5 px-2.5 py-1 text-[11.5px] font-semibold text-ink/75">
              Join {buyerCount} verified buyers
            </span>
          )}
        </div>
      )}
    </div>
  );
}
