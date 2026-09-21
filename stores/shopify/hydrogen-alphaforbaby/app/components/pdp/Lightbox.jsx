import {useEffect} from 'react';
import {X} from 'lucide-react';

/**
 * Full-screen image viewer for customer photos.
 *
 * Closes on the X button, on a click anywhere outside the image, and on
 * Escape. Body scroll is locked while open so the page behind doesn't move
 * under the overlay.
 *
 * @param {{src: string|null, alt?: string, onClose: () => void}}
 */
export function Lightbox({src, alt = '', onClose}) {
  useEffect(() => {
    if (!src) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [src, onClose]);

  if (!src) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Customer photo"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <button
        type="button"
        aria-label="Close photo"
        onClick={onClose}
        className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-ink shadow"
      >
        <X size={20} />
      </button>

      {/* Stop propagation so clicking the photo itself doesn't close it —
          click-outside stays the intended dismissal. */}
      <img
        src={src}
        alt={alt}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
      />
    </div>
  );
}
