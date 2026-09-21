import {Star} from 'lucide-react';

/**
 * Mini review carousel — §5 item 4, sitting between the price and the bundle
 * block (the blank gap Itzik spotted on mobile was this section missing).
 *
 * Carries a gold star row (v1.36 — the new reference screenshot shows one;
 * v1.30's original "no stars" note is superseded).
 * This is a short confidence nudge at the buy decision — photo, name, one quote.
 *
 * Only reviews that genuinely carry a buyer photo are eligible, and only real
 * ones are shown — if fewer than 3 exist, it renders fewer rather than padding
 * with reviews that have no photo (Rule 1).
 *
 * The round thumbnail is the buyer's own submitted product photo, not a
 * portrait — these are real customer uploads, and no headshot is implied.
 *
 * @param {{reviews: Array<object>, limit?: number}}
 */
export function PdpMiniReviews({reviews = [], limit = 4}) {
  const withPhotos = reviews
    .filter((r) => Array.isArray(r.photos) && r.photos.length && r.comment)
    // shortest, punchiest quotes first — a mini card can't carry a paragraph
    .sort((a, b) => a.comment.length - b.comment.length)
    .slice(0, limit);

  if (!withPhotos.length) return null;

  return (
    <section className="pt-4" data-mini-reviews>
      <ul className="flex list-none snap-x snap-mandatory gap-3 overflow-x-auto p-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {withPhotos.map((r) => (
          <li
            key={r.id}
            className="w-[230px] flex-none snap-start rounded-lg border border-divider bg-white p-3"
          >
            <div className="flex items-center gap-2">
              <img
                src={r.photos[0]}
                alt={`Photo shared by ${r.name}`}
                loading="lazy"
                className="h-9 w-9 flex-none rounded-full border border-divider object-cover"
              />
              <span className="truncate text-[13px] font-semibold">
                {r.name}
                {r.country ? ` ${r.country}` : ''}
              </span>
            </div>
            <span className="mt-1.5 inline-flex" aria-label={`${r.rating} out of 5`}>
              {Array.from({length: 5}, (_, i) => (
                <Star key={i} size={15} color="#F5B301"
                  fill={i < (r.rating || 0) ? '#F5B301' : 'none'} aria-hidden="true" />
              ))}
            </span>
            <p className="mt-1.5 line-clamp-3 text-[13px] leading-snug text-ink/75">
              &ldquo;{r.comment}&rdquo;
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
