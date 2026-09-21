/**
 * "How to use" — numbered usage steps, each with its own small real product
 * photo, sitting next to the demo video (skill changelog's HowToUseSection
 * pattern). Placed mid-page after the benefits, not buried in the gallery.
 *
 * Step photos are real supplier images referenced by index into the product's
 * own gallery. They are illustrative product photography for this carrier —
 * the alt text deliberately does not claim a given photo demonstrates that
 * specific carry mode, because this listing's images are colourway variants of
 * one composite rather than per-mode demonstration shots.
 *
 * @param {{
 *   content: {heading?: string, intro?: string, steps?: Array<{n:number,title:string,text:string,imageIndex?:number}>},
 *   images: Array<{url: string, altText?: string|null}>,
 *   video?: {url: string, mimeType: string}|null,
 *   title: string,
 * }}
 */
export function PdpHowToUse({content, images = [], video = null, title}) {
  const steps = content?.steps || [];
  if (!steps.length) return null;

  return (
    <section className="pt-10" data-how-to-use>
      <h2 className="m-0 text-ch2 font-normal">{content.heading || 'How to use it'}</h2>
      {content.intro && <p className="mt-2 max-w-2xl text-[14.5px] text-ink/70">{content.intro}</p>}

      <div className="mt-5 grid gap-6 md:grid-cols-2 md:items-start">
        {video && (
          <div className="md:sticky md:top-24">
            {/* eslint-disable-next-line jsx-a11y/media-has-caption -- supplier demo clip ships without a caption track */}
            <video
              className="w-full rounded-lg bg-black"
              src={video.url}
              autoPlay
              muted
              loop
              playsInline
              preload="auto"
              onClick={(e) => e.preventDefault()}
              style={{pointerEvents: 'none'}}
            />
            {/* Caption stays product-facing: naming the clip's origin
                ("supplier demo") tells a shopper the store is reselling —
                7.D bug #6 covers the supply chain, not just the word "CJ". */}
            <p className="mt-2 text-[12px] text-ink/50">See it in use</p>
          </div>
        )}

        <ol className="m-0 list-none p-0">
          {steps.map((step) => {
            const img = images[step.imageIndex ?? -1];
            return (
              <li key={step.n} className="flex gap-4 border-b border-divider py-4 last:border-b-0">
                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-accent/10 text-[14px] font-semibold text-accent-700">
                  {step.n}
                </span>
                {img && (
                  <img
                    src={img.url}
                    alt={`${title} — colourway shown for step ${step.n}`}
                    loading="lazy"
                    className="h-20 w-20 flex-none rounded-md border border-divider object-cover"
                  />
                )}
                <div className="min-w-0">
                  <h3 className="m-0 text-[15px] font-semibold">{step.title}</h3>
                  <p className="mt-1 text-[14px] leading-[1.5] text-ink/75">{step.text}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
