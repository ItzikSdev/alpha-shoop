import {useEffect, useRef, useState} from 'react';
import {Image} from '@shopify/hydrogen';
import {ChevronLeft, ChevronRight, Expand, Play} from 'lucide-react';
import {Lightbox} from '~/components/pdp/Lightbox';

/** Most dots to draw before switching to a sliding window + "n / total". */
const DOT_WINDOW = 5;

/**
 * Product media viewer.
 *
 * 2026-09-29 (Itzik): skill 09 §7.B Slot 2 — when this product has a real
 * demo clip, it is slide 0 of this gallery, before any photos, with an
 * accent-colored play badge on its thumbnail. This used to say "photos
 * only, deliberately" because the same clip was once ALSO embedded as its
 * own player further down the page (PdpHowToUse / the standalone video
 * section) — two independent <video> elements playing the one clip the
 * shopper already saw in the ad (7.D — the v1.23 incident). The fix here is
 * not "no video in the gallery", it's "exactly one video, and this is where
 * it lives": the other player is gone, and `test_exactly_one_video_instance_on_page`
 * guards against it coming back. See the click-to-enlarge note below for how
 * that invariant survives the lightbox too.
 *
 * There is still no "360°" affordance anywhere: these products ship a flat
 * demo clip, not a rotation asset.
 *
 * Every slide — the video and every photo — opens in the shared Lightbox on
 * click/tap, closable via its own X, a click outside the media, or Escape.
 *
 * @param {{
 *   images: Array<{id: string, url: string, altText?: string|null, width?: number, height?: number}>,
 *   video?: {url: string, mimeType?: string, poster?: string|null}|null,
 *   selectedVariantImage?: {id: string, url: string}|null,
 *   hasUserPicked?: boolean,
 *   title: string,
 * }}
 */
/** Compare two Shopify image URLs by file name — the CDN serves one file under
 * many sizes and query strings, so a string compare on the whole URL misses. */
function sameImage(a, b) {
  const key = (u) => (u || '').split('?')[0].split('/').pop().toLowerCase();
  return !!a && !!b && key(a) === key(b);
}

export function PdpGallery({
  images = [],
  video = null,
  selectedVariantImage,
  hasUserPicked = false,
  title,
}) {
  const hasVideo = !!video;
  const slides = [
    ...(hasVideo ? [{kind: 'video', id: 'gallery-video', ...video}] : []),
    ...images.map((i) => ({kind: 'image', ...i})),
  ];
  const [index, setIndex] = useState(0);
  const [lightboxMedia, setLightboxMedia] = useState(null);
  const trackRef = useRef(null);

  // 7.D #43 / Level 01 rule 9: the picture follows the choice. This prop was
  // being received and ignored, which is why the gallery never moved no matter
  // what the shopper picked in Buy 1 or in any Buy 2 unit row.
  const targetUrl = selectedVariantImage?.url;
  // A programmatic scroll emits onScroll for every intermediate frame, and that
  // handler recomputes `index` from scrollLeft — so a smooth jump would leave
  // the active slide on whatever it happened to pass through. Suppress the
  // handler for the duration of our own scroll, and jump instantly: "the
  // picture matches the choice" should be immediate, not animated.
  const programmatic = useRef(false);
  useEffect(() => {
    // When this product has a video, slide 0 is it — and the whole point of
    // Slot 2 is that an ad visitor's first screen is the same clip they just
    // watched in the ad. `selectedVariant` (and therefore `targetUrl`) is
    // already resolved from the URL on mount — with a Facebook `?Style=…`
    // deep link, that fired on every single load and scrolled straight past
    // the video before it ever painted. So: don't auto-jump away from the
    // video until the shopper has actually picked something themselves
    // (`hasUserPicked`, set the moment Buy 1 or any Buy 2 unit reports a
    // real choice — see products.$handle.jsx). Products without a video, and
        // any product once a real choice has been made, keep the original
    // behavior unchanged: the picture follows the choice, immediately.
    if (hasVideo && !hasUserPicked) return;
    if (!targetUrl) return;
    const i = slides.findIndex((s) => s.kind === 'image' && sameImage(s.url, targetUrl));
    if (i < 0) return;
    programmatic.current = true;
    setIndex(i);
    trackRef.current?.children[i]?.scrollIntoView({
      behavior: 'auto',
      inline: 'center',
      block: 'nearest',
    });
    const t = setTimeout(() => {
      programmatic.current = false;
    }, 150);
    return () => clearTimeout(t);
    // slides is derived from `images`/`video`, which are stable for a given product
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetUrl, hasUserPicked, hasVideo]);

  // Keeps whatever slide `targetUrl` currently points to eager-loaded, so
  // that when the jump above does fire, the image is never a blank box
  // (native lazy-loading doesn't fire for a slide parked off to the side of
  // a horizontal scroller). Measured live 2026-09-25 on the egg page: the
  // opening slide had naturalWidth 0.
  const openingIndex = Math.max(
    0,
    slides.findIndex((s) => s.kind === 'image' && sameImage(s.url, targetUrl)),
  );

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

  // The lightbox's enlarged video is the only <video> allowed on the page
  // while it's open (7.D — v1.23's "two independent players" incident, and
  // test_exactly_one_video_instance_on_page). So the inline gallery slide
  // steps aside to a plain poster frame for as long as that lightbox is open,
  // rather than doubling up.
  const videoLightboxOpen = lightboxMedia?.type === 'video';

  // The data-* hooks below exist for the §5C parity gate: it must be able to
  // count slides and dots on the rendered page without matching Tailwind class
  // strings, which change whenever the design does.
  return (
    <div className="relative" data-pdp-gallery>
      <ul
        ref={trackRef}
        className="m-0 flex list-none snap-x snap-mandatory gap-2 overflow-x-auto p-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        onScroll={(e) => {
          if (programmatic.current) return;
          const w = e.currentTarget.clientWidth || 1;
          setIndex(Math.round(e.currentTarget.scrollLeft / w));
        }}
      >
        {slides.map((slide, i) => (
          <li
            key={slide.id ?? i}
            data-gallery-slide
            {...(i === index ? {'data-gallery-active': ''} : {})}
            className="w-full flex-none snap-center"
          >
            {slide.kind === 'video' ? (
              <button
                type="button"
                aria-label="Enlarge video"
                onClick={() =>
                  setLightboxMedia({type: 'video', src: slide.url, poster: slide.poster})
                }
                className="group relative block aspect-square w-full overflow-hidden rounded-lg bg-black"
              >
                {videoLightboxOpen ? (
                  slide.poster && (
                    <img src={slide.poster} alt="" className="h-full w-full object-cover" />
                  )
                ) : (
                  // eslint-disable-next-line jsx-a11y/media-has-caption -- supplier demo clip ships without a caption track
                  <video
                    className="h-full w-full object-cover"
                    src={slide.url}
                    poster={slide.poster || undefined}
                    autoPlay
                    muted
                    loop
                    playsInline
                    preload="auto"
                  />
                )}
                <span className="pointer-events-none absolute bottom-2 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white">
                  <Expand size={16} />
                </span>
              </button>
            ) : (
              <button
                type="button"
                aria-label="Enlarge image"
                onClick={() =>
                  setLightboxMedia({type: 'image', src: slide.url, alt: slide.altText || title})
                }
                className="group relative block w-full"
              >
                <Image
                  data={slide}
                  alt={slide.altText || title}
                  aspectRatio="1/1"
                  sizes="(min-width: 768px) 560px, 100vw"
                  className="w-full rounded-lg object-cover"
                  loading={i < 3 || i === openingIndex ? 'eager' : 'lazy'}
                  fetchPriority={i === openingIndex ? 'high' : undefined}
                />
                {/* Always visible, not hover-only (Itzik, 2026-09-29): on
                    mobile there's no hover state, so this badge used to be
                    invisible until the very tap that reveals it does
                    something -- exactly the "unresponsive click" pattern
                    Clarity flagged. Matches the video slide's badge, which
                    was already always-on. */}
                <span className="pointer-events-none absolute bottom-2 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white transition-transform group-hover:scale-110">
                  <Expand size={16} />
                </span>
              </button>
            )}
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
                aria-label={slide.kind === 'video' ? 'Show video' : `Show image ${i + 1}`}
                className={`relative block h-14 w-14 overflow-hidden rounded border ${
                  i === index ? 'border-accent' : 'border-divider'
                }`}
              >
                {slide.kind === 'video' ? (
                  <span className="relative block h-full w-full bg-black">
                    {/* Poster frame, never a second <video> element — the
                        thumbnail strip renders on every viewport width
                        (Tailwind's md:flex only changes CSS display, not the
                        DOM), so a live <video> here would sit right next to
                        the autoplaying main slide and trip the "exactly one
                        video on the page" rule. */}
                    {slide.poster && (
                      <img src={slide.poster} alt="" className="h-full w-full object-cover" />
                    )}
                    <span className="pointer-events-none absolute inset-0 flex items-center justify-center">
                      <Play size={16} className="fill-accent text-accent drop-shadow" />
                    </span>
                  </span>
                ) : (
                  <img src={slide.url} alt="" className="h-full w-full object-cover" loading="lazy" />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <Lightbox media={lightboxMedia} onClose={() => setLightboxMedia(null)} />
    </div>
  );
}
