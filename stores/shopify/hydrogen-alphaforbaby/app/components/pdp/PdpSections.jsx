import {Link} from 'react-router';
import {Money} from '@shopify/hydrogen';
import {Baby, Repeat, Shield, Umbrella, Zap, Check, X, ShieldCheck} from 'lucide-react';
import {AddToCartButton} from '~/components/AddToCartButton';

const ICONS = {baby: Baby, repeat: Repeat, shield: Shield, umbrella: Umbrella, zap: Zap};

/** Section 5.4 — 3-5 benefit bullets: icon + bold micro-headline + one sentence. */
export function PdpBenefits({items = []}) {
  if (!items.length) return null;
  return (
    <section className="pt-10" data-benefits>
      <h2 className="m-0 text-ch2 font-normal">Why parents choose it</h2>
      <ul className="mt-4 grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2">
        {items.map((b) => {
          const Icon = ICONS[b.icon] || Check;
          return (
            <li key={b.title} className="flex gap-3">
              <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-accent/10">
                <Icon size={18} className="text-accent" />
              </span>
              <div>
                <h3 className="m-0 text-[15px] font-semibold">{b.title}</h3>
                <p className="mt-0.5 text-[14px] leading-[1.5] text-ink/75">{b.text}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Section 5.5 — mechanism: HOW it delivers the benefit, not just that it does. */
export function PdpWhyItWorks({content}) {
  if (!content?.text) return null;
  return (
    <section className="pt-10" data-why-it-works>
      <h2 className="m-0 text-ch2 font-normal">{content.heading || 'Why it works'}</h2>
      <p className="mt-2 max-w-3xl text-[15px] leading-[1.6] text-ink/80">{content.text}</p>
      {content.points?.length > 0 && (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {content.points.map((p) => (
            <div key={p.title} className="rounded-lg border border-divider p-4">
              <h3 className="m-0 text-[14px] font-semibold">{p.title}</h3>
              <p className="mt-1 text-[13.5px] leading-[1.5] text-ink/70">{p.text}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** Section 5.6 — lifestyle / in-context image with a short supporting headline. */
export function PdpLifestyle({content, images = [], title}) {
  const img = images[content?.imageIndex ?? -1];
  if (!img) return null;
  return (
    <section className="pt-10" data-lifestyle>
      <div className="relative overflow-hidden rounded-xl border border-divider">
        <img src={img.url} alt={title} loading="lazy" className="h-auto w-full object-cover" />
        {content.headline && (
          <div className="bg-gradient-to-t from-black/70 to-transparent p-5 text-white [margin-top:-6rem] relative">
            <p className="m-0 max-w-xl text-[18px] font-semibold leading-snug">{content.headline}</p>
            {content.text && <p className="mt-1 text-[14px] text-white/85">{content.text}</p>}
          </div>
        )}
      </div>
    </section>
  );
}

/** Section 5.7 — "Without X / With X" two-column comparison. */
export function PdpComparison({content}) {
  if (!content?.with || !content?.without) return null;
  const Col = ({data, good}) => (
    <div className={`rounded-lg border p-5 ${good ? 'border-accent bg-accent/5' : 'border-divider'}`}>
      <h3 className="m-0 text-[15px] font-semibold">{data.title}</h3>
      <ul className="mt-3 list-none p-0">
        {data.items.map((t) => (
          <li key={t} className="flex items-start gap-2 py-1.5 text-[14px] text-ink/80">
            {good ? (
              <Check size={16} className="mt-0.5 flex-none text-accent" />
            ) : (
              <X size={16} className="mt-0.5 flex-none text-ink/35" />
            )}
            {t}
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <section className="pt-10" data-comparison>
      <h2 className="m-0 text-ch2 font-normal">{content.heading || 'Compare'}</h2>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Col data={content.without} good={false} />
        <Col data={content.with} good />
      </div>
    </section>
  );
}

/** Section 5.9 — risk reversal, its own visual weight right before the close. */
export function PdpGuarantee({content}) {
  if (!content?.text) return null;
  return (
    <section className="pt-10" data-guarantee>
      <div className="flex flex-col items-start gap-4 rounded-xl border border-divider bg-surface p-6 sm:flex-row sm:items-center">
        <span className="flex h-12 w-12 flex-none items-center justify-center rounded-full bg-accent/10">
          <ShieldCheck size={24} className="text-accent" />
        </span>
        <div>
          <h2 className="m-0 text-[18px] font-semibold">{content.heading || 'Our guarantee'}</h2>
          <p className="mt-1 text-[14.5px] leading-[1.55] text-ink/75">{content.text}</p>
        </div>
      </div>
    </section>
  );
}

/** Section 5.11 — image + price + button again, for anyone who scrolled past. */
export function PdpSecondaryCta({title, image, price, selectedVariant, inStock}) {
  return (
    <section className="pt-10" data-secondary-cta>
      <div className="flex flex-col items-center gap-5 rounded-xl border border-divider p-6 sm:flex-row">
        {image && (
          <img src={image.url} alt={title} loading="lazy" className="h-28 w-28 flex-none rounded-lg object-cover" />
        )}
        <div className="min-w-0 flex-1 text-center sm:text-left">
          <h2 className="m-0 text-[18px] font-semibold">{title}</h2>
          <div className="tnum mt-1 text-[20px]">{price ? <Money data={price} /> : null}</div>
        </div>
        <AddToCartButton
          disabled={!inStock}
          redirectTo="/cart"
          className="btn btn-primary min-h-[48px] w-full px-6 tracking-[.08em] sm:w-auto"
          lines={selectedVariant ? [{merchandiseId: selectedVariant.id, quantity: 1, selectedVariant}] : []}
        >
          {inStock ? 'ADD TO CART' : 'SOLD OUT'}
        </AddToCartButton>
      </div>
    </section>
  );
}
