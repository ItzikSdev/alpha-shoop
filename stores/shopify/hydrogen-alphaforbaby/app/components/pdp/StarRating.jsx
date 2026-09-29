import {Star} from 'lucide-react';

/**
 * A star row that shows the *actual* average, not a rounded one.
 *
 * Rounding is why this exists: a 4.75 average through Math.round() draws five
 * solid stars, visually identical to a flawless 5.0, overstating the product to
 * every shopper who never reads the number.
 *
 * Why this is built per-star rather than as two stacked rows: the first attempt
 * overlaid a gold row on a grey row and clipped the gold one by width. The two
 * rows then laid out independently — the clipped row's flex items resolved to
 * 19.1px against the base row's 20px — so the stars drifted ~0.9px each and sat
 * visibly doubled by the fifth star (7.D #27). There is only one row here. Each
 * star is a single box containing a grey glyph with a gold copy clipped over
 * it, so a star's position is decided once and both layers of that star share
 * it by construction; no second row exists to drift.
 *
 * @param {{value: number, size?: number, className?: string}}
 */
export function StarRating({value = 0, size = 17, className = ''}) {
  const clamped = Math.max(0, Math.min(5, Number(value) || 0));

  return (
    <span
      className={`inline-flex flex-none items-center ${className}`}
      role="img"
      aria-label={`${clamped.toFixed(1)} out of 5 stars`}
    >
      {Array.from({length: 5}, (_, i) => {
        // Portion of THIS star that should be gold: 1 for a full star, 0 for an
        // empty one, the fraction in between for the single partial star.
        const fill = Math.max(0, Math.min(1, clamped - i));
        return (
          <span
            key={i}
            className="relative inline-block flex-none"
            style={{width: size, height: size, lineHeight: 0}}
            aria-hidden="true"
          >
            <Star size={size} color="#F5B301" fill="none" className="absolute left-0 top-0" />
            {fill > 0 && (
              <span
                className="absolute left-0 top-0 overflow-hidden"
                style={{width: `${fill * 100}%`, height: size}}
              >
                {/* fixed size, pinned to this star's own origin — it cannot
                    reflow independently of the outline beneath it */}
                <Star
                  size={size}
                  color="#F5B301"
                  fill="#F5B301"
                  className="absolute left-0 top-0 max-w-none"
                />
              </span>
            )}
          </span>
        );
      })}
    </span>
  );
}
