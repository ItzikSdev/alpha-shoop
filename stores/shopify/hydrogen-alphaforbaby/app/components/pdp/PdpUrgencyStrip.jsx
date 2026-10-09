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
// A scarcity or velocity claim needs proof this store doesn't have: ~40,000
// units in stock and no sales yet. The metafield text "SELLING QUICK, LOW
// STOCK" shipped anyway, so the guard lives in code (Level 01 rule 10).
const UNPROVABLE = /low stock|almost gone|only \d+ left|selling (fast|quick)|sold out soon|limited stock/i;

// True urgency instead (Itzik, 2026-09-25): what the store can actually stand
// behind. Dispatch time is the shipping policy's own "processed within 1–2
// business days"; the holiday cutoff comes from theme.config.json
// (`holidayCutoff`), chosen so the policy's slowest case (2 + 14 business
// days) still arrives before the holiday. After the cutoff date it simply
// disappears — it is never moved forward to keep the pressure on.
// A holiday order-by date is true the day it's set, but showing "Order by
// Nov 30 for Christmas" to a visitor landing in September doesn't read as
// urgency -- it reads as a banner nobody updated, and it was one of only
// two things visible above the fold to real Facebook-ad visitors who bounce
// immediately without scrolling (Itzik, 2026-09-29, via Clarity heatmaps).
// So the cutoff line only surfaces once it's genuinely close; the rest of
// the year the strip just carries the honest dispatch-time line.
const HOLIDAY_WINDOW_DAYS = 45;

function trueUrgency(cutoff) {
  const parts = ['Ships in 1–2 business days'];
  if (cutoff?.date && cutoff?.label) {
    const end = new Date(`${cutoff.date}T23:59:59Z`);
    const now = Date.now();
    const windowStart = end.getTime() - HOLIDAY_WINDOW_DAYS * 24 * 60 * 60 * 1000;
    if (now >= windowStart && now <= end.getTime()) {
      const md = end.toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});
      parts.push(`Order by ${md} for ${cutoff.label}`);
    }
  }
  return parts.join(' · ');
}

export function PdpUrgencyStrip({line: rawLine, avatars = [], buyerCount = 0, holidayCutoff}) {
  const line = rawLine && !UNPROVABLE.test(rawLine) ? rawLine : trueUrgency(holidayCutoff);
  if (!line && !avatars.length) return null;
  return (
    <div className="px-4 pt-2 md:px-0" data-urgency-strip>
      {line && (
        <p data-true-urgency className="m-0 inline-block rounded border border-accent/40 bg-accent/5 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[.05em] text-accent-700">
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
              {buyerCount} reviews from buyers
            </span>
          )}
        </div>
      )}
    </div>
  );
}
