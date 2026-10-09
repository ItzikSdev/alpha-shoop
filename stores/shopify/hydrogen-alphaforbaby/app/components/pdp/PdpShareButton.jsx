import {useState} from 'react';
import {Share2, MessageCircle, Link as LinkIcon, Check} from 'lucide-react';

/**
 * Small share button in the corner of the product gallery (Itzik, 2026-09-28).
 * Uses the native Web Share API where available — on mobile this opens the
 * OS share sheet, which already lists WhatsApp, Messages, etc. with zero
 * extra code. Falls back to a small popover (WhatsApp / Facebook / copy
 * link) for browsers without `navigator.share`, which today is most
 * desktop browsers.
 *
 * @param {{title: string, url?: string}}
 */
export function PdpShareButton({title, url}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const shareUrl = url || (typeof window !== 'undefined' ? window.location.href : '');

  async function handleClick() {
    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({title, url: shareUrl});
      } catch {
        // The shopper cancelled the native share sheet — nothing to do.
      }
      return;
    }
    setOpen((o) => !o);
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API unavailable (e.g. non-HTTPS/older browser) — the
      // popover stays open so the shopper can still see/select the link.
    }
  }

  return (
    <div className="absolute right-2 top-2 z-10">
      <button
        type="button"
        aria-label="Share this product"
        onClick={handleClick}
        className="flex items-center justify-center rounded-full bg-white/90 p-2 shadow"
      >
        <Share2 size={18} />
      </button>

      {open && (
        <>
          {/* Click-outside catcher */}
          <button
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-0 cursor-default"
          />
          <div className="absolute right-0 top-11 z-10 flex min-w-[180px] flex-col gap-1 rounded-lg bg-white p-2 shadow-lg">
            <a
              href={`https://wa.me/?text=${encodeURIComponent(`${title} ${shareUrl}`)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[14px] text-ink hover:bg-black/5"
            >
              <MessageCircle size={16} className="text-[#25D366]" />
              WhatsApp
            </a>
            <a
              href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[14px] text-ink hover:bg-black/5"
            >
              <FacebookGlyph />
              Facebook
            </a>
            <button
              type="button"
              onClick={copyLink}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-[14px] text-ink hover:bg-black/5"
            >
              {copied ? <Check size={16} /> : <LinkIcon size={16} />}
              {copied ? 'Copied!' : 'Copy link'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/** lucide-react dropped brand/logo glyphs, so this one's hand-rolled — same
 * pattern as the inline SVG icons in Header.jsx. */
function FacebookGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="12" fill="#1877F2" />
      <path
        fill="#fff"
        d="M13.4 21v-7.2h2.4l.36-2.8h-2.76V9.2c0-.81.22-1.36 1.39-1.36H16V5.34C15.72 5.3 14.76 5.2 13.64 5.2c-2.33 0-3.93 1.42-3.93 4.03v2.25H7.3v2.8h2.4V21h3.7z"
      />
    </svg>
  );
}
