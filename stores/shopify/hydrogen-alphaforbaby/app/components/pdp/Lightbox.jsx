import {useEffect} from 'react';
import {X} from 'lucide-react';

/**
 * Full-screen viewer for a single enlarged photo or video.
 *
 * Generalized 2026-09-29 (Itzik) to also carry the gallery's own product
 * photos and its Slot 2 demo video, not only customer review photos — same
 * interaction contract either way (skill 09, "review card" spec): closes on
 * the X button, on a click anywhere outside the media, and on Escape. Body
 * scroll is locked while open so the page behind doesn't move under the
 * overlay.
 *
 * The enlarged video gets native `controls` — unlike the ambient gallery
 * slide, this is a deliberate, user-opened view, so playback control makes
 * sense here. That still respects the "at most one <video> on the page"
 * rule (7.D — v1.23 incident): the gallery slide steps aside to its poster
 * frame while this is open (see PdpGallery), so this is always the only
 * <video> actually in the DOM at that moment.
 *
 * @param {{
 *   media: {type: 'image'|'video', src: string, alt?: string, poster?: string}|null,
 *   onClose: () => void,
 * }}
 */
export function Lightbox({media, onClose}) {
  useEffect(() => {
    if (!media) return undefined;
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
  }, [media, onClose]);

  if (!media) return null;
  const {type, src, alt = '', poster} = media;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={type === 'video' ? 'Product video' : 'Product photo'}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <button
        type="button"
        aria-label={type === 'video' ? 'Close video' : 'Close photo'}
        onClick={onClose}
        className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-ink shadow"
      >
        <X size={20} />
      </button>

      {/* Stop propagation so clicking the media itself doesn't close it —
          click-outside stays the intended dismissal. */}
      {type === 'video' ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption -- supplier demo clip ships without a caption track
        <video
          src={src}
          poster={poster || undefined}
          controls
          autoPlay
          playsInline
          onClick={(e) => e.stopPropagation()}
          className="max-h-[88vh] max-w-[92vw] rounded-lg shadow-2xl"
        />
      ) : (
        <img
          src={src}
          alt={alt}
          onClick={(e) => e.stopPropagation()}
          className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
        />
      )}
    </div>
  );
}
