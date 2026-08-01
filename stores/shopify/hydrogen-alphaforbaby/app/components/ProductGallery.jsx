import {useEffect, useState} from 'react';
import {Image} from '@shopify/hydrogen';


/**
 * Main image + clickable thumbnail strip. Defaults to the selected variant's
 * photo (so a Color swap in ProductForm still updates the hero image), but
 * lets the shopper click through the product's full image set independently.
 * @param {{
 *   images: Array<{id: string; url: string; altText?: string | null; width?: number; height?: number}>;
 *   selectedVariantImage?: {id: string; url: string; altText?: string | null; width?: number; height?: number} | null;
 * }}
 */
export function ProductGallery({images, selectedVariantImage}) {
  const gallery = images?.length ? images : [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [autoPlay, setAutoPlay] = useState(true);
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);
  useEffect(() => {
    if (!selectedVariantImage) return;
    const idx = gallery.findIndex((img) => img.id === selectedVariantImage.id);
    if (idx !== -1) {
      setCurrentIndex(idx);
      setAutoPlay(false);
    }
  }, [selectedVariantImage?.id]);

  useEffect(() => {
    if (!autoPlay || gallery.length <= 1) return;
    const interval = setInterval(() => {
      setCurrentIndex(prev => (prev + 1) % gallery.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [autoPlay, gallery.length]);

  useEffect(() => {
    const handleMouseEnter = () => setAutoPlay(false);
    const handleMouseLeave = () => setAutoPlay(true);

    const handleTouchStart = (e) => setTouchStart(e.touches[0].clientX);
    const handleTouchEnd = (e) => {
      const end = e.changedTouches[0].clientX;
      setTouchEnd(end);
      const diff = touchStart - end;
      if (diff > 50) setCurrentIndex(prev => (prev + 1) % gallery.length);
      if (diff < -50) setCurrentIndex(prev => (prev - 1 + gallery.length) % gallery.length);
    };

    document.addEventListener('mouseenter', handleMouseEnter);
    document.addEventListener('mouseleave', handleMouseLeave);
    document.addEventListener('touchstart', handleTouchStart);
    document.addEventListener('touchend', handleTouchEnd);

    return () => {
      document.removeEventListener('mouseenter', handleMouseEnter);
      document.removeEventListener('mouseleave', handleMouseLeave);
      document.removeEventListener('touchstart', handleTouchStart);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [autoPlay, touchStart, touchEnd, gallery.length]);

  return (
    <div className="tobp-carousel">
      {gallery.length === 1 && (
        <Image alt={gallery[0].altText || ''} aspectRatio="1/1" data={gallery[0]} sizes="(min-width: 45em) 50vw, 100vw" />
      )}
      {gallery.length > 1 && (
        <div className="tobp-carousel-nav">
          <div className="tobp-carousel-viewport">
            <div className="tobp-carousel-track" style={{transform: `translateX(-${currentIndex * 100}%)`}}>
              {gallery.map((img, index) => (
                <div key={img.id} className="tobp-carousel-slide">
                  <Image
                    alt={img.altText || ''}
                    aspectRatio="1/1"
                    data={img}
                    sizes="100vw"
                  />
                </div>
              ))}
            </div>
            <button
              type="button"
              className="tobp-carousel-arrow tobp-carousel-arrow-prev"
              aria-label="Previous image"
              onClick={() => setCurrentIndex((prev) => (prev - 1 + gallery.length) % gallery.length)}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <button
              type="button"
              className="tobp-carousel-arrow tobp-carousel-arrow-next"
              aria-label="Next image"
              onClick={() => setCurrentIndex((prev) => (prev + 1) % gallery.length)}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 6 15 12 9 18" />
              </svg>
            </button>
          </div>
          <div className="tobp-carousel-dots">
            {gallery.map((img, index) => (
              <button
                key={img.id}
                className={`tobp-carousel-dot ${index === currentIndex ? 'active' : ''}`}
                onClick={() => setCurrentIndex(index)}
              ></button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
