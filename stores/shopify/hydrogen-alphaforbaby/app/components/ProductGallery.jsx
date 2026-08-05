import {useEffect, useRef} from 'react';
import {Image} from '@shopify/hydrogen';
import {ChevronLeft, ChevronRight} from 'lucide-react';

/**
 * Horizontal scroll-snap gallery — "Classical" theme (2026-08-02 handoff).
 * Every slide sits inside a `.plate` frame (surface mat + accent outline).
 * Touch/trackpad swipe already works natively; the left/right arrows are for
 * desktop/PC mouse users (md+ only — mobile relies on swipe, no arrows there).
 * @param {{
 *   images: Array<{id: string; url: string; altText?: string | null; width?: number; height?: number}>;
 *   selectedVariantImage?: {id: string; url: string; altText?: string | null; width?: number; height?: number} | null;
 *   discountPercent?: number;
 * }}
 */
export function ProductGallery({images, selectedVariantImage, discountPercent}) {
  const gallery = images?.length ? images : [];
  const trackRef = useRef(null);

  useEffect(() => {
    if (!selectedVariantImage || !trackRef.current) return;
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
    </div>
  );
}
