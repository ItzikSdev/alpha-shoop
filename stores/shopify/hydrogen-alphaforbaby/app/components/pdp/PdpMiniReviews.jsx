import {useCallback, useEffect, useRef, useState} from 'react';
import {ChevronLeft, ChevronRight, Star} from 'lucide-react';

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

  // 7.C.1: the card row already scrolled and snapped, but carried no marks and
  // no controls — a mouse user had no way to step through it.
  const stripRef = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);
  const sync = useCallback(() => {
    const el = stripRef.current;
    if (!el) return;
    setAtStart(el.scrollLeft <= 1);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 1);
  }, []);
  useEffect(() => {
    sync();
    const el = stripRef.current;
    if (!el) return undefined;
    el.addEventListener('scroll', sync, {passive: true});
    window.addEventListener('resize', sync);
    return () => {
      el.removeEventListener('scroll', sync);
      window.removeEventListener('resize', sync);
    };
  }, [sync, withPhotos.length]);
  const step = (dir) => {
    const el = stripRef.current;
    if (!el) return;
    const card = el.querySelector('li');
    const by = card ? card.getBoundingClientRect().width + 12 : el.clientWidth / 2;
    el.scrollBy({left: dir * by, behavior: 'smooth'});
  };

  return (
    <section className="pt-4" data-mini-reviews>
      <div className="flex items-center gap-1">
      {withPhotos.length > 1 && (
        <button type="button" data-mini-prev aria-label="Previous photo" disabled={atStart}
          onClick={() => step(-1)}
          className="hidden h-11 w-11 flex-none items-center justify-center rounded-full border border-divider bg-white text-ink disabled:opacity-30 md:inline-flex">
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
      )}
      <ul
        ref={stripRef}
        data-mini-strip
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') { e.preventDefault(); step(1); }
          if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
        }}
        className="flex list-none snap-x snap-mandatory gap-3 overflow-x-auto p-0 [-webkit-overflow-scrolling:touch] [touch-action:pan-x] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {withPhotos.map((r) => (
          <li
            key={r.id}
            className="w-[230px] flex-none snap-start rounded-lg border border-divider bg-white p-3"
          >
            <div className="flex items-center gap-2">
              <img
                /* not [data-review-photo]: this is the reviewer's avatar inside
                   a card, not a photo in the browsable gallery — clicking it
                   opens nothing, and marking it made the lightbox test click
                   here instead of the gallery. The card row itself is the
                   browsable surface here (arrows + snap, 7.C.1). */
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
      {withPhotos.length > 1 && (
        <button type="button" data-mini-next aria-label="Next photo" disabled={atEnd}
          onClick={() => step(1)}
          className="hidden h-11 w-11 flex-none items-center justify-center rounded-full border border-divider bg-white text-ink disabled:opacity-30 md:inline-flex">
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      )}
      </div>
    </section>
  );
}
