import {useRef, useState} from 'react';
import {Link} from 'react-router';
import {Image, Money} from '@shopify/hydrogen';
import {RotateCw} from 'lucide-react';
import {useVariantUrl} from '~/lib/variants';

/**
 * A product card in the ALPHA FOR BABY design (.tob-card, 3:4 image, hover zoom).
 * @param {{
 *   product:
 *     | CollectionItemFragment
 *     | ProductItemFragment
 *     | RecommendedProductFragment;
 *   loading?: 'eager' | 'lazy';
 * }}
 */
export function ProductItem({product, loading}) {
  const variantUrl = useVariantUrl(product.handle);
  // Reel's generated lifestyle photo is always uploaded to gallery position 1
  // (position 0 stays the supplier's own photo, tied to color selection — see
  // src/mcp_tools/shopify.py's attach_local_image_to_product). Prefer it here.
  const galleryImages = product.images?.nodes ?? [];
  const image = galleryImages[1] || product.featuredImage;
  const available = product.availableForSale ?? true;
  const videoSource = (product.media?.nodes ?? [])
    .flatMap((n) => n.sources ?? []).find((s) => s.mimeType === 'video/mp4');
  const [playingVideo, setPlayingVideo] = useState(false);
  const loopCountRef = useRef(0);

  return (
    <Link className="tob-card" key={product.id} prefetch="intent" to={variantUrl}>
      <div className="tob-imgwrap relative">
        {image && (
          <Image
            alt={image.altText || product.title}
            aspectRatio="3/4"
            data={image}
            loading={loading}
            sizes="(min-width: 820px) 300px, 45vw"
          />
        )}
        {videoSource && playingVideo && (
          <video
            src={videoSource.url}
            autoPlay
            muted
            playsInline
            className="absolute inset-0 h-full w-full object-cover"
            onEnded={(e) => {
              loopCountRef.current += 1;
              if (loopCountRef.current >= 2) {
                e.currentTarget.pause();
                setPlayingVideo(false);
              } else {
                e.currentTarget.play();
              }
            }}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setPlayingVideo(false);
            }}
          />
        )}
        {videoSource && (
          <button
            type="button"
            aria-label={playingVideo ? 'Show photo' : 'Play 360° video'}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              loopCountRef.current = 0;
              setPlayingVideo((v) => !v);
            }}
            className="absolute bottom-2 right-2 z-10 flex items-center gap-1 rounded-full bg-white/90 px-2 py-1 text-[11px] font-semibold shadow"
          >
            <RotateCw size={12} />
            360°
          </button>
        )}
      </div>
      <h3>{product.title}</h3>
      <div className="tob-price">
        <Money data={product.priceRange.minVariantPrice} />
        {!available && <span className="tob-soldout">Sold out</span>}
      </div>
    </Link>
  );
}

/** @typedef {import('storefrontapi.generated').ProductItemFragment} ProductItemFragment */
/** @typedef {import('storefrontapi.generated').CollectionItemFragment} CollectionItemFragment */
/** @typedef {import('storefrontapi.generated').RecommendedProductFragment} RecommendedProductFragment */
