import {useCallback, useEffect, useRef, useState} from 'react';
import {ChevronLeft, ChevronRight, X} from 'lucide-react';

/**
 * Level 09 Section 7.C.1 (v3.3) — review photos must be browsable.
 *
 * Before this, review photos rendered as a static wrapped block: no arrows, no
 * swipe, no scroll container anywhere on the site. Customers read photo reviews
 * more than they read our copy, so this is the one place a static grid costs
 * real money.
 *
 * Mobile: a horizontally scrolling row with `scroll-snap-type: x mandatory` and
 * one snap point per photo. `touch-action: pan-x` keeps a finger drag on this
 * strip from fighting the vertical page scroll.
 * Desktop: 44x44 prev/next buttons, disabled at the ends, plus arrow keys when
 * the strip has focus.
 * Both: tapping a photo opens it large with the same navigation, a close
 * control, and the reviewer's name, country and rating beside it.
 *
 * @param {{photos: Array<{src:string, name?:string, country?:string, rating?:number}>,
 *          size?: number, className?: string}}
 */
export function ReviewPhotoStrip({photos = [], size = 80, className = '', marked = true}) {
  const stripRef = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);
  const [open, setOpen] = useState(-1);

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
  }, [sync, photos.length]);

  const step = (dir) => {
    const el = stripRef.current;
    if (!el) return;
    // one photo + gap; falls back to a third of the viewport if we can't measure
    const first = el.querySelector('[data-review-photo]');
    const by = first ? first.getBoundingClientRect().width + 8 : el.clientWidth / 3;
    el.scrollBy({left: dir * by, behavior: 'smooth'});
  };

  const onKey = (e) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      step(1);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      step(-1);
    }
  };

  useEffect(() => {
    if (open < 0) return undefined;
    const onWinKey = (e) => {
      if (e.key === 'Escape') setOpen(-1);
      if (e.key === 'ArrowRight') setOpen((i) => Math.min(photos.length - 1, i + 1));
      if (e.key === 'ArrowLeft') setOpen((i) => Math.max(0, i - 1));
    };
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onWinKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onWinKey);
    };
  }, [open, photos.length]);

  if (!photos.length) return null;
  const many = photos.length > 1;
  const cur = open >= 0 ? photos[open] : null;

  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-1">
        {many && (
          <button
            type="button"
            {...(marked ? {'data-review-prev': ''} : {})}
            aria-label="Previous photo"
            disabled={atStart}
            onClick={() => step(-1)}
            className="hidden h-11 w-11 flex-none items-center justify-center rounded-full border border-divider bg-white text-ink transition disabled:opacity-30 md:inline-flex"
          >
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
        )}

        <ul
          ref={stripRef}
          {...(marked ? {'data-review-photos': ''} : {})}
          tabIndex={0}
          onKeyDown={onKey}
          aria-label="Customer photos"
          className="m-0 flex list-none gap-2 overflow-x-auto p-0 [-webkit-overflow-scrolling:touch] [scrollbar-width:none] [touch-action:pan-x] [&::-webkit-scrollbar]:hidden"
          style={{scrollSnapType: 'x mandatory'}}
        >
          {photos.map((p, i) => (
            <li key={p.src} className="flex-none" style={{scrollSnapAlign: 'start'}}>
              <button
                type="button"
                aria-label={`Enlarge photo ${i + 1} of ${photos.length}${p.name ? ` from ${p.name}'s review` : ''}`}
                onClick={() => setOpen(i)}
                className="block cursor-zoom-in"
              >
                <img
                  data-review-photo
                  src={p.src}
                  alt={p.name ? `Photo from ${p.name}'s review` : 'Customer photo'}
                  loading="lazy"
                  style={{width: size, height: size}}
                  className="rounded-md border border-divider object-cover transition hover:opacity-90"
                />
              </button>
            </li>
          ))}
        </ul>

        {many && (
          <button
            type="button"
            {...(marked ? {'data-review-next': ''} : {})}
            aria-label="Next photo"
            disabled={atEnd}
            onClick={() => step(1)}
            className="hidden h-11 w-11 flex-none items-center justify-center rounded-full border border-divider bg-white text-ink transition disabled:opacity-30 md:inline-flex"
          >
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        )}
      </div>

      {cur && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Customer photo"
          onClick={() => setOpen(-1)}
        >
          <div className="relative max-h-full w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              aria-label="Close photo"
              onClick={() => setOpen(-1)}
              className="absolute -top-2 right-0 flex h-11 w-11 items-center justify-center rounded-full bg-white text-ink"
            >
              <X size={18} aria-hidden="true" />
            </button>
            <img
              src={cur.src}
              alt={cur.name ? `Photo from ${cur.name}'s review` : 'Customer photo'}
              className="max-h-[70vh] w-full rounded-lg object-contain"
            />
            <div className="mt-2 flex items-center justify-between gap-3 rounded-lg bg-white/95 px-3 py-2">
              <span className="text-[13px] font-semibold">
                {cur.name}
                {cur.country ? ` ${cur.country}` : ''}
              </span>
              {cur.rating ? (
                <span className="text-[13px] text-accent-700" aria-label={`${cur.rating} out of 5 stars`}>
                  {'★'.repeat(cur.rating)}
                  <span className="text-ink/25">{'★'.repeat(5 - cur.rating)}</span>
                </span>
              ) : null}
            </div>
            {many && (
              <>
                <button
                  type="button"
                  aria-label="Previous photo"
                  disabled={open === 0}
                  onClick={() => setOpen((i) => Math.max(0, i - 1))}
                  className="absolute left-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-ink disabled:opacity-30"
                >
                  <ChevronLeft size={20} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  aria-label="Next photo"
                  disabled={open === photos.length - 1}
                  onClick={() => setOpen((i) => Math.min(photos.length - 1, i + 1))}
                  className="absolute right-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-ink disabled:opacity-30"
                >
                  <ChevronRight size={20} aria-hidden="true" />
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
