import {useEffect, useState} from 'react';
import {ArrowUp} from 'lucide-react';

/**
 * Floating "back to top" button (Itzik, 2026-09-28). Appears once the page
 * is scrolled down a bit and smooth-scrolls to the top on click. Rendered
 * once from PageLayout so it shows on every page, not just the PDP.
 */
export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    function onScroll() {
      setVisible(window.scrollY > 480);
    }
    onScroll();
    window.addEventListener('scroll', onScroll, {passive: true});
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  if (!visible) return null;

  return (
    <button
      type="button"
      className="tob-back-to-top reset"
      aria-label="Back to top"
      onClick={() => window.scrollTo({top: 0, behavior: 'smooth'})}
    >
      <ArrowUp size={20} strokeWidth={2.25} />
    </button>
  );
}
