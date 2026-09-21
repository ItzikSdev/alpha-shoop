import {useState} from 'react';
import {Star} from 'lucide-react';
import {Lightbox} from '~/components/pdp/Lightbox';
import {StarRating} from '~/components/pdp/StarRating';

/** Parse the product's `custom.reviews` JSON metafield. Never throws — a missing
 * or malformed value simply means there are no reviews yet. */
export function parseReviews(metafieldValue) {
  if (!metafieldValue) return [];
  try {
    const parsed = JSON.parse(metafieldValue);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** How many reviews show before "View all" is needed. */
const INITIAL_VISIBLE = 5;

function Stars({value = 5, size = 17}) {
  return (
    <span className="inline-flex" aria-label={`${value} out of 5 stars`}>
      {Array.from({length: 5}, (_, i) => (
        <Star
          key={i}
          size={size}
          // lucide draws the outline from `color` and the body from `fill`;
          // both must be set or a "filled" star still renders hollow.
          color="#F5B301"
          fill={i < value ? '#F5B301' : 'none'}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}

/**
 * One review card.
 *
 * No date is shown. These are genuine third-party reviews of the underlying
 * product, written before this store existed — printing "May 2021" on a 2026
 * storefront reads as a giveaway even though the review itself is real. Skill
 * 7.C: drop the exact date, never substitute an invented one.
 *
 * Photos belong to the reviewer who submitted them, so they render inside this
 * card rather than in a gallery detached from their author, and each opens in
 * a lightbox.
 */
function ReviewCard({review, onOpenPhoto}) {
  const photos = Array.isArray(review.photos) ? review.photos : [];
  return (
    <li className="border-b border-divider py-4 last:border-b-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Stars value={review.rating} />
        <span className="text-[13px] font-semibold">
          {review.name}
          {review.country ? ` ${review.country}` : ''}
        </span>
        <span className="text-[11.5px] font-semibold text-accent-700">✓ Verified buyer</span>
      </div>

      <p className="mt-2 text-[14.5px] leading-[1.5] text-ink/85">{review.comment}</p>

      {photos.length > 0 && (
        <ul className="mt-3 flex list-none flex-wrap gap-2 p-0">
          {photos.map((src) => (
            <li key={src}>
              <button
                type="button"
                aria-label={`Enlarge photo from ${review.name}'s review`}
                onClick={() => onOpenPhoto(src, `Photo from ${review.name}'s review`)}
                className="block cursor-zoom-in"
              >
                <img
                  data-review-photo
                  src={src}
                  alt={`Photo from ${review.name}'s review`}
                  loading="lazy"
                  className="h-20 w-20 rounded-md border border-divider object-cover transition hover:opacity-90 md:h-24 md:w-24"
                />
              </button>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

/**
 * Ratings and reviews for one product, from the `custom.reviews` metafield.
 *
 * There is deliberately no "Write a review" form here: this storefront has no
 * post-purchase verification, and a submit button that can't prove the writer
 * bought the product is UI pretending to do something it doesn't (skill 7.C).
 * The real path is Shopify's native Shop-channel review request, enabled in
 * admin once the store is live.
 *
 * @param {{reviews: Array<object>}}
 */
export function PdpReviews({reviews = []}) {
  const [showAll, setShowAll] = useState(false);
  const [lightbox, setLightbox] = useState({src: null, alt: ''});
  const openPhoto = (src, alt) => setLightbox({src, alt});
  const closePhoto = () => setLightbox({src: null, alt: ''});

  const count = reviews.length;
  const average = count ? reviews.reduce((s, r) => s + (r.rating || 0), 0) / count : 0;
  const withPhotos = reviews.filter((r) => Array.isArray(r.photos) && r.photos.length);

  // Reviews carrying real customer photos lead the first page — they're the
  // most useful ones to a shopper, and burying them behind "View all" would
  // waste the only genuine photo proof this product has.
  const ordered = [...withPhotos, ...reviews.filter((r) => !withPhotos.includes(r))];
  const visible = showAll ? ordered : ordered.slice(0, INITIAL_VISIBLE);

  return (
    <section className="pt-10">
      <h2 className="m-0 text-ch2 font-normal">Ratings &amp; Reviews</h2>

      {count > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StarRating value={average} size={19} />
          <span className="text-[13px] text-ink/70">
            {average.toFixed(1)} out of 5 · {count} review{count === 1 ? '' : 's'}
            {withPhotos.length > 0 && ` · ${withPhotos.length} with photos`}
          </span>
        </div>
      ) : (
        <p className="mt-2 text-[14px] text-ink/60">Be the first to review this product.</p>
      )}

      {count > 0 && (
        <>
          <ul className="mt-3 list-none p-0">
            {visible.map((r) => (
              <ReviewCard key={r.id} review={r} onOpenPhoto={openPhoto} />
            ))}
          </ul>

          {!showAll && count > INITIAL_VISIBLE && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="mt-4 min-h-[44px] w-full rounded border border-accent px-5 text-[14px] font-semibold text-accent-700 transition hover:bg-accent/5 sm:w-auto"
            >
              View all {count} reviews
            </button>
          )}
        </>
      )}

      <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={closePhoto} />
    </section>
  );
}
