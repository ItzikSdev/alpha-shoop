<!-- Level 9 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 7.A, 7.B, 7.C, 7.E. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 7. ASSET GENERATION

## 7.A — Images (real supplier photos first, generate only to fill gaps)

If you sourced via Section 2, start from the CJ listing's real
`productImageSet` — that is always your primary gallery. Use the shot
list below to (a) identify which of the real CJ photos already cover
each shot type, and (b) generate AI images ONLY for shot types the real
set is missing. If you're in Mode A with no supplier photos at all,
generate every shot below.

For each generated shot, fill the template with the specific product
from the brief. Use whatever image model is available locally or via
API (Flux, SDXL, Midjourney, Nano Banana/Gemini image, DALL·E — pick
whichever is configured); the prompt content matters more than the tool.

1. **Studio hero shot** — `Professional e-commerce product photography of
   [product], centered on a clean seamless [white/bold-accent-tinted]
   background, crisp studio lighting, no harsh shadows, high resolution,
   photorealistic, subtle drop shadow, square 1:1 crop, catalog-ready.`
2. **Lifestyle in-use shot (x2-3)** — `Photorealistic lifestyle photo of
   [target customer, e.g. "a smiling toddler" / "a young mother"] using
   [product] in [natural real-world setting matching the product, e.g. a
   sunlit nursery / a cozy living room], warm natural light, candid
   unposed feel, shallow depth of field, emotionally warm, energetic
   framing, no visible competing brand logos.`
3. **Macro/detail shot** — `Extreme close-up macro photo of [product]
   showing [specific texture/material/stitching/mechanism detail],
   sharp focus, soft directional light, emphasizing quality and
   craftsmanship.`
4. **Variant/color array shot** — `Flat-lay or grid product photo showing
   all [N] color/style variants of [product] laid out neatly side by
   side on a [neutral background], evenly lit, consistent angle for
   each, e-commerce catalog style.`
5. **Scale/size reference shot** — `Product photo of [product] next to a
   common reference object appropriate to its category (e.g. a hand, a
   standard object) to clearly communicate real-world size, clean
   background, simple annotation-ready composition.`
6. **Infographic base shot** (for benefit-bullet section) — `Clean
   product photo of [product] on a soft-colored background with open
   negative space around it, suitable for adding icon callouts and short
   text labels in post-production.`
7. **"Why it works" mechanism shot** — `Simple, clear photo or cutaway-
   style image of [product] illustrating [the specific mechanism that
   creates the benefit], instructional but still attractive, soft
   background.`

Consistency rule: lock one lighting style, one background tone, and one
color grade across all shots for a single product — mismatched lighting
between real CJ photos and AI-generated fill-ins is the single biggest
"looks cheap/scammy" signal on dropshipping pages, so grade/tone-match
generated shots to the real ones, not the other way around.

### 7.A.1 — Product images and the hero image (v2.2, Itzik's rule)

**v2.2 correction.** v2.1 of this section wrongly let customer review
photos compete for the hero spot, and all three live products ended up
with a review photo as their hero. That was not Itzik's intent and it
is now forbidden: **product images — the gallery and the hero — come
only from the images that ship with the product's own CJ listing.**
Review photos belong in the reviews section and nowhere else (not the
gallery, not the hero, not the homepage card, not link previews).

**Two stages, in this order:**

**Stage 1 — every CJ image is checked BEFORE it is uploaded.** Take
every image on the product's CJ listing (main image, gallery, variant
images). Each one must pass both hard checks; an image that fails is
not uploaded to Shopify at all — not "uploaded and moved to the back."

1. **Not pixelated.** Short side ≥ 1000px on the original file;
   Laplacian variance ≥ 100 (grayscale, resized to 1024px on the long
   side); reject upscaled thumbnails (< 0.5 bytes/pixel as JPEG).
2. **No Chinese text.** Zero characters matching
   `[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002a6df]` in
   the OCR text — packaging, stickers, labels, watermarks, overlays.

**Stage 2 — choose the hero from the images that passed Stage 1.**

3. **Prefer a photo of someone using the product** (a parent wearing
   the carrier, a child playing with the toy). Tie-break by higher
   Laplacian variance, then larger short side.

If fewer images pass Stage 1 than the page needs, report it — don't
lower the bar, don't blur or crop the Chinese text out and call it
clean, and never fill the gap with review photos. If NO CJ image
passes, the product has no usable imagery: report it to Itzik before
building.

**Tooling — [markitdown](https://github.com/microsoft/markitdown) with
OCR.** For an image, markitdown returns EXIF metadata plus, with an LLM
client, a vision-model description. The prompt is ours, so one call does
both the OCR (transcribe every visible character) and the "person using
it" judgement:

```bash
pip install 'markitdown[all]' openai pillow opencv-python-headless
```

```python
import json, re
from markitdown import MarkItDown
from openai import OpenAI

# Any OpenAI-compatible client with a VISION model. The repo's LiteLLM
# proxy (litellm_config.yaml) works; qwen3-14B is text-only and cannot
# read images — route this call to a vision-capable model.
client = OpenAI(base_url=LITELLM_URL, api_key=LITELLM_KEY)

IMAGE_PROMPT = (
    "You are auditing a product photo for an online baby store. "
    "Reply with JSON only: "
    '{"ocr_text": "<every visible character, verbatim, any language>", '
    '"person_using_product": true|false, '
    '"what_is_shown": "<one short sentence>"}'
)

md = MarkItDown(llm_client=client, llm_model=VISION_MODEL,
                llm_prompt=IMAGE_PROMPT)
result = md.convert(path)            # result.markdown = EXIF + description
data = json.loads(re.search(r"\{.*\}", result.markdown, re.S).group(0))
```

Note: the separate `markitdown-ocr` plugin adds OCR to PDF, DOCX, PPTX
and XLSX — not to standalone photos — so for product images the OCR is
this vision-model transcription.

**Apply it:** upload only the Stage-1 passes, make the Stage-2 choice
position 1 in the product's media, and save the decision to
`store-profiles/alphaforbaby/hero-selection/<handle>.json`:

```json
{
  "handle": "ergonomic-baby-hip-carrier",
  "cj_listing_url": "https://cjdropshipping.com/product/...",
  "chosen": {"url": "https://cdn.shopify.com/...", "source": "cj",
             "cj_source_url": "https://cf.cjdropshipping.com/...",
             "short_side": 1600, "laplacian_var": 312.4, "cjk_chars": 0,
             "person_using_product": true},
  "uploaded": [{"url": "...", "source": "cj", "short_side": 1200,
                "laplacian_var": 180.2, "cjk_chars": 0}],
  "rejected": [{"cj_source_url": "...", "reason": "cjk_text: 3 chars on the box"}],
  "model": "<vision model used>", "checked_at": "2026-09-21"
}
```

Every entry in `chosen` and `uploaded` must have `"source": "cj"`.
Level 14's `TestHeroImage` enforces this and checks the rendered page
against the record.

## 7.B — Video (two separate slots: hero background is mandatory; product-demo video prefers the real thing)

**Slot 1 — hero background video (mandatory, generate if no real option exists).**
Confirmed directly on beelyra.com (2026-09-06): one full-bleed, muted,
autoplay, looping cinematic video plays behind the hero headline itself
(not a separate gallery item) — mood/lifestyle footage of the problem
being solved (a mother carrying a sleeping baby), with the headline text
("Transfer your baby without waking them") overlaid directly on the
video. This is the concrete pattern behind "use more video in the
background, it's more sellable," and every build now requires one —
this is NOT conditional on whether real CJ/ad video exists, because it
is a different kind of asset (mood/narrative, not a product close-up):
1. Generate via whatever text-to-video/image-to-video tool is
   available (Veo, Kling, Runway, Luma), 6-10 seconds, seamless loop,
   muted (never depend on audio — autoplay-with-sound is blocked by
   browsers anyway).
2. Prompt shape: `Cinematic, warm, natural-light shot of [target
   customer] experiencing [the exact pain point the product solves],
   then [product or its effect] visibly present, resolving it — gentle
   camera movement, no text, no logos, loopable, shot on film-like
   color grade.` This is the "problem → solution" narrative Itzik asked
   for — show the pain, then the resolution, in one continuous clip.
3. Overlay the H1/subheadline/CTA directly on the video with a
   gradient scrim behind the text (same fix as the 7.D.3 bug — never a
   flat fixed-opacity wash), same as beelyra's layout.
4. Go through this codebase's existing video-generation cost-approval
   gate before calling a paid video model, same as any other generated
   clip (see Slot 2 below) — being mandatory does not mean skipping an
   existing safety gate to get it.
If genuinely no video-generation tool is available in this build
environment, ship a high-quality static hero image instead and state
the gap plainly — don't silently skip the requirement without saying so.

**Slot 2 — product-demonstration video (in the image gallery).**
Priority order for the gallery's first/second video slot:
1. A Section 2.C ad-trend video (`ad_trend_data.ad_video_url`), if this
   was a Mode B2 hand-off — proven creative with real performance numbers
   behind it, the strongest option available. This is what actually shows
   the product solving a real problem in use, which is the real reason
   video converts — prefer this over any other option whenever a hand-off
   is available.
2. A real CJ `productVideo`, either from a Section 2.D Top Selling
   hand-off (where a meaningful fraction of listings genuinely have one —
   check the specific pid's detail response) or, much more rarely, from
   Mode B keyword search (confirmed empirically null on 294/294 sampled
   candidates there — see 2.A.2, don't expect this tier from a keyword
   sweep specifically).
3. Generated video (below) — a genuine fallback for when neither real
   option is available (typically: a Mode B keyword-search build, no
   hand-off possible), not a step to run by default. **Do not generate
   video automatically right now** — real video via 2.C/2.D is the
   priority; only reach for generation when asked to, or when a real
   option has genuinely been ruled out for this specific build.

**Where this actually lives in code (added v1.14, don't skip this
check):** `react-store-template`'s `ProductConfig.productVideo: { src,
poster, alt? }` (`src/config/types.ts`) is the slot — `Gallery.tsx`
renders it as slide 0 of the main gallery, before any images, with an
accent-colored ▶ badge on its thumbnail. `App.tsx` passes it through as
`<Gallery video={product.productVideo} .../>`. **v1.33 correction: no
`controls` attribute, and no way to pause/stop it by tapping** — Itzik
was explicit: it autoplays and the shopper cannot interact with it
(no native scrubber/play-pause UI, and don't let a tap on the video
element itself toggle playback the way a custom player sometimes
does — either omit a click handler on it entirely or explicitly
`preventDefault`/ignore taps on that element; the surrounding gallery's
normal prev/next navigation to move PAST the video slide is still
fine, that's not the same as controls on the video itself). Element is
`<video autoPlay muted loop playsInline>` with no `controls` attribute.
Whichever source wins from the priority list above, it still has to
land in this field — a video that only exists in your notes or in
`store_brief.json` and never makes it into `productVideo` renders
nothing, which is exactly the bug v1.14 fixed (the field didn't exist
in the template at all before that; if
you're working from a template snapshot older than v1.14, add it
before assuming the gallery already supports video).

If you do generate a 360° spin, note that this codebase's Veo integration
(`src/video/veo_video.py`, Veo 3.1 Fast, roughly $0.10/second of output)
exists for exactly that, and its own code comments require going through
whatever owner cost-approval gate the tooling defines
(`src/api/routes/videos.py`) before it is ever called — surface the cost
and get approval the same way the tooling already requires, every time.

Whichever real video you have, still generate the following as
supplements, not replacements, when you do have video-generation tooling
available and it's been asked for:

1. **360° product spin** (reuse the exact pattern already proven on
   alphaforbaby: a slow, smooth full rotation of the studio hero shot,
   3-6 seconds, looping, clean background) — via an image-to-video tool
   (Kling, Runway, Luma, Pika) fed the studio hero shot.
   Prompt: `Smooth continuous 360-degree rotation of the product, studio
   lighting held constant, no camera shake, clean loop, 4-6 seconds.`
2. **In-use motion clip** (6-10 seconds): `Short cinematic clip of
   [target customer] naturally using [product] in [same setting as the
   lifestyle photo], gentle camera movement, warm lighting, no text
   overlay, loopable.` Feed the lifestyle image as the starting frame.
3. **UGC-style talking clip (optional, if a talking-avatar tool like
   MakeUGC/HeyGen is available)**: a 15-30 second scripted clip of an
   avatar describing the ONE core benefit and the guarantee, ending on
   the CTA. Script formula: `Hook (pain point, 1 sentence) → I found
   this (product name) → it does X (core benefit) → here's the proof
   (one concrete detail) → guarantee line → "link in bio/below."`
   Always disclose or keep neutral — do not have the avatar claim to be
   a real verified customer (see Section 1, Rule 1); frame it as the
   brand's own presenter/founder voice, not a testimonial.

**A live store should not ship with zero video in either slot.** For
Slot 1 (hero background) generation is expected by default (above) —
that one doesn't wait for a real supplier asset because no CJ/ad video
is ever mood/narrative footage anyway. For Slot 2 (product demo), the
fix is getting real video via 2.C/2.D, not defaulting to generation —
Mode B keyword search alone essentially never surfaces real video
(294/294 null, see 2.A.2), which is exactly why Section 2's intro tells
you to prefer a 2.C or 2.D hand-off before falling back to keyword
search at all. If you do end up on a Mode B build with no real Slot 2
video and generation hasn't been asked for, state that plainly as a gap
in your output (with the recommendation: get a 2.C/2.D hand-off, or
approve generation) rather than silently shipping without it AND
without generating one unprompted.

## 7.C — Trust, urgency, and review components

Build these as designed, functional components, then populate per
Section 1's honesty rules:
- **Star rating widget**: reusable component (stars + numeric average +
  review count). CJ sourcing never supplies this (Section 2.A.3) — shows
  0 honestly until a real review app is wired up, or a "New Arrival"
  badge instead of a fake rating.
- **Review pipeline (v1.30 — REVISED default, supersedes the v1.x
  metafield-first order below)**: Itzik installed the free **AG Product
  Reviews** app (Shopify Admin → Apps) and confirmed, end-to-end, on the
  real live store, that CJ's own documented **Method 2** import works:
  app sidebar → Collect reviews → Import → paste the sourced product's
  real CJ listing review-page URL → Import — result on the real carrier
  product: "Import successfully! 20 of 20 reviews are imported into
  your store," each one tagged "CJ Dropshipping" as its source in the
  app's Manage reviews table. This is now the **required default
  pipeline for every product**, ahead of the old manual-extraction
  route:
  1. **AG Product Reviews app, Method 2 URL import (v1.30 default)** —
     for each sourced product, get its real CJ listing's review-page URL
     (Section 2.A.3/2.D already establish where a pid's reviews live)
     and run the Import flow above. Free, zero added ongoing cost (the
     app itself is free — this satisfies Itzik's standing "no added
     cost" constraint below), and it's the actual mechanism CJ documents
     for its own dropshippers (cjdropshipping.com/article-details/108),
     not a workaround. This is Method 2 specifically — CSV-based Method
     1 (export CJ reviews to CSV, edit, re-import) is a fallback only
     when Method 2's direct-URL import fails for a given pid.
  2. **Manual extraction from the pid's own "Buyer Review" tab into a
     Shopify metafield** (the pre-v1.30 default) — demote to a fallback,
     used only when (1) genuinely doesn't work for a specific pid (the
     app's importer can't parse that listing's review page, or the CJ
     page has zero reviews but you can see real reviews elsewhere for
     the same underlying product). When you do fall back to this, the
     mechanism is unchanged from before: read the pid's own Buyer Review
     tab (2.D step 4) and write the extracted reviews onto the product
     as a `custom.reviews` metafield.
  3. **A paid review-import app** (Ali Reviews, Judge.me, Loox, etc.) —
     only when both (1) and (2) genuinely found nothing AND Itzik has
     explicitly said this specific build may use a paid app. Never
     default to this silently; his standing answer is no added cost, so
     treat every occurrence as a fresh yes/no to ask, not a settled
     default.
  4. **Honest empty state** when none of the above applies.
  **Retire the hand-rolled display components** (`ReviewsSection.tsx`,
  `MiniReviewCarousel.tsx` or equivalents) in favor of whatever the AG
  Product Reviews app itself renders, per product — that's the whole
  point of moving to a real app instead of a bespoke component.
  **Open technical question, must be actually answered, not assumed
  (v1.30):** this storefront is a headless Hydrogen build, and AG
  Product Reviews is a normal Shopify (Liquid-theme-era) app. Before
  claiming reviews are "properly displayed," confirm — by actually
  checking the app's own docs/settings, or by inspecting what data it
  actually exposes (a Shopify **metafield** it writes reviews into that
  the Storefront API can read, a public read API/widget script it
  offers, or a Liquid-only `{% section %}`/App Block with no data path
  a headless frontend can reach at all) — which of these is true. If
  it's Liquid-theme-only with no metafield/API a Hydrogen page can
  query, that is a real integration gap, not a solved problem — report
  it explicitly rather than quietly re-building the retired custom
  components with the app's data hand-copied in once (that would be the
  old bespoke-component problem again, just re-populated from a
  different source, and it stops being "the app's data" the moment
  someone edits a review in the app and the storefront doesn't update).
  A working embed/App Block on the *Liquid* storefront proves nothing
  about the *Hydrogen* storefront being able to reach the same data —
  verify on this codebase specifically.
- **Review card component, additional requirements (v1.23)**: if the
  real review's date predates the store's own launch (common — these are
  genuine third-party reviews of the underlying product, sourced before
  this store existed), do not display the exact date; show star/name/
  flag/quote/photo only. Do not invent a substitute date. Any photo on a
  review card must open in a click-to-enlarge lightbox (modal, closable
  via X / click-outside / Escape, body scroll locked while open) — this
  is a standard interaction, not a one-off. Do not render a "Write a
  review" form unless it actually persists somewhere real (e.g. a wired
  metafield write) — a form with no backend behind it is dishonest UI;
  omit it entirely rather than ship a dead submit button. (These
  requirements apply to whichever component actually renders reviews —
  the app's own UI if v1.30's pipeline reaches the storefront directly,
  or a thin wrapper around app-sourced data if it doesn't.)
- **Countdown/urgency component**: takes a real ISO datetime or a real
  stock-count field as input; if neither is supplied by the brief, this
  component is not rendered at all — do not fabricate a value for it.
- **Guarantee badge set**: Secure Payment / [N]-Day Guarantee / Free or
  Insured Shipping — these three are safe to state universally as long
  as the store's actual policies match them.


## 7.E — 24/7 support widget (Nora)

Every build needs a persistent support entry point: a small floating
chat bubble, bottom-right corner (bottom-left on an RTL layout),
present on every page, `--color-accent`-filled, that opens into a
compact panel introducing **Nora** as the store's support presence —
name, a friendly avatar/icon (illustrated, not a real person's photo —
Nora is a support persona, not a claimed real employee, keep this
honest per Rule 1), and a **"24/7 Support"** badge. The panel's actual
function is a simple contact form or a `mailto:` link to Nora's support
inbox. **v1.30 — the real inbox is now on file, use it:**
`support@alphaforbaby.com`. This replaces every earlier
`support@[storedomain]` placeholder in this codebase — grep the whole
frontend for the placeholder string and any other fabricated support
address and replace every occurrence, not just the one in the widget
component (check for a duplicate in a footer contact link, an FAQ
answer, or a policy page too). For any *other* store built from this
skill where Itzik hasn't yet given a real address, the placeholder rule
is unchanged: do not invent that email address, ask him for the real
one, and use the clearly-marked `support@[storedomain]` placeholder
(stating in your output that it's a placeholder) until he provides it
— alphaforbaby.com specifically is simply no longer in that state.
Keep the panel's copy
short and human ("Hi, I'm Nora — happy to help! Message me and I'll get
back to you." + an email field or the mailto link) — this is a trust
signal (someone's there if something goes wrong), not a scripted bot
flow, so don't over-build it with fake canned responses pretending to
be a live conversation.
