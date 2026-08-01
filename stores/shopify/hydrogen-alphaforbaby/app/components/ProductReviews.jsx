import {useEffect, useRef, useState} from 'react';
import {useFetcher} from 'react-router';
import {Rating, Input, Textarea, Button, Typography} from '@material-tailwind/react';

/** Parses the product's `custom.reviews` JSON metafield into a safe array,
 * newest first. Never throws — a missing/malformed metafield just means no
 * reviews yet (this is the same "best-effort JSON metafield" pattern the
 * size guide uses). */
export function parseReviews(metafieldValue) {
  if (!metafieldValue) return [];
  try {
    const parsed = JSON.parse(metafieldValue);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function average(reviews) {
  if (!reviews.length) return 0;
  return reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length;
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-US', {year: 'numeric', month: 'short', day: 'numeric'});
  } catch {
    return '';
  }
}

/** Rating-with-comment section for a single product page — a Material Tailwind
 * `Rating` component (star display/input, https://www.material-tailwind.com/docs/html/rating)
 * used both to show existing reviews and to collect new ones. Every product page
 * renders its own instance, keyed by `productId`, so reviews never bleed across
 * products. Submissions POST to this route's own `action`, which writes to the
 * product's `custom.reviews` Shopify metafield (see products.$handle.jsx). */
export function ProductReviews({productId, reviews}) {
  const fetcher = useFetcher();
  const formRef = useRef(null);
  const [ratingInput, setRatingInput] = useState(5);

  const submitting = fetcher.state !== 'idle';
  const result = fetcher.data;

  useEffect(() => {
    if (result?.ok) {
      formRef.current?.reset();
      setRatingInput(5);
    }
  }, [result]);

  const avg = average(reviews);

  return (
    <div className="product-reviews">
      <div className="product-reviews-summary">
        <h2 className="product-reviews-heading">Ratings &amp; Reviews</h2>
        {reviews.length > 0 ? (
          <div className="product-reviews-summary-row">
            <Rating value={Math.round(avg)} readonly />
            <span className="product-reviews-summary-text">
              {avg.toFixed(1)} out of 5 &middot; {reviews.length} review{reviews.length === 1 ? '' : 's'}
            </span>
          </div>
        ) : (
          <p className="product-reviews-empty">Be the first to review this product.</p>
        )}
      </div>

      {reviews.length > 0 && (
        <ul className="product-reviews-list">
          {reviews.map((r) => (
            <li key={r.id} className="review-card">
              <Rating value={r.rating} readonly />
              <Typography className="review-card-comment">&ldquo;{r.comment}&rdquo;</Typography>
              <div className="review-card-meta">
                <span className="review-card-name">{r.name}</span>
                {r.createdAt && <span className="review-card-date">{formatDate(r.createdAt)}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}

      <fetcher.Form method="post" ref={formRef} className="review-form">
        <h3 className="review-form-heading">Write a review</h3>

        <div className="review-form-rating">
          <span className="review-form-rating-label">Your rating</span>
          <Rating value={ratingInput} onChange={setRatingInput} />
        </div>
        <input type="hidden" name="rating" value={ratingInput} />
        <input type="hidden" name="productId" value={productId} />
        {/* Honeypot — hidden from real customers, bots fill every field. */}
        <input
          type="text"
          name="website"
          tabIndex={-1}
          autoComplete="off"
          className="review-form-honeypot"
          aria-hidden="true"
        />

        <div className="review-form-row">
          <Input label="Your name" name="name" required maxLength={80} />
        </div>
        <div className="review-form-row">
          <Textarea label="Your review" name="comment" required maxLength={1000} />
        </div>

        {result?.error && <p className="review-form-error">{result.error}</p>}
        {result?.ok && <p className="review-form-success">Thanks — your review was posted!</p>}

        <Button type="submit" disabled={submitting} className="review-form-submit">
          {submitting ? 'Submitting…' : 'Submit review'}
        </Button>
      </fetcher.Form>
    </div>
  );
}
