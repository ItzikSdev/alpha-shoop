import {useRef, useState} from 'react';
import {Image} from '@shopify/hydrogen';
import {ChevronLeft, ChevronRight} from 'lucide-react';

/** Most dots to draw before switching to a sliding window + "n / total". */
const DOT_WINDOW = 5;

/**
 * Product photo viewer.
 *
 * Photos only, deliberately. There is one real demo clip per product, and it
 * lives in the "how to use it" section where it actually explains something —
 * embedding the same source in two independent <video> players made the page
 * look like it had two videos when it has one.
 *
 * There is also no "360°" affordance anywhere: these products ship a flat demo
 * clip, not a rotation asset.
 *
 * @param {{
 *   images: Array<{id: string, url: string, altText?: string|null, width?: number, height?: number}>,
 *   selectedVariantImage?: {id: string, url: string}|null,
 *   title: string,
 * }}
 */
export function PdpGallery({images = [], selectedVariantImage, title}) {
  const slides = images.map((i) => ({kind: 'image', ...i}));
  const [index, setIndex] = useState(0);
  const trackRef = useRef(null);

  if (!slides.length) return null;

  const go = (next) => {
    const i = Math.max(0, Math.min(slides.length - 1, next));
    setIndex(i);
    trackRef.current?.children[i]?.scrollIntoView({behavior: 'smooth', inline: 'center', block: 'nearest'});
  };

  // Which dot indices to draw: all of them for a short gallery, otherwise a
  // window of DOT_WINDOW centred on the current slide and clamped to the ends.
  const dotWindow = (() => {
    const n = slides.length;
    if (n <= DOT_WINDOW) return Array.from({length: n}, (_, i) => i);
    const half = Math.floor(DOT_WINDOW / 2);
    const start = Math.max(0, Math.min(index - half, n - DOT_WINDOW));
    return Array.from({length: DOT_WINDOW}, (_, k) => start + k);
  })();

  // The data-* hooks below exist for the §5C parity gate: it must be able to
  // count slides and dots on the rendered page without matching Tailwind class
  // strings, which change whenever the design does.
  return (
    <div className="relative" data-pdp-gallery>
      <ul
        ref={trackRef}
        className="m-0 flex list-none snap-x snap-mandatory gap-2 overflow-x-auto p-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        onScroll={(e) => {
          const w = e.currentTarget.clientWidth || 1;
          setIndex(Math.round(e.currentTarget.scrollLeft / w));
        }}
      >
        {slides.map((slide, i) => (
          <li key={slide.id ?? i} data-gallery-slide className="w-full flex-none snap-center">
            <Image
              data={slide}
              alt={slide.altText || title}
              aspectRatio="1/1"
              sizes="(min-width: 768px) 560px, 100vw"
              className="w-full rounded-lg object-cover"
              loading={i === 0 ? 'eager' : 'lazy'}
            />
          </li>
        ))}
      </ul>

      {slides.length > 1 && (
        <>
          <button
            type="button"
            aria-label="Previous image"
            onClick={() => go(index - 1)}
            className="absolute left-2 top-1/2 hidden -translate-y-1/2 rounded-full bg-white/90 p-2 shadow md:block"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            type="button"
            aria-label="Next image"
            onClick={() => go(index + 1)}
            className="absolute right-2 top-1/2 hidden -translate-y-1/2 rounded-full bg-white/90 p-2 shadow md:block"
          >
            <ChevronRight size={18} />
          </button>
        </>
      )}

      {/* One dot per slide only works for a short gallery. The crib has 21
          images, which rendered as a full-width band of 21 dots at 375px —
          unusable as a control and visually noisy (7.D #30). Past DOT_WINDOW
          slides this becomes a sliding window of dots plus a plain "n / total"
          counter, so the control stays a fixed width whatever the image count. */}
      {slides.length > 1 && (
        <div className="mt-3 flex items-center justify-center gap-2 md:hidden">
          <ul className="flex list-none items-center gap-2 p-0">
            {dotWindow.map((i) => (
              <li key={`d-${slides[i].id ?? i}`}>
                <button
                  type="button"
                  data-gallery-dot
                  aria-label={`Go to image ${i + 1} of ${slides.length}`}
                  aria-current={i === index}
                  onClick={() => go(i)}
                  className={`block h-2 rounded-full transition-all ${
                    i === index ? 'w-5 bg-accent' : 'w-2 bg-ink/25'
                  }`}
                />
              </li>
            ))}
          </ul>
          {slides.length > DOT_WINDOW && (
            <span className="tnum text-[12px] text-ink/55" aria-hidden="true">
              {index + 1} / {slides.length}
            </span>
          )}
        </div>
      )}

      {slides.length > 1 && (
        <ul className="mt-2 hidden list-none gap-2 overflow-x-auto p-0 md:flex">
          {slides.map((slide, i) => (
            <li key={`t-${slide.id ?? i}`}>
              <button
                type="button"
                onClick={() => go(i)}
                aria-label={`Show image ${i + 1}`}
                className={`block h-14 w-14 overflow-hidden rounded border ${
                  i === index ? 'border-accent' : 'border-divider'
                }`}
              >
                <img src={slide.url} alt="" className="h-full w-full object-cover" loading="lazy" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
