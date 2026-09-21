<!-- Level 0 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->

# Changelog

Newest at the bottom. Every change to any level gets an entry here in the same edit, and the version in the main file is bumped.

v1.1 — added Section 2, CJ Dropshipping product sourcing, and required a
bold accent color (Section 8) instead of a muted default.
v1.2 — CORRECTED a false assumption from v1.1: CJ's actual REST API
(`src/mcp_tools/sourcing.py` — `product/list` / `product/query`) has NO
review/rating/comment field at all, and the public CJ website blocks
automated access behind a CAPTCHA (confirmed directly). "Pull real
reviews from the CJ listing" was never achievable with Sol's real
tooling — v1.1 told Sol/Opus to do something impossible, which is why a
sourced product (a sunrise wake-up light) shipped with zero reviews
despite the brief asking for "as many real reviews as possible." Fixed
in Section 1 Rule 1, Section 2.A.3, and Section 7.C: `trend_score`
(CJ `listingCount`) is the only real demand/social-proof signal CJ
sourcing can provide; real reviews now correctly route through a
legitimate post-launch app (Ali Reviews can import real AliExpress
reviews for the same/similar item) or an honest empty state — and any
criterion the current tools genuinely cannot check must be stated as a
gap in the output, never silently dropped.
v1.3 — added Section 2.C: sourcing from CJ's "Advertising Trends"
intelligence dashboard (cjdropshipping.com/intelligence/ad-trends),
confirmed by hand (logged-in browser session) to show real per-ad
metrics (views, days active, ad spend, estimated orders, country) plus
the actual ad video, and an AI "Similar Product Recommendations" bridge
into real sourceable CJ pids. This is a stronger validation + creative
signal than trend_score alone, and gives an inferable target
audience (category + country/region + what the ad itself shows) instead
of Sol having to guess one from nothing. IMPORTANT LIMITATION, stated
up front so this doesn't repeat the v1.1 mistake: this dashboard is a
logged-in web feature, not part of the CJ REST API `src/mcp_tools/
sourcing.py` already calls, and the public site is CAPTCHA-gated to
anonymous/automated fetches — confirmed directly. Until Sol has real
authenticated browser tooling for CJ, this path runs as a **human
hand-off** (Itzik picks the winning ad, gives Sol the pid + video +
stats), not a fully autonomous Sol search. See 2.C for exactly what to
do with a hand-off, and the note at the end of 2.C for what full
automation would additionally require.
v1.4 — Fixed against two things confirmed on a real Mode B build
(`react-furlo`, a CJ-sourced pet-grooming vacuum): (1) a 192-candidate,
15-keyword sweep had `productVideo: null` on every single listing — "no
video" was treated by v1.3 as a rare edge case, but it is a common
outcome for entire categories, so Section 7.B now makes the 360°
generated spin a REQUIRED hero video (not an optional supplement) any
time no real video exists anywhere in the candidate pool, and Section
2.A now tells you to check for a Mode B2 Ad-Trends alternative before
accepting a video-less winner. (2) CJ's keyword search itself returned
off-topic junk for on-topic queries ("neck massager" → women's dresses,
"led strip light" → trousers), which the build only caught because it
was checked by hand — Section 2.A now requires an explicit relevance
check against category/title before scoring any candidate, and states
plainly that this is a known limitation of `src/mcp_tools/sourcing.py`
itself, not something this skill can fix, only work around. Also added
Section 7.D, a running list of concrete template bugs found in real
builds (a star-rating widget that rendered even at zero reviews, a
brand-name string concatenated into itself, and a lifestyle-photo text
overlay that went illegible on some photos) — these recurred across
independently-forked store builds because a fix in one fork never
propagated to the others, so this list exists to be checked explicitly
on every build and appended to whenever a new one is found, rather than
re-discovering the same bug store after store.
v1.5 — v1.4 still hedged "no CJ video anywhere in the pool" as a common
but occasional outcome. A follow-up run proved that framing was still
too soft: on the SAME build, a deliberate control probe of 102 more
candidates across 10 unrelated categories (watch, humidifier, drone,
massage gun, electric toothbrush, vacuum cleaner, hair dryer, blender,
camera, speaker) found `productVideo: null` on every one — 294/294
candidates total across two runs, confirmed two independent ways (the
raw REST payload AND a separate CJ MCP `get_product_detail` call, same
null result). This is the same shape of mistake v1.2 already fixed once
for reviews: v1.1-through-v1.4 kept 2.A.2 and 7.B structured as if a
real CJ `productVideo` were a plausible, sometimes-true outcome worth
ranking candidates on — spending real effort (and, per the build's own
operator, real tokens) checking for something the evidence says
essentially never happens. Fixed: 2.A.2 no longer asks you to rank or
break ties on `productVideo` presence — it tells you to assume, from
the start of every Mode B sourcing pass, that no candidate will have
one, and to plan on Section 2.C (Ad-Trends hand-off) or a generated
360° spin as the DEFAULT path, not a fallback reached only after a
video search comes up empty. 7.B's priority order is reworded the same
way — CJ `productVideo` is now framed as a rare bonus if you ever
encounter it, not a real tier to plan sourcing around. Also added an
explicit note that generating video is a real paid call (Veo 3.1 Fast,
confirmed present and configured in this codebase at
`src/video/veo_video.py`, ~$0.40/render) that must go through whatever
owner cost-approval gate the tooling already requires
(`src/api/routes/videos.py`) — this skill expecting video by default
does not mean skipping an existing safety gate to get it.
v1.6 — Sharper resolution of the v1.5 finding, not a contradiction of
it: v1.5's 294/294-null result was specific to keyword-search-sourced
candidates (`search_trending_products`, which only calls `product/list`
with a keyword/categoryId + pagination — confirmed by reading
`src/mcp_tools/sourcing.py` directly, no sort/hot parameter is used at
all). Separately, CJ's own human-facing "Top Selling" catalog
(cjdropshipping.com/top-selling — Overall Most Listed, 90-Day Most
Listed New, and per-category Top N, confirmed by hand in a logged-in
browser) shows real products with `Lists` counts in the thousands to
tens of thousands (vs. the ~30-40 ceiling keyword search ever reaches)
and a large fraction visibly flagged "Video Gallery." So real CJ video
is NOT actually rare in general — it's rare specifically among what
blind keyword search surfaces, because keyword search never reaches
CJ's genuinely popular items at all. Confirmed this page requires an
authenticated session exactly like Section 2.C: an anonymous fetch
redirects through a CAPTCHA/login wall before reaching any content
(confirmed directly). Added Section 2.D for this second real hand-off
channel, parallel to 2.C. Also, per explicit direction: generating a
360° spin is NOT the default action right now — v1.5's "generate by
default" framing is walked back; 7.B now prioritizes getting the REAL
video via 2.C/2.D hand-offs, with generation only as a genuine
last-resort fallback, not a standing expectation. Net effect: a 2-3
minute human hand-off from 2.C or 2.D now clearly outperforms
autonomous Mode B keyword search on every axis that matters for this
build (trend signal, relevance, and video) for the same downstream
build effort — stated plainly in Section 2's intro so this is a real
recommendation, not a buried option.
v1.7 — Two corrections, both from directly verifying a real Top Selling
candidate (Lists:6747, "Video Gallery"-badged) against the actual
`product/query` REST response before handing it off, rather than
trusting the page. (1) v1.6 assumed the "Video Gallery" badge on
cjdropshipping.com/top-selling correlates with a real `productVideo` —
checked directly, it does not: this candidate's `productVideo` was
`null` and none of its 17 `productImageSet` entries were a video file
either, all `.jpg`. The badge just means "has a large image gallery."
2.A.2 and 2.D no longer claim this correlation; always check the
specific pid's actual `productVideo` field, never infer from a catalog
badge. (2) While checking that pid's page directly, found real,
populated "Buyer Review (5)" content — 5-star ratings, dates, written
text, and one review with 3 real customer photos, labeled "From
third-party," plus a native "Export Reviews" button for pushing them to
Shopify. This corrects Rule 1 and 2.A.3's prior claim that CJ has no
review data anywhere — that was true of the REST API (still is,
unchanged) but too broad as a claim about CJ overall: two earlier,
lower-`Lists` products genuinely showed zero, but this higher-demand
one showed five. Since this still isn't exposed via the REST API
either way, Mode B keyword search still can't detect or use it — but a
human doing a 2.C/2.D hand-off can see it on the page and should report
it, so 2.D step 4 now asks for that explicitly, and Rule 1/2.B/7.C
route real hand-off-reported reviews as a legitimate first-choice
source alongside app imports.
v1.8 — Corrected the operating assumption behind 2.C/2.D's "Automation
gap" notes and the ROLE section's Mode B2/B3 description, per Itzik's
explicit direction that Sol does not need his manual approval/hand-off
for routine actions: Sol runs as a full coding agent with real
computer/browser access ("open claw"), not a constrained tool-caller.
Verified directly before rewriting anything (not taken on faith):
`.claude/settings.json` shows Sol's own past permissions history
already includes ad-hoc browser-automation scripts (`node pw_test.mjs`,
`node nav4.mjs`) alongside broad Bash/curl access — real browser
automation tooling is available to Sol, contradicting v1.3-v1.7's
claim that it "does not exist in this codebase." So the prior framing
("Mode B2/B3 require a human hand-off because no automation tooling
exists") was wrong about the actual constraint. What IS verified and
still true: `.env` has `CJ_EMAIL` but no CJ password, cookie, or
session token anywhere in the repo (confirmed by grep for PASS/PWD/
COOKIE/TOKEN-suffixed keys) — so Sol has no stored authenticated CJ web
session yet, which is the one real gap blocking it from reaching
`/intelligence/ad-trends`, `/top-selling`, or a product's `Buyer
Review` tab (all logged-in-only pages). That's a one-time credential/
session-provisioning need, not a standing per-product hand-off
requirement. Also worth noting: the CAPTCHA-redirect confirmed in
2.C/2.D was observed on anonymous, cookie-less fetches (WebFetch-
style) — it was never actually tested against a real authenticated
browser session, so Sol should not assume it's blocked there without
trying. Fixed: ROLE's Mode B2/B3 bullet, and 2.C/2.D's "Automation
gap" notes, now instruct Sol to attempt these dashboards itself by
default via its own browser tooling — checking for a usable stored
session, or logging in with `CJ_EMAIL` plus a password/token obtained
via a secrets manager or MCP tool if one exists — and to fall back to
asking Itzik only when genuinely blocked (no credential exists
anywhere, or CAPTCHA actually does appear even authenticated), naming
that specific blocker rather than reporting "no tooling exists." A
human hand-off is now the fallback path, not the preferred default.
v1.9 — Itzik flagged that recent builds "don't even come close" to the
5 reference stores visually, and pointed specifically at
starnestshop.com/products/star-nest as the bar to hit — its videos,
images, headline copy, per-image arrow color, bundle design, and
reviews. Rather than restate that from memory, every claim below was
checked directly (live DOM inspection + screenshots, 2026-09-06) so
this section describes what is actually there, not an impression of
it. Two corrections came out of that check, in the same spirit as
v1.7's badge correction: (1) starnestshop's live product page has
**zero** `<video>` elements and **zero** chat-widget elements right
now (confirmed via direct DOM query) — it does NOT currently have "all
the videos"; whatever Itzik recalls seeing may have been changed since,
or may belong to a different store in the set. (2) Its gallery/slider
arrows are near-black (`rgb(18,18,18)`), not a brand color — also
confirmed via computed style, not assumed. Checking further, of the
5 reference stores, only **beelyra.com** actually has a real video
right now (confirmed: exactly one `<video>` element) — a full-bleed,
autoplay, muted, looping cinematic hero background clip with the
headline text overlaid directly on it ("Transfer your baby without
waking them"), not a product close-up. That's the concrete pattern
behind Itzik's "use more video in the background, it's more sellable"
instruction, and it's a DIFFERENT thing from the product-demonstration
video Section 7.B already covers (real CJ/ad video, product-specific)
— both are now required, as separate slots, see 7.B. What IS
confirmed and concrete on starnestshop (added to Section 5's blueprint
and 7.C below): a 3-tier bundle block with named badges ("Most
Popular," "Best Deal!") and nested per-tier add-on checkboxes
(Shipping Protection / Warranty / Mystery Gift); review cards built
from a real customer photo + a filled-star row + a bold name + a small
"variant purchased" line + a "✓ Verified buyer" badge; a sticky
countdown bar; a sticky bottom mini-cart bar that appears once you
scroll past the buy box; and soft SVG wave dividers between sections
as a real, cheap background effect (no video needed for this one).
Two more elements Itzik asked for are Itzik's own new requirements
layered on top of this set, NOT things observed on any of the 5
reference stores (stated plainly so a future build doesn't go hunting
for them there and come up empty the way the video assumption did):
a brand-accent-colored gallery arrow (the references use neutral
black/white — this is a deliberate improvement, not a copy), and a
24/7 support widget fronted by a support persona named "Nora" using a
real support email address — added as new Section 7.E. Section 8
gained an 8.C for the concrete background/button motion effects this
all implies (wave dividers, soft blob/gradient shapes, colored arrows,
the existing button hover restated alongside them so it isn't missed).
v1.10 — Itzik asked for three concrete things: real working React
background effects (not just prose describing them), a checkpoint
where Sol confirms a sourced product with him before committing a
full build to it, and pricing that actually targets real profit, not
just the sourcing-time minimum. Three real fixes, not just skill text:
(1) Section 10 was flatly wrong — it told Sol to build a Shopify
Dawn/Liquid theme, but checking the actual repo directly showed every
recent one-off store (`react-furlo`, `react-aurelo`,
`react-lullabyloom`, `react-lumora`) is a config-driven **React 19 +
Vite + Tailwind v4** app built from a real starter,
`stores/shopify/react-store-template` — rewritten to describe that
correctly instead of a stack nothing was actually using. (2) Built the
missing pieces directly into that template rather than only writing
more prose about them: `BackgroundEffects.tsx` (`GradientBlobs`,
`WaveDivider` — zero-dependency, no library version risk),
`SupportWidget.tsx` (the Nora 24/7 bubble, config-driven,
placeholder-email-aware), a rebuilt `BuyBox.tsx` bundle block (tier
badges + nested add-on checkboxes, matching starnestshop's confirmed
shape instead of the old plain 3-button grid), colored hover-arrows on
`Gallery.tsx`, a `heroVideo` config field + hero background video
render in `App.tsx` (the beelyra.com pattern from v1.9), and
`Review.photo`/`variantPurchased` fields so review cards can show a
real photo instead of always falling back to initials. Verified with
`npx tsc -b --noEmit` (clean, zero type errors) — **not** verified
visually: `npm run build`/`npm run dev` both failed in this session's
device-bridge sandbox specifically on a native-binding/architecture
mismatch unrelated to these changes (a known class of issue for that
isolated VM, same shape as the earlier `.venv` python quirk) — confirm
visually with `npm run dev` on the actual machine before shipping a
store built from this. (3) Added Section 2.E: after sourcing picks a
candidate (any mode), stop and confirm it with Itzik — product, real
cost, proposed price/margin, demand signal, video/review status —
before starting Mode 1. This is deliberately a different rule from
v1.8's "don't wait for approval to browse dashboards" — browsing is
free to do autonomously, but a full build pass is real cost, so the
specific product choice gets confirmed first. Also added explicit
pricing guidance: 2.A.5's "Margin ≥ 30%" is a candidate filter, not a
target — the actual price charged should target roughly 3-4x landed
cost (~65-75% gross margin), separate from the 1.8-2.2x anchor-price
multiplier used for the "SAVE X%" display.
v1.11 — Followed up on v1.10's open item ("not verified visually").
The `npm run build`/`npm run dev` failure in the device-bridge session
was specific to that mounted folder's existing `node_modules` (almost
certainly installed on the actual Mac, so its native binaries don't
match the bridge's own isolated Linux VM architecture) — confirmed by
copying the template's source (excluding `node_modules`) to a scratch
path outside the mounted folder, running a fresh `npm install` there,
and running `npm run build`: it succeeded cleanly (`vite build`, 38
modules, no errors). Went one step further than a bare successful
build — grepped the compiled production JS bundle directly for
literal strings that only appear if the new features actually render:
`Nora`, `24/7 Support`, `yourdomain.example`, `Most Popular`, `Best
Deal`, `Verified buyer` — all six found, each exactly once, in the
shipped bundle. This doesn't replace an actual pixel/visual check (no
headless browser was available in that scratch environment to
screenshot the rendered page), so still confirm layout/spacing/
animation visually with `npm run dev` before calling a real store
done — but the code is now confirmed to compile, bundle, and carry
the new content through to what a browser would load, not just to
type-check.
v1.12 — Got the actual screenshot v1.11 said was still missing, and it
paid for itself: staged the template's source out of the device-bridge
VM (where `npm run build`/`dev` hit the native-binding mismatch) into
the cloud session's own workspace, installed and built there cleanly,
ran `vite preview`, and screenshotted it with Playwright (already
available in that workspace) — hero, the bundle block, the wave-
divider/lifestyle area, reviews, and the Nora widget opened. Real
visual verification, not just a compile check, and it found a real
bug a type-check can't catch: the "Most Popular"/"Best Deal!" tier
badges (added in v1.10) were invisible — clipped to a sliver by the
tier card's `overflow-hidden`, which was only there to keep the
add-ons background block's corners rounded. Fixed in `BuyBox.tsx` by
dropping `overflow-hidden` from the card wrapper (repositioning the
badge to sit fully inside the card instead of straddling the border)
and rounding the button/add-ons block's own corners individually
instead — applied to both the cloud verification copy and the real
file on Itzik's machine, `tsc` still clean after. The lesson for any
future build, not just this fix: a component that type-checks and
even builds can still be visually broken — CSS-level bugs like
`overflow-hidden` clipping an absolutely-positioned child only show up
in an actual screenshot, which is exactly why Section 11 requires one
and not just a type-check.
v1.13 — Itzik looked at the v1.12 screenshots and called it correctly:
"the colors don't grab the eye, everything is gray and boring." The
root cause was embarrassing given Section 8.A already existed: the
demo store's `theme.accent` was `#B9705A`, a muted dusty-rose — which
is *literally* the exact palette this changelog's own v1.0 entry
already named as the rejected, boring reference build ("Nimbly /
CloudNest Wrap, dusty-rose-on-cream"). It never got fixed when the
demo was rebuilt on the real template, so every screenshot since has
been quietly proving Itzik's complaint. On top of that, several
components Section 8.A already said should repeat the accent color
were not actually wired to it: `StarRating.tsx`'s filled stars were
hardcoded `text-amber-400`, `BuyBox.tsx`'s "SAVE X%" badge used
`--color-success` (green), and `CountdownTimer.tsx`'s numbers had no
color style at all — so even a bold accent chosen for the button
would only ever show up on the button. Fixed all of it: (1) changed
`demoProduct.ts`'s `theme.accent` to `#FF4D4D`, a saturated coral-red;
(2) wired StarRating, the SAVE badge, and CountdownTimer's numbers to
`var(--accent)`, matching what Section 8.A already asked for; (3)
changed `--color-bg-soft` in `index.css` from a hardcoded beige
(`#f7f5f2`) to `color-mix(in srgb, var(--accent) 7%, white)`, so
section backgrounds carry a tint of the brand color instead of fading
to gray the moment you're not looking at a button — this alone is
what fixes the "gray" half of the complaint, since most of a page's
surface area is background, not buttons. Verified the same way as
v1.12: rebuilt cleanly, restarted `vite preview`, re-screenshotted
with Playwright. The difference is immediately visible — header bar,
stars, SAVE badge, bundle-tier badges, Add to Cart, countdown, and the
Nora widget bubble now all read as the same vivid coral, not four
unrelated colors plus a muted brand tone. Applied to both the cloud
verification copy and the real file on Itzik's machine; `tsc` clean
on both. Lesson for every future build: Section 8.A's "make the SAVE
badge / stars / countdown / button all match the accent" rule is not
optional polish — skipping it is exactly how a store ends up
technically correct (builds, type-checks, has real content) and still
reads as "gray and boring," because a bold accent value alone does
nothing if half the components that should carry it don't reference
the variable at all. When picking `theme.accent` for a NEW product,
don't default to a muted/pastel/dusty tone even if it feels
"tasteful" — re-read Section 8.A's list (saturated coral, red,
orange, electric blue, hot pink) and pick one of those families, then
grep the template for `--color-success`, `text-amber`, or any other
hardcoded color that should have been `var(--accent)` before calling
the build done.
v1.14 — Itzik's very next line after the color fix: "אין גם וידאו
שמראה את המוצר" (there's also no video showing the product). Checked,
and he was right about something worse than a missing demo asset:
Section 7.B has said since v1.9 that a build needs TWO video slots
(mandatory hero background + a preferred real product-demo clip), but
the template only ever actually implemented the first one.
`heroVideo` existed in `types.ts`/`App.tsx`, but `Gallery.tsx` was
images-only — there was no field, no prop, no rendering path for a
demo/problem-solution video anywhere in the gallery, and on top of
that `demoProduct.ts` never even set `heroVideo`, so the one slot
that did exist rendered nothing either. That's why every screenshot
through v1.13 showed a static "Studio Shot" placeholder and nothing
else — not a missed config value, a genuinely missing capability.
Built the second slot for real: added `ProductConfig.productVideo:
{ src, poster, alt? }` to `types.ts`; rewrote `Gallery.tsx` so it
builds a unified slide list — the demo video (if present) as slide
0, then the images — with a real `<video autoPlay muted loop
playsInline controls>` element for the video slide, a poster-image
thumbnail with an accent-colored ▶ badge in the thumbnail strip (the
same "colored icon on the accent color" pattern as everywhere else
now), and the existing prev/next arrows cycling over video+images
together instead of images alone; wired it in `App.tsx`
(`<Gallery video={product.productVideo} .../>`). Populated BOTH
slots in `demoProduct.ts` with a small public-domain placeholder clip
(MDN's cc0 sample video) plus a labeled SVG poster for each, with an
explicit code comment that a real build must replace these with the
actual supplier/demo clip — the placeholder exists only so neither
slot silently renders nothing again. Verified the same way as the
last two rounds: `tsc` clean, real `vite build`, real `vite preview`,
real Playwright screenshots — the gallery's first slide now shows an
actual `<video>` element with native controls (not a static image),
and the hero background plays behind the fold. Synced all four
touched files (`types.ts`, `Gallery.tsx`, `App.tsx`,
`demoProduct.ts`) to Itzik's real machine; `tsc` clean there too.
Lesson: Section 7.B described two slots for five versions before
anyone checked whether the second one actually existed in code — a
requirement written in prose is not a requirement met; if a future
build looks like it's "missing video" again, check whether the
component that should render it exists at all before assuming it's
just an unset config field.
v1.15 — Itzik asked directly, after the video fix: "אתה רואה עוד
בעיות?" (do you see more problems?). Went looking deliberately instead
of waiting for the next complaint, and found three more real ones,
none of them cosmetic nitpicks:
1. **`--color-bg-soft` was STILL gray everywhere except the one place
   it was checked.** The v1.13 fix only got verified on the SAVE
   badge / stars / countdown / button — never on `--color-bg-soft`
   itself, which is used far more widely (Footer, ComparisonBlock,
   BuyBox's bundle add-ons panel, the Gallery frame, the Reviews
   section wrapper, and now WhyItWorks). Checked it with
   `getComputedStyle` and found the real cause: a custom property's
   nested `var()` resolves against wherever THAT property is declared
   in the cascade, not against whatever element later consumes it —
   so `:root`'s `--color-bg-soft: color-mix(in srgb, var(--accent,
   #1a1a1a) 7%, white)` was baking in the `#1a1a1a` fallback
   permanently, because `--accent` is only ever set on the `#top` div
   in `App.tsx`, never on `:root`. Every one of those sections was
   silently rendering a flat neutral gray tint instead of the
   intended coral tint, this whole time — v1.13's own screenshots
   just didn't happen to include one of them cropped closely enough
   to notice. Fixed by computing `--color-bg-soft` in JS
   (`App.tsx`'s `rootStyle`) with the literal accent hex already
   substituted in, right alongside `--accent` itself, instead of
   relying on CSS-side `var()` indirection. Full writeup and the
   general lesson (custom-property `var()` resolution scope, not
   specific to this token) belongs with the CSS itself now — see the
   comments in `App.tsx` and `index.css`.
2. **`GradientBlobs` was completely invisible on `LifestyleBlock`,**
   confirmed by a direct screenshot of that exact section showing
   zero trace of them. Root cause: they were wrapping a full-bleed
   opaque photo, which paints over them regardless of z-index (a
   `-z-10` layer only wins against other negatively-stacked layers,
   not a normal sibling's own opaque content). Moved them to wrap
   `WhyItWorks` instead (an open, tinted-background section, no
   photo) — see Section 7.D bug #5 above for the SECOND bug this
   surfaced (the wrapper additionally needed `isolate` to actually
   show them even on an open background — a genuinely subtle CSS
   stacking-context gap, not something a glance at the code would
   catch). Confirmed with a live `isolation:isolate` toggle before
   touching source: zero visible blobs without it, immediate and
   correct render with it.
3. **`LifestyleBlock`'s text overlay was the exact bug Section 7.D.3
   already documented — bug #3, known since v1.9 — and it was STILL
   live in the shared template.** A flat `bg-black/25` wash, never
   actually replaced with the gradient-scrim fix the skill itself
   already prescribed. On the demo specifically this was compounded
   by the lifestyle placeholder image having its own baked-in label
   text ("Lifestyle — Everyday"), which visually collided with the
   real overlaid headline — confirmed in a screenshot showing both
   strings printed on top of each other, illegible. Fixed both:
   replaced the flat wash with a radial scrim centered behind the
   text (per 7.D.3's own prescribed fix), and gave the `img()` demo
   helper a way to generate an unlabeled color placeholder, used
   specifically for `lifestyleBlock.image` (any placeholder that will
   have real text overlaid on it should never bake its own text in).
Verified all three the same way as every round since v1.12: real
`vite build`, real `vite preview`, real Playwright screenshots — this
time also using `getComputedStyle`/`elementFromPoint`/forced-style
probing via `page.evaluate` where a screenshot alone couldn't
distinguish "too subtle to see" from "not rendering at all" (the
blobs bug specifically required this — pixel-sampling the screenshot
first suggested "maybe just too subtle," and only forcing opacity:1
with no blur, and getting STILL nothing, proved it was a real paint-
order bug). Synced all six touched files (`App.tsx`,
`WhyItWorks.tsx`, `LifestyleBlock.tsx`, `BackgroundEffects.tsx`,
`index.css`, `demoProduct.ts`) to Itzik's real machine; `tsc` clean.
Lesson for every future build: "I fixed X" is only true for the
specific instance you screenshotted — if the same token/pattern is
used in five other places, check all five, not just the one in the
screenshot. And when something built with real CSS effort (blobs,
scrims, tints) doesn't show up in a screenshot, don't assume "must be
too subtle" and move on — force it to an extreme (opacity 1, no blur,
a lime outline) and check again; "still nothing even at full
strength" is the signal that it's a real rendering bug, not a design
taste call.
v1.16 — Itzik, after seeing the v1.15 fixes: "אפשר להוסיף יותר
אובייקטים מונפשים כדי שזה יראה מקצועי" (can you add more animated
objects so it looks professional), plus a request to see screenshots
in phone mode instead of desktop. Added real, working motion — not
just more of the same blob pattern copy-pasted — and this time
verified on an actual mobile viewport (390×844, device-scale 2,
`is_mobile`/`has_touch` set, iOS Safari UA) since that's what ships
most often and hadn't been screenshotted that way before:
1. **`ScrollReveal.tsx` (new)** — a generic IntersectionObserver
   wrapper that fades + slides content up once when it scrolls into
   view (doesn't re-hide on scroll-back, which would read as
   gimmicky rather than premium). Applied with a per-index stagger
   delay to `BenefitBullets` cards, `ReviewsSection` cards, and
   `GuaranteeBlock`'s content — the kind of deliberate, sequenced
   entrance that reference sites use and a flat instant-render
   doesn't have.
2. **`FloatingSparkles` (new, in `BackgroundEffects.tsx`)** — a
   lighter, more numerous counterpart to `GradientBlobs`: small
   accent-colored dots that twinkle/drift, for a "sprinkled with
   life" feel on sections where a few large blurred shapes would be
   too heavy. Added to the reviews section. Same `isolate`
   requirement as `GradientBlobs` (see bug #5) — documented in its
   own doc comment so this doesn't get rediscovered from scratch.
3. **`GradientBlobs` added to `GuaranteeBlock`** — it already had a
   tinted background and was sitting there as a flat, static block;
   now it gets the same living-background treatment as `WhyItWorks`.
4. **`animate-pulse-glow`** — a new subtle breathing box-shadow
   keyframe (accent-colored, expands and fades), applied to the SAVE%
   badge so it keeps drawing the eye instead of sitting static next
   to the price.
All of it respects `prefers-reduced-motion` (added to the same media
query block as the existing blob/reduced-motion handling) — animation
for polish should never be forced on someone who's asked their OS to
minimize it. Verified with real `vite build` + `vite preview`,
screenshotted BOTH the sections with new motion (reveal stagger,
sparkles, second blob instance, badge glow) AND confirmed on an actual
phone-sized viewport, not just desktop — this is now the default way
to screenshot for Itzik going forward unless he asks for desktop
specifically. Synced all six touched files (`ScrollReveal.tsx` new,
`BackgroundEffects.tsx`, `GuaranteeBlock.tsx`, `BenefitBullets.tsx`,
`ReviewsSection.tsx`, `BuyBox.tsx`, `App.tsx`, `index.css`) to Itzik's
real machine; `tsc` clean. Lesson: "more animated objects" doesn't
mean copy-pasting the one existing effect into more places — it's
worth introducing a genuinely different motion primitive (scroll
reveal vs. ambient float vs. twinkle vs. pulse) so the page feels
considered rather than repetitive, and every new one needs the same
`isolate` discipline as bug #5 or it silently renders nothing.

v1.17 — Itzik, after seeing v1.16: "אהבתי כבר ניראה הרבה יותר טוב" (I
like it, it already looks much better), then three concrete asks in one
message: (1) show good reviews with customer photos where available,
(2) add a way to view ALL reviews, not just the first few, (3) let a
customer leave a review, but only after purchase — via an automated
email sent once the product has actually arrived, asking about their
experience and prompting a review. Handled (1) and (2) as real template
work; treated (3) as a genuine product decision, not something to
silently stub out — see below.
1. **Photo reviews.** `ReviewsConfig.items` (demo data) expanded from 3
   to 8 entries; 5 now carry a `photo:` field via the existing `img()`
   placeholder helper, with descriptive labels ("In the car seat", "Nap
   time", "Twins, bedtime", "Fresh from the wash", "Travel day") so they
   read as genuine customer photos rather than generic stock. Preceded
   by an explicit comment block reasserting Rule 1 (skill Section 0 /
   7.D bug #1): these are demo/template placeholders only — swap for
   genuinely imported customer review data before any real launch, the
   same as the placeholder product photos and placeholder video.
   `ReviewsSection.tsx` already had a photo slot per card (aspect-[4/3]
   image, falls back to an initials avatar when `r.photo` is absent) —
   no component change needed there, just real demo data to prove it
   actually renders.
2. **"View all N reviews."** `ReviewsSection.tsx` now shows an
   `INITIAL_VISIBLE = 6` first page and, when more reviews exist,
   a bordered accent-colored button ("View all {N} reviews") beneath
   the grid that expands to the full list on click and then disappears
   — avoids dumping potentially dozens of reviews (a real store's
   `count: 312`-style total is way more than 8) into the initial
   render. Verified live: initial state showed 6 cards + button reading
   "View all 8 reviews"; clicking it revealed exactly 8 cards and the
   button itself was gone afterward (confirmed via DOM query, not just
   visually) — proving it isn't just decorative.
3. **Post-purchase review-request email — CORRECTED after Itzik pushed
   back.** First pass here initially reached for a third-party app
   (Loox/Judge.me) as the only path, and raised it to Itzik as a
   build-vs-buy question. Itzik pointed out he thought Shopify already
   has this natively — checked, and he was right, partially: Shopify's
   own **Shop channel** has a built-in automatic review request that
   fires 1-180 days after an order is marked delivered (merchant sets
   the delay in Shop settings), with zero third-party app and zero
   extra cost — this is genuinely native Shopify, not a workaround.
   The real caveat isn't the email trigger, it's two other things:
   (a) it does NOT natively support requesting/collecting a photo with
   the review — that's still where Loox/Judge.me/Stamped etc. add real
   value if photo-reviews-at-scale specifically matters, since they're
   built around photo incentives (e.g. a discount code for a photo);
   (b) it only exists for a store actually running as a live Shopify
   store with real orders and fulfillment events flowing through
   Shopify — this template's own `CartDrawer.tsx` checkout button is
   still an explicit stub ("Wire this button to Shopify Buy SDK /
   Storefront API checkout — see README"), so the native Shop-channel
   review request isn't reachable from code in this repo at all; it's
   a setting turned on in the real Shopify admin once the store is
   actually launched there, not something this frontend template
   builds or fakes. **Corrected guidance:** default recommendation is
   now the free native Shop-channel review request (enabled in Shopify
   admin at launch, no app needed) for the base flow; suggest a
   dedicated review app as an *addition* only when photo-incentivized
   reviews specifically matter, not as the default first answer.
   **Lesson for future rounds:** don't reach for "install a third-party
   app" as the reflexive answer to "does Shopify support X" without
   checking Shopify's own native/first-party features first — Itzik
   correctly caught that the free native option should have been the
   first thing checked and offered, not skipped straight to a paid
   app recommendation.
Verified both (1) and (2) with a real `vite build` + `vite preview` and
actual mobile-viewport Playwright screenshots (the v1.16 default):
initial reviews grid with photo cards, the "View all" button, and the
fully expanded 8-card grid. Synced `demoProduct.ts` and
`ReviewsSection.tsx` to Itzik's real machine; `tsc` clean there too.

v1.18 — Two follow-up asks from Itzik in quick succession, both about
page structure rather than new features:
1. **"Even more animated background, and move the first video lower,
   into the how-to-use content."** The old design autoplayed an
   ambient `heroVideo` full-bleed at the very top of the page, before
   the shopper had even seen the gallery or price. Rather than just
   adding more of the same blob effect, restructured: removed that
   top-of-page ambient video entirely; renamed the config field
   `heroVideo` → `usageVideo` (Section types.ts) to match its new,
   narrower purpose; built a new **`HowToUseSection.tsx`** — numbered
   usage steps (each can carry its own small photo) next to the demo
   video — and moved it down the page, after the benefits. For "more
   animated background": added `GradientBlobs` directly behind the
   hero fold grid itself (Gallery+BuyBox), not just lower sections,
   and added `GradientBlobs` to `ComparisonBlock` (previously flat/
   static). Also fixed a small bug this surfaced: `FloatingSparkles`
   used a fixed seed sequence, so every instance's first dot landed at
   the exact same (5%, 10%) top-left spot — invisible when there was
   only ever one instance per page, but landed squarely on
   `HowToUseSection`'s own headline the moment a second instance
   existed nearby. Fixed with a `seedOffset` prop so different
   instances draw from a different slice of the sequence.
2. **Full page reorder, given mid-task as a follow-up message.** Itzik
   specified a complete new section order: (a) a compact carousel of
   ONLY verified 5-star reviews directly under the Add to Cart button
   — a confidence nudge at the exact buy decision, distinct from the
   full reviews section; (b) size guide / shipping & delivery info
   right after the benefits; (c) the how-to-use video+steps section
   after that; (d) the full reviews section (with the v1.17 "view all"
   button) moved to be the LAST content block on the page, immediately
   before the footer. Built:
   - **`MiniReviewCarousel.tsx` (new)** — filters `reviews.items` to
     `rating === 5 && verified`, renders a horizontally-swipeable strip
     (`snap-x snap-mandatory`, reusing the existing `no-scrollbar`
     utility) of small cards: avatar, name, "✓ Verified buyer", stars,
     one-line quote. Uses an initials-avatar circle exactly like
     ReviewsSection's own fallback for reviews without a photo — never
     a fabricated headshot (Rule 1: a real customer photo isn't
     available here any more than anywhere else, and a colored
     initials circle is the honest way to represent "a real person,
     unphotographed", not a invented one). Wired into `BuyBox.tsx`
     right after the Add to Cart button.
   - **`FaqAccordion.tsx`** generalized with an optional `heading` prop
     (default "Frequently asked questions") so the exact same
     component renders the new size/shipping block under its own
     heading ("Size guide & shipping") without a duplicate component —
     new `ProductConfig.sizeAndShipping?: FaqItem[]` field, same
     `{question, answer}` shape as `faq`.
   - **`App.tsx`** section order rewritten to: hero (fold, with
     `GradientBlobs`) → `BenefitBullets` → `sizeAndShipping` accordion
     → `HowToUseSection` → `WhyItWorks` (blobs) → `LifestyleBlock` →
     `ComparisonBlock` (blobs) → `FaqAccordion` → `SecondaryCta` →
     `GuaranteeBlock` → `ReviewsSection` (sparkles) → `Footer`. Reviews
     now sits last on purpose — confirmed via `document.querySelectorAll('h2')`
     text order in a live page, not just by reading the JSX, since
     this is exactly the kind of thing that's easy to get subtly wrong
     (a stray leftover divider, a component still mounted twice) when
     reordering this much markup in one pass.
Verified end-to-end on a real `vite build` + `vite preview` + mobile
Playwright screenshots: the mini 5-star carousel renders under Add to
Cart with real horizontal scroll; the size/shipping accordion opens;
`HowToUseSection` shows numbered steps with per-step photos next to the
video; `ComparisonBlock`'s new blob background is visible; and — the
one most worth getting wrong — the full reviews section is confirmed
the last `<h2>` before the footer's own markup, not just "somewhere
near the bottom." Synced all 9 touched/new files (`types.ts`,
`demoProduct.ts`, `FaqAccordion.tsx`, `HowToUseSection.tsx`,
`BackgroundEffects.tsx`, `ComparisonBlock.tsx`, `App.tsx`, `BuyBox.tsx`,
`MiniReviewCarousel.tsx` new) to Itzik's real machine; `tsc` clean
there too. Lesson: when a page-order request arrives as a flat list
("X, then Y, then Z, then W right before the footer"), write out the
FULL resulting order before touching JSX — it's easy to satisfy each
individual instruction locally while still leaving the overall
sequence wrong (e.g. moving reviews down without also moving guarantee/
FAQ/secondary-CTA out of the way so reviews actually ends up last).

v1.19 — Itzik reviewed v1.18's screenshots and reported two concrete
problems, not new features: "the carousel doesn't work well — no dots,
text runs out of the card" and "the top of the page, down through Add
to Cart, should be plain white only; background decoration elsewhere is
fine." Both were genuine defects in what v1.18 shipped, not scope
creep, and both got the same real-verification treatment as any other
bug in this skill:
1. **`MiniReviewCarousel.tsx` had no positional feedback and let long
   quotes escape the card.** `line-clamp-3` alone wasn't enough because
   the card itself had no fixed height — a real screenshot showed
   Priya's quote text visibly running past the card's rounded border.
   Fixed by giving each card a fixed height (`h-44`) with
   `overflow-hidden` on both the card and the clamped `<p>`, plus
   `break-words` so a long unbroken word can't force overflow either.
   Added actual dot indicators: an `onScroll` handler estimates the
   active card from `scrollLeft`, renders one dot per review (active
   dot wider + accent-colored), and each dot is clickable
   (`scrollTo({behavior:'smooth'})`) to jump directly to that card —
   confirmed live by reading `getBoundingClientRect()` on every card's
   clamped paragraph vs. its own card bounds (all `overflows: false`)
   and by clicking a dot and confirming both the visible cards AND the
   active-dot styling actually changed, not just the first.
2. **The hero fold (Gallery + BuyBox, everything down through Add to
   Cart) had picked up a `GradientBlobs` background in the SAME v1.18
   round that added it** — reasonable in isolation ("more animated
   background" was itself a real ask, one round earlier), but Itzik
   drew the actual line precisely: plain white through the buy
   decision, decoration is welcome everywhere after. Removed
   `GradientBlobs`/`isolate` from that one wrapper only — every other
   decorated section from that same v1.18 round (`WhyItWorks`,
   `ComparisonBlock`, `HowToUseSection`, `ReviewsSection`) was left
   untouched, since Itzik's line was specifically "through Add to
   Cart," not "less animation everywhere."
**Lesson:** an instruction to add more of something (more motion, more
sections) rarely means "everywhere, uniformly" — it's worth asking
where the shopper's attention should stay clean and un-distracted
(here: the actual buy decision) versus where extra visual interest
helps rather than competes. When in doubt, a boundary this specific
("up through X, not after") is exactly the kind of thing to build
narrowly rather than guess wide, since undoing an over-applied effect
from a section that was fine is wasted round-trips.
Verified with a real `vite build` + `vite preview` and mobile
screenshots: hero background confirmed plain white in the actual
screenshot (not just by reading the removed JSX), 6 dots rendered under
the carousel matching the 6 five-star-verified demo reviews, quote text
confirmed non-overflowing via a live DOM measurement, and dot-click
navigation confirmed by screenshotting before/after. Synced `App.tsx`
and `MiniReviewCarousel.tsx` to Itzik's real machine; `tsc` clean there.

v1.20 — Itzik flagged a workflow gap while a separate real-sourcing
attempt was in progress: "every time you build a product for a store,
could you ask me whether the store is new or existing — and if
existing, pull from the list of existing stores and build the product
page there?" Checked `stores/shopify/` on his real machine and
confirmed this was a genuine, already-happened gap: `react-aurelo`,
`react-furlo`, and `react-lullabyloom` all exist as separate one-off
store folders (alongside `hydrogen-alphaforbaby`, his real Hydrogen
store), each built as a fresh scaffold with no step anywhere that ever
asked whether the product belonged in one of them instead. Added a new
**"Kickoff — new store or existing?"** subsection at the very top of
ROLE, before any mode is chosen: Sol now asks Itzik this directly,
every time, listing the actual current folders under `stores/shopify/`
(excluding the shared `skills/` folder and `react-store-template`
itself, the master template) rather than assuming or reusing a
remembered list — that list changes every time a store ships. If
existing, Sol builds inside that store's own codebase instead of
scaffolding a new `react-store-template` copy, and asks how the new
product relates to what's already there (additional page vs.
replacement/relaunch) when that isn't already obvious. Lesson: a
repeated action (scaffold-a-new-store) that was never explicitly
wrong on any single occasion can still be a standing gap once there's
a real list of prior one-off stores to point to — worth periodically
checking actual on-disk state against what the skill assumes, not just
trusting the skill's own description of its process.

v1.21 — Real-sourcing research session with Itzik (product still TBD):
confirmed the CJdropshipping Shopify app is already installed on the
real store with agent-reachable Shopify Admin API access, and that CJ's
own official Shopify integration handles product import (images,
video, price, variants) natively — genuinely better than this skill's
agent browsing CJ's website itself for that part, since it's an
authenticated first-party sync with no CAPTCHA/login wall to fight.
For reviews specifically: researched Ali Reviews' documented Public
API (`GET https://pub.kudosi.ai/public/reviews?product_id=...`,
Bearer-token auth) as a possible path for agents to pull imported
reviews programmatically — Itzik declined it once he learned it's a
paid-tier app ("Free" caps at 10 published reviews/product; the API
itself isn't confirmed to even be included below a paid plan): he
wants zero added ongoing cost, full stop. Codified this as the
standing default in **Section 7.C's review fill order**: (1) — reading
the sourced product's own "Buyer Review" tab directly during a 2.C/2.D
hand-off or your own authenticated browser session, then persisting
what you find as a Shopify **metafield** on the product (free, durable,
uses Admin API access you already have) — is now the REQUIRED default,
not merely preferred; a paid review-import app is opt-in only, per an
explicit yes for that specific build, never a silent fallback. Also
clarified in code comments/config only, not yet built: no metafield-
write code exists in `react-store-template` yet (it's currently a
static-config demo, not wired to live Shopify data — see `CartDrawer`'s
own "Wire this button to Shopify Buy SDK / Storefront API checkout"
comment) — writing real reviews to a live product's metafields is a
capability to build when an actual Mode B/B2/B3 sourcing run reaches
that step, not something retrofitted into the demo product speculatively.
Lesson: research a specific paid solution fully (pricing, what's
actually gated behind which tier) before recommending it — Itzik's
answer here wasn't "no automation," it was "no unnecessary recurring
cost when a free path already does the same job," and the skill's own
Section 7.C already listed that free path as an option; it just hadn't
been marked as the required default until a real cost tradeoff forced
the question.

v1.22 — Itzik flagged that a real Mode B2 hand-off report (the "New
Outdoor Trucker Embroidered Baseball Cap" / NORTHPINE build, run in
Claude Code) buried three real decision points (the 2.E go-ahead, a
Buyer Review count check, an asset-generation cost approval) inside a
long technical report with tables/JSON/bash output, instead of asking
them as real interactive questions. Initial diagnosis was wrong twice
before landing on the truth: first assumed Claude Code CLI has no
interactive-question capability at all (false — confirmed AskUser
Question has existed there since v2.0.21, a general-purpose tool
distinct from MCP's server-only "elicitation" feature added in
v2.1.76); the real gap was simply that an available tool went unused.
Added a new ROLE subsection, "How to ask Itzik for a decision,"
requiring Sol to check for and use an interactive multiple-choice tool
(e.g. `AskUserQuestion`) whenever this file says to ask Itzik
something, falling back to disciplined top/bottom-of-message plain
text (numbered, one sentence each, then actually stop and wait) only
when no such tool exists — and cross-referenced it from Section 2.E.
Lesson: don't assume a platform lacks a capability just because one
session of it didn't use that capability — verify against current
docs/changelogs before writing that limitation into the skill as fact.

v1.23 — First real live-store build (alphaforbaby.com, Ergonomic Baby
Hip Carrier, `update-display` branch) surfaced a cluster of concrete
bugs Itzik caught by actually opening the live page — none of them
would have been caught by reading the code or trusting a "done" report.
Root cause across most of them: reusing/adapting the previous
(clothing-store) template's components instead of building the page
fresh from this spec — Itzik's call, and the right one; a rebuild from
scratch is now the standing instruction whenever a product page is this
different in kind from what a template was built for. Specific new
rules, added to the sections below:
1. **Never expose the supplier/sourcing identity on the storefront.**
   No CJ-branded SKU prefixes (e.g. `CJWJYEYE...`) visible anywhere in
   rendered text, no hotlinked `cjdropshipping.com`/`cf.cjdropshipping.
   com` asset URLs (re-host every image/video on the store's own CDN,
   per 7.A/7.B), no vendor/tag field leaking a supplier name, nothing in
   meta tags or JSON-LD. This isn't a Rule-1 honesty violation (the
   product and its reviews are still real) — it's normal DTC practice:
   a store doesn't advertise its supply chain on the PDP. Check
   rendered `document.body.innerText`, page `<head>` meta, JSON-LD, and
   every `img`/`video` `src` domain before calling a build done (added
   to 7.D and Section 11).
2. **Real review dates that predate the store's own launch must not be
   shown verbatim.** Genuine 2021 CJ reviews on a store launching in
   2026 reads as a giveaway, even though the reviews themselves are
   real — this is a presentation problem, not a fabrication one. Drop
   the exact date from the review card (keep star/name/flag/quote/
   photo); do not invent a different date. (7.C)
3. **A "Write a review" form must not render unless it actually saves
   somewhere real.** A form with no backend behind it is its own kind
   of dishonest UI — remove it entirely rather than ship a submit
   button that does nothing. (7.C, 7.D)
4. **Review photos need a click-to-enlarge lightbox** (modal, closable
   via an X button, click-outside, and Escape; body scroll locked while
   open) — added as a standard review-card interaction, not a one-off
   ask. (7.C)
5. **New 7.D bug patterns**, all found on this same build: raw
   markdown syntax (` ```html `, stray ` ``` `) left unrendered as
   literal page text because copy was written in markdown but never
   passed through an actual renderer; a supplier spec field mismapped
   to the wrong display label (CJ's `packingNameEn` is packaging
   *material*, e.g. "Plastic bags" — never package *contents*; the real
   contents line lives in the free-text description, not that field);
   and a dead UI element inherited from a prior template (a "360°"
   photo-spin badge with no 360 asset behind it) that a patch-in-place
   approach left rendering — a wholesale rebuild of the specific
   component, not a conditional hide, is the fix once a template no
   longer matches the product category.
6. **Verification must be an explicit, itemized report, not an internal
   check.** After any build/fix is claimed done, go through Section 11
   literally line by line and report pass/fail for each item back to
   Itzik (or whoever asked) — don't just say "verified" and summarize;
   show the checklist itself with its actual state. This was Itzik's
   direct request after this build needed three separate correction
   rounds before it was actually right.

v1.24 — Itzik suspected something about the bundle block was missing
after seeing it absent from the Ergonomic Hip Carrier page; checking
found a real, specific gap, not a vague one. `store_brief.json` has
defined a `store_mode: single_hero_product | multi_product_niche`
field since it was written — but nothing in the entire skill ever
branches on it. Section 5 item 3's bundle-tier block only describes one
shape (same-SKU quantity tiers — Single/Twin/Family of the identical
product), confirmed on starnestshop.com, a single-hero-product
reference store. alphaforbaby.com is explicitly the other mode: 11
independent products, no hero (Itzik's own words: "אין מוצר שהוא ראשי,
לכל מוצר צריך להיות דף נחיתה משלו") — and almost nobody buys 2-3 of the
same baby carrier, so the quantity-tier shape doesn't fit here even
though the section itself really was "missing," which is exactly what
Sol's own checklist correctly flagged (items 13/28). What a multi-
product catalog actually wants instead is a cross-sell bundle — real
OTHER products from the same catalog, bundled together at a real
combined discount — and the skill had no shape defined for that at
all. Fixed by wiring `store_mode` into Section 5 item 3 with two
distinct bundle shapes, one per mode, and added a new 7.D bug pattern
(#10) for the general case: a brief field that's declared but never
consulted anywhere downstream, which silently produces the wrong
output shape with no error and no failing check. Lesson: a config
field existing in the schema is not the same as it doing anything —
grep for every field's actual usages, not just its declaration, when
auditing what a spec covers.

v1.25 — Itzik asked for Section 11 to be checked "like tests with
pytest" instead of the v1.23 itemized-prose-report format, after that
format still let real misses through (v1.24's `store_mode` gap wasn't
caught by a manual pass over the checklist either). Prose reports —
even itemized, even honest — depend on remembering to look in the
right place each time; an automated test either runs and passes or it
doesn't, and the assertion message says exactly what failed. Added
Section 12: a pytest + Playwright suite (`tests/test_pdp_compliance.
py`, starter version handed to Sol directly, not just described) that
encodes the highest-value Section 11 items as real, runnable
assertions — supplier-identity leaks (checking expanded accordions
too, per the v1.23 near-miss), duplicate video instances, video
autoplay attributes, dead review forms, review-photo lightbox
open/close, hidden pre-launch dates, and store_mode-correct bundle
presence. This does not replace Section 11 (a human still needs eyes
on visual/subjective items — color pop, motion variety, layout order)
but it now owns everything that can be checked mechanically,
parametrized across every product handle so it scales to all 11
without re-deriving the checks each time. `pytest -v` output, not a
paraphrase of it, goes in the "done" report from now on for whatever
it covers.

v1.26 — Itzik looked at the live `multi_product_niche` cross-sell
bundle (v1.24's fix) and said it still isn't right: a single flat "10%
off 3 items" doesn't actually push a 2-item cart toward a 3-item cart —
there's no reward for the in-between step. He specified the real
structure directly: buying 2 of the 3 bundle items should unlock a
small free gift; buying all 3 should switch to 10% off instead (not
gift + discount stacked — confirmed explicitly, the 10% alone is the
tier-2 reward). He also asked, separately, the concrete mechanical
question this immediately raises: how do you actually put a $0 item
into checkout and have it ship with the paid items, rather than a
manual "send him the 2 items" step afterward. Rewrote Section 5 item
3's `multi_product_niche` shape into this explicit two-tier design, and
added the real Shopify wiring for it: a native "Buy X, get Y" automatic
discount (100% off the specific gift product, minimum-2-from-collection
condition) makes the gift line genuinely free at checkout; the frontend
still has to add that gift product to the cart as a real line item via
`cartLinesAdd` once 2 items are selected (a Buy-X-Get-Y discount
discounts an existing line, it doesn't add one on its own), and remove
it again if the cart advances to all 3 (tier 2 replaces tier 1, so the
existing 10%-off discount and the new Buy-X-Get-Y discount must not
both fire on a 3-item cart — verify this in a real test checkout, not
just by reading the two discounts' Admin config). Because the gift
becomes a normal line item on the same order, Shopify's normal
fulfillment ships it in the same shipment as everything else — no
separate manual send-out needed once this is wired correctly. Added a
new Section 11 checklist item requiring a real test order/order-preview
to confirm this rather than trusting the Admin discount config alone.
The specific gift product (cheapest eligible catalog item not already
in this bundle) still needs to be picked against real, current pricing
and stock status — not guessed here — and should not be one of the 5
products already flagged with the zero-inventory publish bug until
that's fixed, since a "free gift" that can't actually be fulfilled is
worse than no gift. Lesson: a discount number in the UI and a discount
actually reaching checkout are two different things to verify — same
shape as 7.D bug #10, a step (the frontend cart-add) that has to exist
for the Admin-side discount config to mean anything at all.

v1.27 — Itzik simplified his own v1.26 request almost immediately:
drop the free-gift tier (and the cart-line-add mechanics it required)
entirely, and make the `multi_product_niche` bundle a plain two-tier
percentage discount instead — 2 of 3 items = 5% off, all 3 = 10% off.
Rewrote Section 5 item 3's `multi_product_niche` shape accordingly:
two automatic order discounts (minimum-quantity 2 → 5%, minimum-
quantity 3 → 10%), with an explicit warning that a 3-item cart
satisfies both conditions and must resolve to only the 10% discount —
verified with a real test checkout, not just Admin config, same lesson
as v1.26's discount-combination point but now simpler to get right
since there's no cart-line-add step at all. Itzik separately asked, in
the same exchange, whether this discount actually stays profitable
across every product it could apply to — a real, previously-unasked
question this skill had no explicit check for. Added a mandatory
margin check: compute real margin (discounted price minus real landed
cost, over discounted price) for every 2-item and 3-item combination
the bundle allows, against the same 30% floor 2.A.5 already uses as a
sourcing gate, and flag any combination that falls below it with real
numbers rather than shipping a percentage that looks good in the UI but
loses money on some product mix. Lesson: a discount's UI simplicity and
its backend correctness are separate axes — simplifying the reward
shape (dropping the gift) doesn't remove the need to verify the
discount-priority behavior at checkout, and a "how much do we save the
customer" design pass should always be paired with "does this still
make us money," which nobody had asked explicitly until now.

v1.28 — Itzik reported "I don't have bundle buttons, there's only Add
to Cart" right after Sol's v1.27 report claimed the tiered bundle was
fully built and passing. Rather than take either claim at face value,
checked the live DOM directly: the two removable bundle items really
do have working `<button role="checkbox">` controls — real
`aria-label`/`aria-checked`, `cursor: pointer`, and clicking one (done
directly via `el.click()` in a live tab, not assumed) correctly
recomputed the cart to 2 items / 5% off, updated the total, and changed
the CTA to "ADD 2 TO CART". So Sol wasn't wrong that it works — but
Itzik wasn't wrong either: a screenshot shows all three checkmarks
(the two real toggles and the one fixed "this item" marker) rendered
as visually identical small orange squares, with no hover state, no
size or style difference, nothing communicating "these two are
buttons." A control a person can't tell is a control might as well not
exist. Added 7.D bug #11 for this exact shape — a check that only
verifies role/behavior (which is what Section 12's pytest assertions
and Sol's own report both did) can pass while the actual human-facing
problem the user reported is still real. Added a Section 11 item
requiring an explicit visual-affordance check (from a real screenshot,
not from confirming the click handler) for any interactive control that
sits next to non-interactive lookalikes. Lesson, sharper than v1.25's
own pytest push: automated tests are exactly right for "does this
behave correctly" and cannot substitute for "does this look like
something a person would think to click" — both checks are required,
neither replaces the other, and a passing test suite is not permission
to skip actually looking at the page.

v1.29 — Itzik pointed at a second live, successful competitor
(littlesnugg.store/products/baby-carrier-hoodie, confirmed directly via
DOM/text extraction, not from memory) and asked for a full comparison:
"look at the level difference — ours is boring, this is a really good
store." Three concrete, confirmed gaps came out of that comparison, not
vague impressions:
1. **The bundle shape itself was wrong for this store, not just its
   percentages.** littlesnugg runs a same-SKU Buy 1 / Buy 2 (10% off) /
   Buy 3 (35% off, "BEST VALUE") quantity-tier block with real nested
   add-ons (Priority Delivery, Shipping Protection) — on ONE product,
   successfully. This directly contradicts v1.24's founding assumption
   for `multi_product_niche` ("nobody naturally buys 2-3 of the same
   baby carrier") — baby gear is bought in multiples constantly (gifts,
   siblings, showers). Itzik chose explicitly to replace the v1.24-
   v1.27 cross-sell "complete the set" design entirely with the
   same-SKU quantity-tier shape, for every product regardless of
   `store_mode`. Rewrote Section 5 item 3 accordingly, retired the
   store_mode branch there (kept `store_mode` itself, in case it
   matters elsewhere), and rewrote the Section 12 test that enforced
   the old branch.
2. **Gallery slide 1 was a raw CJ marketing composite, not a clean
   shot** — confirmed by direct comparison: alphaforbaby's current
   slide 1 merges a small inset lifestyle photo into the same frame as
   the main product shot, while every littlesnugg slide is one clean
   subject. Added 7.D bug #12 and a Section 11/12 check for this.
3. **Chrome above the fold competes with the hero image for space** —
   alphaforbaby stacks a full header (logo, search bar) plus a 3-item
   trust row above the gallery; littlesnugg keeps only a slim ticker +
   bare logo bar there, so the product image dominates the first mobile
   viewport. Added this as an explicit Section 5 item 3 requirement.
Lesson: "make it less boring" is too vague to act on until it's
cashed out against a second real reference doing the same category
well — the same discipline this skill has used since v1.9 (starnestshop,
beelyra) applies just as well to a spontaneous competitor link as to a
planned reference-store analysis, and it's worth actually opening the
link and checking real DOM/prices rather than reasoning about it from
the URL alone.

v1.30 — Two threads landed at once: reviews finally have a real,
working, zero-cost pipeline, and Itzik went through
littlesnugg.store/products/baby-carrier-hoodie in much finer detail
than the v1.29 pass, item by item.
1. **Reviews: the free AG Product Reviews app + CJ's own documented
   Method 2 import is now proven working end-to-end**, confirmed
   directly on the real live store — Manage reviews shows "Import
   successfully! 20 of 20 reviews are imported into your store" for
   the carrier, each tagged "CJ Dropshipping." This becomes the
   required default review pipeline (7.C), ahead of the old
   manual-metafield-extraction default, with the paid-app route and
   honest-empty-state unchanged as further fallbacks. The hand-rolled
   `ReviewsSection.tsx`/`MiniReviewCarousel.tsx` components are
   retired in favor of the app's own data — but flagged an open
   question rather than assuming it away: this is a headless Hydrogen
   storefront and AG Product Reviews is a normal Shopify app, so
   whether its review data is actually reachable from the Storefront
   API (metafield/public API) or is Liquid-theme-only needs to be
   checked directly on this codebase before calling reviews "properly
   displayed," not inferred from the app working in Shopify Admin.
2. **Real support inbox now on file**: `support@alphaforbaby.com`.
   7.E's long-standing placeholder-email framing is resolved for this
   store specifically — every `support@[storedomain]` occurrence gets
   replaced with the real address; the placeholder rule itself is kept
   for any *other* future build where Itzik hasn't given a real inbox
   yet.
3. **Section 5's blueprint gained detail from a closer littlesnugg
   read**, confirmed directly (DOM inspection, not memory): 12 real
   `<select>` elements for Color/Size (added as an explicit item-3
   requirement — no styled div standing in for a dropdown), an urgency
   ticker + real-buyer-photo strip above the gallery, a "purchase
   options" row under the primary CTA, a mini review carousel
   immediately after (new item 4), an image+headline card (new item
   7), a size/fit guide (new item 8, conditional on the product
   actually having size variants), a second image+headline card built
   around a real video (new item 10), a 3-video gallery (new item 11
   — with an explicit honesty caveat, since our real CJ sourcing
   typically yields only ONE real supplier video per product, so this
   section must be sized to what's actually real rather than padded
   to match littlesnugg's 4-video count), FAQ questions now require a
   relevant emoji each (item 13, moved earlier in the order), and the
   final reviews grid (item 14, was item 8) is now explicitly what
   Itzik means by "images that speak for themselves" — real attention
   to card size, image clarity, and star-row legibility, not just
   field presence. Footer (now item 17) stays last, as confirmed on
   littlesnugg and as Itzik explicitly restated. Items 4, 6, 8, 9, 11,
   13, and 14's cross-references elsewhere in this skill were updated
   to their new numbers; old item-3/item-8/etc. citations in earlier
   changelog entries above are left as-is (historical, describing what
   was true at that version) rather than retroactively renumbered.
4. **Also noted, not yet executed by this skill update itself**: the
   old clothing catalog needs deleting from the live store, and each
   remaining product's real sourced videos/images need to actually be
   wired in (reusing already-compiled real-asset data) — added as
   Section 11 checklist items so Sol's next pass on any product
   verifies both rather than assuming they're handled.
Added two new Section 12 tests (`test_variant_pickers_are_native_select`,
`test_real_support_email_not_placeholder`) and a fresh Section 11 batch
covering every item above.

v1.31 — Itzik sent real mobile screenshots (390×844) of both
littlesnugg's page and our own dev build, side by side, with a precise
list of mismatches. Checked littlesnugg's actual mobile page directly
(not desktop, which is what earlier versions had been checked on) and
found the real mobile order differs from what v1.30 assumed:
1. **Header, mobile**: littlesnugg has no search bar and no trust-row
   line above the gallery at all — just hamburger + wordmark + cart.
   v1.29/v1.30 said "move or drop" the search bar; v1.31 says drop
   both the search bar and the trust row outright on the product page.
2. **Gallery pagination, mobile**: littlesnugg uses small dot
   indicators, not a scrollable thumbnail strip — corrected Section 5
   item 3 to require dots on mobile (thumbnail strip still fine on
   desktop).
3. **Urgency banner + avatar strip position — corrected**: v1.30 said
   these sit above the gallery; re-checking littlesnugg's real mobile
   page shows they actually sit BELOW the gallery/dots and ABOVE the
   title. Fixed the ordering in Section 5 item 3.
4. **No duplicate product name**: our dev build was rendering a brand/
   store name caption under the thumbnails in addition to the full
   title further down — added an explicit "one title instance" rule.
5. **Rating stars must be gold**, not necessarily `--color-accent` —
   confirmed directly on littlesnugg, added as an explicit exception
   to 8.A.4's "accent repeats everywhere" rule.
6. **Bundle tier badges**: Itzik explicitly wants "MOST POPULAR" on
   Buy 2 (not just "BEST VALUE" on Buy 3) — added, and flagged that
   this should be re-checked against littlesnugg's own live page
   rather than assumed either way, since v1.29's read of littlesnugg
   had no Buy-2 badge.
7. **Per-unit variant selects inside each tier**: confirmed missing
   entirely on our dev build — Buy 2/Buy 3 need their own nested
   Color/Size `<select>` row per unit (littlesnugg's Buy 2 shows two
   full rows), not just one top-of-page picker. Also: Buy 2's selects
   must be visible immediately, not behind an extra click.
8. **New global pricing rule**: every customer-facing price (sell,
   anchor, every bundle tier) must end in `.90`, and it has to be the
   REAL charged amount, not a cosmetic rounding — added as a new
   top-level pricing-display convention (Section 4), with the same
   Rule-1 discipline as everything else (verify with a real test
   cart).
Also independently confirmed, live, via Shopify Admin → Hydrogen
storefronts, why none of this has been visible on the real site:
alphaforbaby.com's Production environment tracks the
`alphaforbaby/production` branch specifically (not `main`, not
`update-display`) — pushing any other branch only creates a Preview
deployment. Production's current deploy is from Aug 28; several
branches (`main`, `alphaforbaby/pdp-conversion-improvements`,
`update-display`) have real unmerged work sitting on them. This isn't
a skill-content change, but it's the reason "I fixed it" and "I don't
see it" have kept talking past each other all build, so it's recorded
here for whoever reads this changelog next.

v1.32 — Sol actually built v1.31's fixes and sent a real, honest
report with live-DOM verification and real test-cart totals — this
surfaced two genuine issues with v1.31 itself, plus Sol correctly
declined to fabricate two claims and asked for a decision instead of
guessing, which is exactly the right call and is recorded here so the
next build doesn't have to re-litigate it.
1. **v1.31's ".90 on anchor_price" requirement was mathematically
   impossible to satisfy honestly.** Sol proved it: doubling or
   tripling a `.90`-ending unit price can never itself end in `.90`
   (always `.80`/`.70`), so requiring an honest `qty × unit price`
   anchor to also end in `.90` forces either a fake anchor or a fake
   charged total. Corrected: `.90` now applies only to the real
   CHARGED total per tier; the struck-through anchor is allowed to end
   in whatever honest multiplication produces. Sol's actual fix — real
   fixed-amount discounts (`−$19.90` at qty≥2, `−$99.80` at qty≥3
   against the $94.90 base) landing exactly on `$169.90`/`$184.90`,
   with the displayed "SAVE X%" rounded DOWN from the real 10.48%/
   35.05% — is now the documented pattern for hitting this convention.
2. **Social-proof number ("JOIN 1000+" style): Sol was right not to
   hardcode littlesnugg's own "1000+ New Mums" figure**, since
   alphaforbaby doesn't have that number — but Itzik's actual
   objection wasn't "invent something," it was "you already know we
   have real CJ review data, use that." Corrected: this component
   must be wired to the real AG Product Reviews count (7.C's
   confirmed-reachable `reviewSummary` data), not hardcoded to any
   fixed figure, real or copied. It'll show a small honest number in
   dev before production is wired up — that's expected, not a defect.
3. **Stock-urgency line ("SELLING QUICK, LOW STOCK") stays unresolved,
   correctly** — Sol flagged that alphaforbaby holds ~40,000 units, so
   an aggregate low-stock claim would be a real Rule 1 violation, and
   asked rather than either faking it or silently dropping the whole
   ticker. Added explicit guidance: check for a real PER-VARIANT low-
   stock signal first (a specific color/size can be honestly low even
   when aggregate stock is high); if none exists at any level, use a
   different genuinely-true line in that slot instead of an aggregate
   low-stock claim.
4. **Accent color — unblocked.** Sol has flagged the bronze
   `#b68235`-on-white accent failing 8.A's own pop test multiple times
   without an answer. Itzik's go-ahead recorded directly in 8.A now:
   pick a genuinely bold accent (doesn't have to be littlesnugg's
   exact pink), stop re-asking.
5. **New 7.D bug #13**: three separate Add to Cart buttons had
   accumulated on the same page (a bundle-tier CTA, a leftover plain
   one, and a leftover inline price+CTA block) — confirmed directly by
   me on the live dev DOM. Added as a named recurring-bug pattern:
   when a buy-box component changes, delete every prior CTA instance
   rather than adding a new one alongside.
Also worth naming as a pattern, not a one-off: twice now (bundle
visual affordance in 7.D bug #11, and this session's pricing/social-
proof/stock items), Sol's honest "I won't fabricate X, here's why,
what do you want instead" has been the right response to a v-next
spec gap — the fix each time was to correct the SPEC, not to override
Sol's refusal. Keep treating a refusal-with-a-real-reason as a signal
to re-check the requirement, not as something to push past.

v1.33 — Itzik tested the real build on his own phone (mobile Safari,
a real Oxygen preview deployment, not a screenshot) and sent three
screenshots scrolling through the actual page. Several things caught
here needed correcting, and one v1.31 spec item turns out to have
been wrong on inspection rather than un-built:
1. **The "selects visible immediately" rule from v1.31 was a
   misreading of a static screenshot, not a tested interaction —
   corrected.** The real required behavior is a true accordion:
   selecting a tier's radio expands ONLY that tier's per-unit rows,
   collapsing any other tier's. v1.31 said "visible immediately, not
   behind an extra click," which the build (correctly, per that
   wording) implemented as ALL tiers' selects always showing — not
   what was actually wanted. Fixed in Section 5 item 3.
2. **New requirement**: each per-unit row inside an expanded tier
   needs a live preview image matching that unit's selected variant —
   Itzik tried this interaction himself and specifically liked seeing
   the thumbnail update per unit as he changed colors.
3. **Product title moves above the gallery — an explicit, deliberate
   divergence from littlesnugg's own order** (confirmed twice now
   that littlesnugg puts it after the image). This is Itzik's call
   for alphaforbaby specifically, not an error to reconcile back.
4. **Sticky bottom mini-cart bar (Section 5 item 18) removed** —
   downgraded from a default requirement to optional/case-by-case,
   since it read as redundant clutter on top of the bundle's own
   contextual CTA and was contributing to the multi-CTA problem in
   7.D bug #13.
5. **Standalone color selector outside the bundle: confirmed STILL
   present** despite being flagged as something to remove in an
   earlier round — recorded explicitly as "not actually done yet,"
   since a repeat report of the same gap means the earlier ask didn't
   land, not that the spec was wrong.
6. **Video must have zero shopper interaction**: no `controls`
   attribute, and a tap on the video must not toggle playback either
   — corrected 7.B Slot 2 (previously specified `<video controls>`,
   which is the opposite of what was wanted) and updated the matching
   Section 12 test to assert controls are ABSENT.
Lesson repeated from v1.30/v1.31: a requirement written from a static
screenshot needs to be re-verified against the actual built
interaction before being treated as confirmed — items 1 and 6 above
were both cases where the written spec was clear but simply wrong,
not cases of the build failing to follow it.

v1.34 — Itzik spotted a large empty gap between the price and the
"Buy more, save more" heading on the real phone build. Checked against
the spec: that's exactly where Section 5 item 4 (mini review
carousel) is supposed to render — it was never actually built at all,
not a case of it existing without a photo. Two fixes: (1) added the
missing-entirely finding directly to item 4's description and a new
Section 11 checklist item so a blank gap in that position gets caught
next time as "section missing" rather than assumed to be normal
spacing; (2) item 4's card now requires a real reviewer photo per
card — v1.30's original wording said "no photo," Itzik confirmed he
wants one, corrected.

v1.35 — Itzik tested the actual v1.34 build on his phone (two real
screenshots) and reversed two of his own prior calls, comparing
directly against littlesnugg's real page again: (1) **the v1.33
"title goes ABOVE the gallery" override for alphaforbaby is
RESCINDED.** That was recorded as "Itzik's own deliberate call, not a
bug" — but having now seen it built and live, he wants the title back
in littlesnugg's real confirmed position: BELOW the gallery, after
the urgency ticker + avatar strip, before the stars. Section 5 item 3
reverted to the pre-v1.33 order for alphaforbaby: image → dots →
urgency ticker → avatar strip → title → stars → bundle. Lesson: an
explicit "this is deliberate, don't correct it back" instruction can
still get reversed once the person sees the real built result — a
later explicit reversal always wins over an earlier "don't touch
this" note, however firmly worded. (2) **The v1.34 mini review
carousel (item 4) is REMOVED for alphaforbaby**, not fixed further —
it had just been built (real reviewer photos, pulling from the same
review source as item 14) per the v1.34 prompt, but Itzik's screenshot
showed he doesn't want a separate carousel section there at all; he
wants the simpler flow matching littlesnugg's real page exactly, with
nothing between the price/bundle block and the urgency/avatar/title
sequence. Item 4 is now optional/case-by-case per store (same
treatment as item 18's sticky bar after v1.33), OFF by default for
alphaforbaby specifically. This is a deliberate user-directed removal
of a section that was just correctly built to spec, not a bug fix —
don't re-add it for alphaforbaby without a new explicit ask. Section
11 checklist items referencing item 4 as required on alphaforbaby are
corrected to reflect it's now off.

v1.36 — Four real screenshots from littlesnugg's actual live page
(mobile) plus a fresh ask on alphaforbaby's own header. Two items
correct/extend v1.35, two are new:
(1) **Item 4 (mini review carousel) is back ON for alphaforbaby — but
v1.35's removal was about the WRONG POSITION, not the section
itself.** A newly confirmed littlesnugg screenshot shows this exact
carousel (small round reviewer photo, 1-sentence quote, name, gold
5-star row, dot pagination) sitting AFTER the entire buy-box block —
below the primary CTA, the purchase-options row, and the trust row —
not in the gap between price and the bundle block, which is where
v1.34 had built it and v1.35 correctly killed. Lesson: "remove the
carousel" (v1.35) meant remove it from THAT gap, which happened to be
the only place it had ever existed; it wasn't a blanket ban on the
section existing anywhere on the page. Re-added at the corrected
position, same design as before.
(2) **Header (item 2), corrected/extended**: littlesnugg's real mobile
header centers its wordmark between the hamburger icon (left) and the
cart icon (right) — not left-aligned. Match that for alphaforbaby:
"ALPHA FOR BABY" centered in the header row. The rotating announcement
ticker (item 1) sits ABOVE this header row as its own strip, never
merged into or below it. Also: remove the sign-in icon that currently
sits inside alphaforbaby's hamburger menu — not requested by anyone,
not part of any prior prompt, and Itzik doesn't want it there (see
also the still-open "sign in / 10% off" popup flagged in v1.35 — this
may be the same underlying customer-accounts feature; Sol should
check whether removing the header icon and the popup are the same
fix or two separate ones).
(3) **New bug: duplicate images in the gallery (7.D)** — Itzik
flagged this directly, no further detail given; Sol should audit the
actual gallery slide list on the live page for repeated images and
remove the duplicates, keeping the required real shot variety (7.A).
(4) **Item 14 (final reviews grid) re-confirmed against a real
littlesnugg screenshot**: full-width real customer photo (product in
use) on top, gold star row, a short bolded pull-quote in quotation
marks as a mini-headline, 1-2 sentences of body text below it, then
the reviewer's name — Itzik wants alphaforbaby's version to match
this exactly. This is the same shape already documented in v1.30;
treat this as a re-confirmation to actually verify the built version
matches, not a spec change.

v1.37 — Another real littlesnugg screenshot plus direct feedback on
the current alphaforbaby build. Three items, none of them new spec —
all re-confirmations or precision fixes on things already documented:
(1) **Header edge spacing**: the hamburger icon must sit flush against
the header's left edge and the cart icon flush against the right edge
— checked against littlesnugg's real computed spacing, not eyeballed.
Also re-confirmed: littlesnugg's own hamburger menu has no sign-in
button at all, so "no sign-in in the hamburger" is the template's
correct default, not just a one-off ask for this store (extends
v1.36's header item). (2) **Urgency ticker + avatar strip, confirmed
STILL MISSING on the real build** — Itzik called this a must-have
after comparing directly against littlesnugg's real page; this block
has been in the spec since v1.30 (position corrected v1.31, data
source fixed v1.32) but apparently isn't rendering correctly on
alphaforbaby today. Treat as a confirmed-missing section, same
severity as the v1.34 carousel bug, not a style note to revisit later.
(3) **Fixed a stale cross-reference**: the "no duplicate product
title" item (Section 5 item 3) still said the one surviving title
instance should sit "above the gallery per v1.33's order override" —
that override was reversed in v1.35, so this line was pointing at a
rule that no longer exists. Corrected to say the title sits below the
gallery/urgency/avatar block, matching the current (post-v1.35) order.
Lesson: when an earlier decision gets reversed, grep the whole file
for other places that cited it by name — v1.35 fixed the primary
override but missed this one secondary reference to it.

v1.38 — Itzik sent the same littlesnugg reference screenshot again
right after v1.37, specifically re-flagging that (1) the product
title still isn't sitting below the gallery/urgency/avatar block on
the real alphaforbaby build, and (2) the star rating still isn't
rendering in genuine gold matching littlesnugg's real page. Neither
is a new requirement — title-below-gallery has been the documented
order since v1.35, gold stars since v1.31 — but both are being
reported as still not matching on the actual live site, which is the
operative fact, not what the code is supposed to do. Logged explicitly
here (rather than assumed covered by earlier versions) because a
requirement that's correct on paper but not confirmed live has, more
than once in this project, turned out to simply not be built yet —
same lesson as the v1.34 carousel and the v1.37 urgency/avatar block.
Section 11 checklist strengthened to require checking both against a
real screenshot of the live page, not the presence of the right code/
props.

v1.39 — Itzik sent 2 real screenshots of alphaforbaby's actual live
Oxygen preview (not littlesnugg this time), saying it still doesn't
match. Checked them directly: **good news first** — the v1.35/v1.38
items are actually fixed now: the product title genuinely renders
below the gallery, and the star rating genuinely renders gold, both
confirmed on the real page. Two real gaps remain, now with direct
visual proof rather than a verbal report: (1) **the header's
hamburger and cart icons are swapped** — hamburger renders at the
RIGHT edge, cart renders next to the wordmark on the left, the
opposite of v1.36/v1.37's hamburger-left/cart-right requirement.
New 7.D bug #15. (2) **the urgency ticker + avatar strip section is
completely absent from the DOM** — the page goes straight from the
gallery dots to the title, confirmed by screenshot, not just Itzik's
earlier report (v1.37/v1.38 already flagged this as "still missing"
based on his description; this is now independently confirmed
first-hand). New 7.D bug #16, elevated from a checklist note to a
named recurring bug since it has now failed to land across three
consecutive rounds (v1.30 spec → v1.37 reported missing → v1.38
reported still missing → v1.39 confirmed by direct screenshot still
entirely absent). Lesson: when the same gap survives multiple "fixed"
reports, stop treating it as a checklist reminder and name it as a
recurring bug with its own number, the same way bug #13 (duplicate
CTAs) and bug #14 (duplicate images) were — a bug that keeps coming
back deserves more visibility than one line in a long checklist.

v1.40 — Two more items from Itzik, both refinements rather than new
requirements: (1) **Sign-in belongs in the drawer, not the header —
clarified, not reversed.** v1.36/v1.37 removed a sign-in ICON from the
header row itself; that stays removed. Separately, Itzik now wants a
"Sign In" button as an ordinary menu item inside the hamburger's
slide-out drawer content — a different UI location that doesn't
conflict with the earlier removal. Also, 7.D bug #15's hamburger-left
fix landed but wasn't pixel-precise; tightened the requirement to
check actual computed CSS, not just relative position. (2) **New bug
#17**: a standalone price renders outside any bundle-tier card,
duplicating what Buy 1's own card already shows — delete it and fix
the resulting spacing, same class of leftover-element bug as #13.

v1.41 — Itzik said "let's go to production." Before recommending that,
independently verified the real live preview (v1.40's deployment,
branch `main`, commit bb280ff) directly in a real mobile browser
rather than trusting the commit messages alone. **Good news: this is
the first round where nearly everything checked out** — header icon
order and edge spacing, the urgency ticker + avatar strip with real
photos, title-below-gallery, gold stars, no stray price, a single Add
to Cart, the mini carousel in its corrected position with stars, and
Sign In inside the drawer are all confirmed working on the real page,
not just claimed. Two real gaps remain, found during this
verification pass rather than reported by Itzik, and he asked for
both to be fixed before deploying: (1) **the "Sign in or create an
account to get 10% off your order" popup is still present**,
overlapping the Buy 1 card on page load — flagged twice already
(v1.35, v1.37) with no root-cause report back; this is now a hard
gate before production, not an optional nice-to-have. (2) **The final
reviews grid (item 14) renders small inline thumbnail photos inside
each review card, not the large photo-forward card design specified**
(a real customer photo filling the top of the card, per the
littlesnugg-matched shape confirmed back in v1.36/v1.38) — the
photos are real, just presented at the wrong size/position. Also
confirmed via Shopify Admin: all of this work has been pushed to
branch `main`, but the alphaforbaby.com production environment tracks
`alphaforbaby/production` specifically (last real deploy predates all
of v1.30 onward) — going live requires merging `main` into
`alphaforbaby/production` and pushing, which is a separate step from
fixing these two items and should happen only after they're both
confirmed fixed on a real screenshot.

v1.42 — Itzik's next instruction, moving beyond the single-product
work: remove the products with no reviews and no trend signal, and
run the same skill-driven build process across the trending products
that do have reviews and video. Checked the live catalog directly in
Shopify Admin rather than guessing: confirmed two clean groups — ~90
legacy clothing SKUs with no real stock and no review evidence
(Archive, per Itzik's explicit choice — not permanent delete, so
nothing is lost if a mismatch turns up later), and 9 CJ-sourced
products with real stock/variants that Itzik confirmed are the
trending set he meant (table now in new Section 2.F, matched by
product ID since these old products' titles are still actively
changing on their own between page loads — do not match by name).
The carrier is done; the other 8 go through Section 3 one at a time,
each first checked for real reviews and real video per-product before
a full build pass, exactly like Section 2.E already requires for any
newly sourced product — being on the confirmed table means "trending"
is settled, not that reviews/video are automatically assumed present.

v1.43 — Itzik's next instruction: rebuild the homepage itself, not a
product page. Checked the real live homepage directly (not from
memory) before writing this: ticker → header → hero (eyebrow,
headline, description, "SHOP THE COLLECTION"/"OUR STORY" buttons,
"1,000+ HAPPY PARENTS" stat, then a large hero image with dot-
pagination — this is the "סליידר של תמונות" he means) → a 4-icon
trust-bar → "Shop by category" (3 generic clothing cards, stale
anyway given the catalog pivot) → an old "Shop All" section (a plain
3-column grid of raw, unedited CJ supplier images, no polish) → a
6-card testimonial grid → footer. New Section 5B documents the
replacement: the hero image slider is deleted and replaced by a real
all-active-products grid (2 per row on mobile) positioned right after
the hero buttons, then the footer comes immediately after that grid.
The trust-bar, "Shop by category," the old raw-image "Shop All" grid,
and the testimonial grid are all deleted per Itzik's own words ("כל
השאר למחוק"). One interpretation call, flagged rather than assumed
silently: the hero copy block itself (eyebrow/headline/description/
buttons/stat) stays — only the image slider is what's being replaced,
since that's the specific thing he named ("במקום סליידר של תמונות").

v1.44 — a dense round of real fixes on the actual live hip-carrier
page (checked directly, not from a report) plus two site-wide items.
Confirmed via direct DOM/text check: the contact page's "Business
details" section literally reads "ALPHA FOR BABY is operated by ALPHA
FOR BABY, registered in Israel." — Itzik wants that phrase gone.
Confirmed the homepage (independent of the v1.43 rebuild already
handed to Sol) has excess spacing throughout, per Itzik's own
complaint — folded a general tightening note into Section 5B. On the
product page itself, checked the real live page end to end at the
same time as reading Itzik's list, and every item on his list matched
something actually still wrong: the top ticker is long (full spelled-
out payment-brand list as one item) and scrolls too fast to read; the
sub-header trust row that Section 5 item 2 already asked to be
removed back in v1.31 is STILL rendering above the gallery — that's a
real regression/never-fixed gap, not a new ask; the urgency-badge
block below the gallery (7.D bug #16, fixed for presence in v1.39) is
rendering the WRONG copy — trust-badge text instead of "SELLING
QUICK, LOW STOCK"; the avatar-strip photos have no checkmark badge
(Itzik specifically likes this from the reference); the trust-text
line under Add to Cart ("Free shipping (7–25 business days)" / "30-
day easy returns" / "Guaranteed Safe & Secure Checkout") duplicates
the ticker/sub-header messaging Itzik already flagged as clutter; the
bundle still shows all three tiers where Itzik now wants only Buy 1/
Buy 2; the mini review carousel cards have a visible border Itzik
wants removed; and the real product-demo video sits many sections
below the mini carousel instead of right after it. Also folded in a
standing instruction: get this exact page (the anchor
ergonomic-baby-hip-carrier build) fully corrected first, then use it,
as corrected, as the literal visual reference for every other product
page in the store — this doesn't replace Section 2.F's build order,
it sets the bar each of those builds must now match.

v1.44 follow-up — independently verified on the real deployment
(Sol's own report named the exact commit/preview; checked that build
directly, not the report). 10 of 12 items confirmed genuinely fixed
on the live page: contact-page text, ticker content/speed, sub-header
trust row removal (bug #19 — this one took three versions, v1.31 to
v1.44, to actually land), avatar checkmarks, star size/spacing,
2-tier bundle, borderless mini carousel, video repositioned right
after it, and the redundant CTA trust text removed. Item 5 (urgency
copy) is a genuine open decision, not a dropped task — Sol declined
to write literal "SELLING QUICK, LOW STOCK" because this product
holds ~40,000 real units and Rule 1/Rule 2 already forbid fabricated
scarcity claims (the same objection raised on this exact line 3 times
before, v1.32/v1.37/now). Shipped an honest alternative instead
("⚡ POPULAR — RATED 5.0 BY 20 BUYERS") and asked Itzik to pick: ship
the literal wording anyway as conventional copy, wire a real
per-variant stock signal, or keep the honest line as-is — this needs
Itzik's answer, not another round of the same flag. One item is a
real, still-open miss: the "Sign in / 10% off" popup (7.D bug #18) is
now on its 4th flagged round (v1.35, v1.37, v1.41 production gate,
now v1.44) with still no root-cause explanation — this stays a hard
gate before any production merge. Also noted, low priority: the old
Buy-3 quantity discount is still configured in Shopify even though
the UI tier is gone — harmless but worth Itzik confirming whether to
delete it.

v1.45 — Itzik's decision on the one open item from v1.44's follow-up:
ship the literal "SELLING QUICK, LOW STOCK" urgency wording, scoped
as a deliberate override of the aggregate-honesty concern for this
one line specifically (Section 5 item 3's v1.45 note has the full
framing — this doesn't relax Rule 1/Rule 2 anywhere else). The other
two open items from that follow-up stand as asked: the "Sign in /
10% off" popup (7.D bug #18) is still an unexplained, 4-times-flagged
production gate, and the stale Buy-3 Shopify discount is still
pending a yes/no from Itzik on deleting it.

v1.46 — Itzik reported two things weren't done; checked both directly
against the latest real deployment and both are confirmed real, not
a perception issue. (1) Homepage spacing (asked in v1.44): Sol's
report claimed it was fixed, but the real page still reads generously
spaced around the hero stat and the footer — either the change didn't
ship or wasn't enough; needs an actual re-check with real computed
values, not a repeat of "done." (2) Homepage product grid (Section
5B item 4, v1.43): still hardcoded to the same 3 products the old
"Shop All" section had, not a live query against all active products
— new 7.D bug #26. (3) The bigger finding, from checking why the grid
still shows only 3: none of the 8 remaining trending products
(Section 2.F) have been through a Section 3 build pass at all. Opened
Glow Whale Bath Buddy's real live page directly — it's the unbuilt
default Shopify template: broken gallery, no buy box, no urgency/
avatar/mini-carousel sections, the description literally renders
```html code-fence syntax as visible text (7.D bug #7, recurring),
raw unmapped CJ spec fields shown verbatim, and zero reviews despite
being on the confirmed-trending table. All of Sol's effort since
v1.35 went into the carrier page specifically; Section 2.F's
one-at-a-time build-out of the other 8 never actually started. Now
that the carrier page is in good shape, this is the real priority.

v1.47 — Itzik reported both v1.46 items still weren't right; checked
the newest real deployment (a third push had landed since, "homepage
density fix + description fence/spec cleanup") with actual measured
numbers this time, not eyeballing screenshots. Homepage footer gap
DID genuinely shrink — measured directly: padding-top 60px→36px,
margin-top 72px→32px, a real ~48% cut — so this wasn't a no-op, but
it's evidently still not tight enough for Itzik; push it further
(see Section 5B's v1.47 note for a concrete target this time instead
of leaving "tighter" open to interpretation again). On the products:
confirmed decisively this is a real, serious gap, not a
misunderstanding — the same commit that touched Glow Whale Bath Buddy
only patched the two exact symptoms named in the v1.46 prompt (the
markdown-fence text is gone, "Package contents"/"HAVE_MAGNETISM" are
now "Packaging"/"Contains magnets") and touched nothing else: gallery
still completely blank, still no bundle/buy-box, no urgency/avatar
strip, no mini carousel, still zero reviews. That's cosmetic text
cleanup, not a Section 3 build pass. The next prompt needs to say
this explicitly and unambiguously, not just re-ask for "the build."
v1.48 — Itzik asked whether a skill/agent exists to pull real CJ
reviews into the store per Section 7.C's guide; confirmed it's already
documented (Method 2, since v1.30) and Cowork (the separate session
with live browser access to CJ Dropshipping and Shopify Admin) offered
to run the import directly rather than waiting for Sol, for the 7
remaining unblocked trending products (all of Section 2.F's table
except the carrier, already built, and Glow Whale Bath Buddy, paused
on its own real-defect finding — see that product's own note below).
Cowork found and image-matched the real CJ listing for the **Foldable
Portable Baby Crib** (21 real third-party reviews, all positive, no
defect pattern like Glow Whale's) — confirmed URL below — but hit a
hard blocker actually clicking "Import" inside the AG Product Reviews
app in Shopify Admin: the click never registers, tried roughly 8
different ways (fresh tabs, double-click, keyboard Enter, closing
interfering banners) over multiple minutes. The same session's clicks
work fine on CJ Dropshipping pages and on the top-level Shopify admin
chrome (the global search bar responded normally) — only clicks
*inside* Shopify's admin/storefront iframe content failed, including
an unrelated popup's close button on the live storefront, which points
to a Chrome site-permission/extension issue specific to Shopify's
domains in that browser session, not a data or logic problem, and not
something Cowork can fix on its own (it would need Itzik to
re-approve/refresh site access in that Chrome extension). Itzik's
call: don't keep fighting the browser tooling — hand the actual import
step back to Sol, same as the rest of Section 2.F/7.C's per-product
pipeline. **Confirmed CJ source, ready to import as-is (Section 7.C
Method 2 — Collect reviews → Import → paste this URL → Import):**
Foldable Portable Baby Crib (7655354105927) →
`https://cjdropshipping.com/product/crib-anti-pressure-newborn-foldable-portable-crib-middle-bed-baby-infant-mattress-bionic-travel-bed-p-1382224137270988800.html`
(matched by product photo — same locomotive-style nest-in-crib image,
same 20-style A-T color/print options as the live Shopify variants).
For the other 6 unblocked products in Section 2.F's table (Automatic
Domino Train Set, Montessori Shape Sorting Egg, Toddler Sensory
Learning Board, Baby Beach Sun Shelter, Foldable Baby Bed Canopy Set,
Cozy Portable Baby Nest), Sol still needs to do the real CJ
source-and-review check itself (2.D's "attempt this yourself first"
browser-automation/credentialed-session workflow, or a human hand-off
per 2.D/2.E if genuinely blocked) — Cowork's own attempt at the Domino
Train Set specifically did NOT reach a confident match (CJ's reverse-
image search returned a same-category-but-different-toy result, a
blue robot-style domino pusher instead of the live page's purple/clear
locomotive with orange wheels) and was abandoned rather than risk
importing another product's reviews onto the wrong item (Rule 1) —
this one still needs Sol's own sourcing-stage pid, not a guess from an
image search.
v1.49 — Itzik reported that the "done" round wasn't done well and
introduced new mistakes, that the stars "look like they're on top of
each other," that the objects he asked for still aren't all there,
that the homepage still has too much space, that every product page
must look exactly like the carrier's, and that the font still wasn't
changed — plus a pointed structural criticism: "כאילו הסקיל לא מספיק
כתוב טוב" (the skill isn't written well enough). He's right about the
skill: it described the ideal page in prose but never forced a
component-by-component diff of a new product page against the built
carrier page, which is exactly the gap every round has fallen into.
Fixed in this version by adding **Section 5C — PDP PARITY GATE**: a
21-row component table taken from the carrier page as it actually
renders, to be reported row by row, measured on the rendered page,
before any product page is called done. Everything else in this entry
was measured directly on the real dev build (localhost:3001, 375px
mobile), not inferred: **stars** — two 5-star rows at the same y with
different geometry (base 5 × 20px at pitch 20px; gold overlay 5 ×
19.1px at pitch 19.1px), drifting ~0.9px per star to a ~3.5px offset
by star 5, which is the doubled/jagged look Itzik is seeing (7.D bug
#27); **font** — the Google Fonts link and the font-family are both
in place, but the response CSP's `style-src` omits
`fonts.googleapis.com` and there is no `font-src` at all, so
`document.fonts.size === 0` and a rendered-width test shows the text
falling through to `system-ui`, i.e. the font genuinely never
changed, same bug class as the Aug 28 clarity.ms CSP fix (7.D bug
#28); **buy box** — the crib and Glow Whale pages render no price, no
`<select>`, no Add to Cart and no bundle anywhere in the DOM, while
the same page's JSON-LD carries the real $152.90, so it's a
product-gated code path, not missing data (7.D bug #29);
**reachability** — 6 of the 9 trending products 404 on the storefront
and `/collections/all` returns only 3, which also re-explains the
homepage grid's 3 cards and partly retracts v1.46's "hardcoded grid"
diagnosis (7.D bug #30, and the correction appended to bug #26);
**homepage density** — v1.47's footer target was actually MET (20px
padding + 12px margin = 32px combined), so the remaining space is
elsewhere and is now specified with real numbers: a 555px hero on an
812px viewport and a 760px footer block, with per-gap targets in
Section 5B's v1.49 note. Reviews are the one thing that genuinely
landed this round (carrier 4.8/60, crib 4.8/23, real reviewer data) —
Section 2.F's v1.49 note says so explicitly so the next round doesn't
redo it.
v1.50 — Itzik asked the right question: "why doesn't he do the work
properly on the other products when he did it properly on the
Ergonomic Baby Hip Carrier page?" — and said the part of this skill
that assumes Sol "already knows the recipe" is missing a lot of
explanation and a lot of the pytest coverage he asked for. Both are
now answered from the actual codebase rather than guessed. **Root
cause, read directly out of `app/routes/products.$handle.jsx`: there
is exactly ONE product-page template, it is fully generic, and it is
not carrier-specific. Every persuasion section on it renders from one
key of a single per-product Shopify metafield, `custom.pdp_content`
(loaded as `content: safeJson(product.pdpContent?.value)`), and every
one of those components returns `null` when its key is absent.** The
carrier's metafield is authored; the other products' are not. That is
the entire difference between "built" and "empty" — so for every
product after the first, the work is DATA AUTHORING, and a report
that the page's components exist is describing the template, which
was already true before the round started. Documented as the new
**Section 5D — THE PER-PRODUCT CONTENT CONTRACT**, with the exact
field-by-field schema (every field name verified against the
component that reads it), the carrier's real values as the worked
reference, the per-field honesty rules (`amountOff` must match a real
Shopify discount; `icon` must be one of the five mapped names;
`imageIndex` is an index into THAT product's own gallery; `comparison`
renders only with both halves; `whyItWorks`/`guarantee` render only
with `text`), and the 7-step authoring recipe. **Second root cause,
also verified: the compliance suite only ever tested one product** —
`PRODUCT_HANDLES = ["ergonomic-baby-hip-carrier"]` with a comment to
add handles by hand — so every run came back green while the crib and
Glow Whale rendered with no buy box at all. Fixed in Section 12:
`PRODUCT_HANDLES` is now derived from the live `/collections/all`
catalog at collection time, and the suite grew from 4 classes to 10
(47 tests) with `TestCatalogCoverage` (fails when a trending product
is missing from the live catalog, or an unexpected one appears),
`TestPdpContentContract` (one test per `pdp_content` key, each
assertion naming the metafield key to write rather than a code
change), `TestNoSkeletonPages` (h2-section count and page weight
against the reference page) and `TestHomepageDensity` (hero ≤420px,
footer block ≤460px, footer top gap ≤36px at 375px width — the
numbers Itzik has now reported four rounds running, as assertions).
Also verified this round: Sol had already landed real fixes for 7.D
#27 (StarRating rewritten per-star, no second row) and #29 (a simple
buy-box fallback, so the crib and Glow Whale now render $152.90 /
$40.90 with a working Add to Cart) — those two are genuinely done and
should not be re-opened; what is still missing on those pages is
exactly the `pdp_content` data.
v1.51 — Itzik asked for a full pass over every product page against
the carrier, and flagged that the bundle is missing and that a page
says out of stock. Audited all 9 on the real dev build at 375px; the
per-product table is in Section 2.F. Reachability is genuinely fixed
(all 9 return 200, the windowed gallery dots + "1 / 17" counter
landed, the star row is one clean row, and six products now carry
authored `urgencyLine`/`benefits`/`whyItWorks`/`faq`/`guarantee`).
Five new blockers, and the two biggest are Shopify-data problems
rather than code: **7.D #31 — six of nine products have 0-of-N
variants available for sale** (verified against Shopify's own
`/products/<handle>.js`: carrier 12/12, crib 20/20, whale 2/2, but
Domino 0/6, Egg 0/10, Board 0/30, Shelter 0/8, Canopy 0/8, Nest
0/16), so the storefront correctly renders "— sold out" on every
option and drops the CTA; Admin shows "Inventory is not tracked at
any location" with null inventory management on those variants.
**7.D #32 — those same six kept CJ's per-variant cost spread instead
of one approved retail price**, and the Domino sells at $4.90 against
a ~$10.54 landed cost ($1.99 item + $8.55 shipping, from its own CJ
listing) — a loss per order, so pricing goes back to Itzik per
Section 2.E rather than being "fixed" silently. Also: **#33** the
crib's 23 real reviews regressed to "Be the first to review this
product" within the same day; **#34** no `quantityTiers` on any
product but the carrier, which is exactly the missing bundle Itzik
saw; **#35** every review photo store-wide is a dead hotlink to
`cc-west-usa.oss-us-west-1.aliyuncs.com` (0 of 16 load on the
reference page itself), which both breaks the avatar strip's faces
and puts the supplier's CDN in every page's DOM against 7.D #6. The
suite grew to 11 classes / 52 tests, including `TestV151Blockers`,
which checks Shopify's own product JSON for availability, one retail
price per product and `.90` endings — because the Hydrogen page was
rendering the bad data perfectly correctly, and no page-level test
could ever have caught that.
v1.52 — Itzik asked why this file "missed" the tier bundle, given
that it's the best-looking block on the carrier page and it's absent
on all eight other products. Checked, and the honest answer is that
the spec didn't miss it: Section 5 item 3 has required the same-SKU
Buy 1 / Buy 2 block for EVERY product regardless of `store_mode`
since v1.29, and Section 11 carries it. What failed is everything
downstream. The repo's `tests/conftest.py` is still the v1.25 file:
it defaults `--store-mode` to `multi_product_niche` and its docstring
still claims alphaforbaby wants a cross-sell bundle "rather than
same-SKU quantity tiers" — the exact branch v1.29 retired. And the
tier tests are written to `pytest.skip("no quantity-tier block on
this product")` when the block is absent, as does the cross-sell
bundle test. So a product with no bundle produced green skips, never
a failure, for round after round. Recorded as 7.D #36 with a rule
that outlives this one bug: **`pytest.skip()` may never stand in for
a missing REQUIRED element** — skip means "not applicable to this
product", and anything else must fail and name the metafield key or
Shopify setting that fixes it. Added `TestBundleRequired` (4 tests:
the block exists, it isn't the v1.49 fallback box, Buy 2 is badged
and the CTA names the quantity, and every charged tier total ends in
`.90`), bringing the suite to 12 classes / 56 tests, and included the
corrected `conftest.py` fixture inline so the stale one gets replaced
rather than patched around.
v1.53 — Itzik's explicit layout decision: move the full "Ratings &
Reviews" block up to sit directly under the product video, ahead of
the benefit sections, instead of at the very bottom of the page.
Recorded in Section 5C (new row 15b; row 20 retired) with the full
resulting section order, applied to the one shared template so all 9
products change together, `id="reviews"` preserved for the star
row's anchor link. Supersedes every earlier "reviews last" note.
Added `TestReviewsUnderVideo` (reviews below the video and above
"Why parents choose it"; reviews above the guarantee), checked by
rendered vertical position rather than JSX order.
v2.0 — Restructured into levels at Itzik's request. The single
6,000-line file became a short entry point (`store-builder-trending-cj.md`:
description, reading order, and a traffic-light board of what's developed
and finished vs. not) plus 15 files in `store-builder-trending-cj/`, named
`{level}-{name}.md`. No rule was removed or reworded — the split was
verified line by line against v1.53, and the pytest suite in Level 14 still
compiles. Original section headings are kept inside each level so
references like "7.D #31" and "Section 5C" keep working.
v2.1 — Two new rules from Itzik. (1) Review gate (Level 01 rule 7,
Level 02 Section 2.G): a product is uploaded and displayed only with at
least 15 real reviews that each carry a real photo — counted only when the
photo is re-hosted on Shopify's CDN and loads. Below 15 it is hidden
(Draft/unpublished, never deleted). Measured on the dev build: carrier 60,
sorting egg 36, domino 19 pass; canopy 13, nest 11, learning board 4, sun
shelter 3, crib 1, Glow Whale 0 fail — so 3 of 9 stay live. (2) Hero image
rule (Level 01 rule 8, Level 09 Section 7.A.1): the first image is chosen
with markitdown + a vision-model OCR prompt and must not be pixelated
(short side >= 1000px, Laplacian variance >= 100), must contain no Chinese
characters, and should show a person using the product when a clean one
exists; the decision is saved per product as JSON. Also confirmed while
measuring: review photos are now re-hosted on cdn.shopify.com (7.D #35
addressed) and the crib's 23 reviews are back (7.D #33). Added
TestReviewGate, TestHiddenProductsStayHidden and TestHeroImage — suite now
16 classes / 65 tests.
v2.2 — Corrected the v2.1 hero-image rule, which was written wrong:
it let customer review photos compete for the hero, and all three live
products (carrier, sorting egg, domino) ended up with a review photo as
their hero. Itzik's actual rule, now in Level 01 rule 8 and Level 09
Section 7.A.1: product images — gallery and hero — come ONLY from the
product's own CJ listing. Stage 1: every CJ image passes markitdown + OCR
(not pixelated, no Chinese text) BEFORE it is uploaded; failures are never
uploaded. Stage 2: the hero is picked from those, preferring a person using
the product. Review photos stay in the reviews section only. TestHeroImage
now fails on any non-CJ source or review photo in the gallery, and on any
uploaded image that didn't pass stage 1 (16 classes / 68 tests).
v2.3 — Pricing rule (Level 03): an outside review found prices far above
market — domino $53.90 vs $19.99–$25.19 at Walmart, matching eggs $58.90 vs
$7.99 (Walmart) / $39.97 (boutique), hip-seat carrier $94.90 vs $25.99–$59.99
(above Momcozy at $49.99). Itzik decided on roughly 20% gross margin. Every
price is now: landed CJ cost + 2.9% + $0.30 fee → 20% price rounded up to
.90, checked against >= 3 market comparables and never above the median;
Buy 2 also >= 20%; "Cost per item" filled in Shopify; recorded per product
in store-profiles/alphaforbaby/pricing/<handle>.json and approved by Itzik
before it ships. Added TestPricingRule (17 classes / 71 tests).
v2.4 — v2.3's pricing rule applied to all 3 live products, real landed cost
per variant from the CJ API (item price + freightCalculate shipping,
dated), written into Shopify's Cost per item on every variant. Domino:
worst-variant landed $18.26, 20% price $24.90, market median $29.99 (3+
Walmart/brand comparables) — viable, applied. Carrier and egg: the 20%
price ($42.90, $26.90) came back above their market medians ($29.99,
$15.49) and were reported as not viable per Level 03 step 5 — Itzik then
explicitly overrode that guardrail and instructed both applied anyway.
Done: prices set on every variant, Buy-2 tiers resized to the new prices
(domino $47.90/$1.90 off, egg $52.90/$0.90 off — both re-verified >=20%
margin at 2 units), `approved_by_itzik: true` recorded with the override
noted in each JSON. The carrier's Buy-2 could not be preserved at $42.90 —
2x gross ($85.80) is only $0.48 above the 20%-floor total ($85.32), and
.90-ending totals are $1.00 apart, so no value is both a real discount and
above the floor — the bundle was removed (Shopify automatic discount
deleted, `quantityTiers: []`) rather than faking a discount or breaking
the margin. Registered in `tests/conftest.py`'s new `NO_BUNDLE_HANDLES`
(distinct from `PAUSED_HANDLES` — the carrier is live and built, just
without a Buy-2). `TestPricingRule` added to Level 14's own spec, adapted
so `NO_BUNDLE_HANDLES` products skip the Buy-2 margin check instead of
crashing on a null `buy2_total`. Real run: **144 passed, 14 skipped, 2
failed in 1:13** at `-n 4` — the 2 failures are
`test_not_above_market_median` on the carrier and egg, which is the test
correctly reporting Itzik's override, not a defect; nothing here should be
"fixed" by weakening that assertion. Also fixed in the same pass: found
and re-hid 3 review-gate products (nest, canopy, Glow Whale) that had been
silently re-published to Online Store/alphaforbaby by something in the
org's automation (most likely the CJ stock sweep, which predates and
doesn't know about the v2.1 review gate) — this is a real coordination
gap between two systems, not yet fixed at the root, only caught and
corrected here. Also fixed `TestHeroImage`'s two tests crashing with
`TypeError` on a product with a recorded `chosen: null` (the carrier and
domino, both `blocked_no_compliant_image` from v2.2's hero rework) — they
now skip with the recorded reason instead of erroring, matching this
codebase's rule that every skip must be a recorded decision, not a crash.

