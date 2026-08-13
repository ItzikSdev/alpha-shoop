import {useEffect, useRef, useState} from 'react';
import {Image} from '@shopify/hydrogen';
import {ChevronLeft, ChevronRight, RotateCw} from 'lucide-react';

/**
 * Horizontal scroll-snap gallery — "Classical" theme (2026-08-02 handoff).
 * Every slide sits inside a `.plate` frame (surface mat + accent outline).
 * Touch/trackpad swipe already works natively; the left/right arrows are for
 * desktop/PC mouse users (md+ only — mobile relies on swipe, no arrows there).
 *
 * The 360° button (when a product video exists) is rendered once, pinned to
 * the gallery wrapper itself — not per-slide — so it never moves as the
 * carousel is scrolled/swiped between images.
 * @param {{
 *   images: Array<{id: string; url: string; altText?: string | null; width?: number; height?: number}>;
 *   selectedVariantImage?: {id: string; url: string; altText?: string | null; width?: number; height?: number} | null;
 *   discountPercent?: number;
 *   videoSource?: {url: string; mimeType: string} | null;
 * }}
 */
export function ProductGallery({images, selectedVariantImage, discountPercent, videoSource}) {
  const gallery = images?.length ? images : [];
  const trackRef = useRef(null);
  const [playingVideo, setPlayingVideo] = useState(false);
  const loopCountRef = useRef(0);

  const handleVideoEnded = (e) => {
    loopCountRef.current += 1;
    if (loopCountRef.current >= 2) {
      e.currentTarget.pause();
      setPlayingVideo(false);
    } else {
      e.currentTarget.play();
    }
  };

  // Captured once (not in an effect) so it survives React StrictMode's
  // dev-only double-invoke of effects. The carousel should open on the lead
  // slide (the AI baby photo), not jump to the default variant's own photo
  // — only scroll when the shopper actually changes color/variant.
  const initialVariantImageIdRef = useRef(selectedVariantImage?.id);
  useEffect(() => {
    if (!selectedVariantImage || !trackRef.current) return;
    if (selectedVariantImage.id === initialVariantImageIdRef.current) return;
    const idx = gallery.findIndex((img) => img.id === selectedVariantImage.id);
    if (idx === -1) return;
    const track = trackRef.current;
    const slide = track.children[idx];
    slide?.scrollIntoView({behavior: 'smooth', inline: 'center', block: 'nearest'});
  }, [selectedVariantImage?.id]);

  if (!gallery.length) return null;

  const scrollByOne = (direction) => {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({left: direction * track.clientWidth, behavior: 'smooth'});
  };

  return (
    <div className="relative">
      <div
        ref={trackRef}
        className="no-scrollbar flex snap-x snap-mandatory gap-2 overflow-x-auto px-4 pb-3 pt-4"
      >
        {gallery.map((img, index) => (
          <figure key={img.id} className="relative w-full flex-none snap-center">
            <div className="plate rounded">
              <Image
                alt={img.altText || ''}
                aspectRatio="1/1"
                data={img}
                sizes="(min-width: 430px) 430px, 100vw"
                loading={index === 0 ? 'eager' : 'lazy'}
                className="aspect-square w-full object-cover"
              />
            </div>
            {index === 0 && discountPercent > 0 && (
              <span className="tag tag-outline tnum absolute left-3 top-3 bg-bg">
                SAVE {discountPercent}%
              </span>
            )}
          </figure>
        ))}
      </div>

      {/* Video overlay sits above the whole track (not a slide), so it covers
          whichever image is currently scrolled into view. */}
      {videoSource && playingVideo && (
        <div className="pointer-events-none absolute inset-0 px-4 pb-3 pt-4">
          <div className="plate pointer-events-auto relative aspect-square w-full overflow-hidden rounded">
            <video
              src={videoSource.url}
              autoPlay
              muted
              playsInline
              onEnded={handleVideoEnded}
              className="h-full w-full object-cover"
            />
          </div>
        </div>
      )}

      {gallery.length > 1 && (
        <>
          <button
            type="button"
            aria-label="Previous image"
            onClick={() => scrollByOne(-1)}
            className="btn btn-primary btn-icon absolute left-6 top-1/2 z-10 hidden -translate-y-1/2 bg-bg md:flex"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            type="button"
            aria-label="Next image"
            onClick={() => scrollByOne(1)}
            className="btn btn-primary btn-icon absolute right-6 top-1/2 z-10 hidden -translate-y-1/2 bg-bg md:flex"
          >
            <ChevronRight size={18} />
          </button>
        </>
      )}

      {/* Pinned to the gallery wrapper (not a slide) so it never moves as the
          carousel scrolls between images. */}
      {videoSource && (
        <button
          type="button"
          aria-label={playingVideo ? 'Show photo' : 'Play 360° video'}
          onClick={() => {
            loopCountRef.current = 0;
            setPlayingVideo((v) => !v);
          }}
          className="absolute bottom-6 right-6 z-20 flex items-center gap-1 rounded-full bg-white/90 px-2.5 py-1.5 text-[11px] font-semibold shadow"
        >
          <RotateCw size={12} />
          360°
        </button>
      )}
    </div>
  );
}
