<!-- Level 10 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 7.D. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

## 7.D — Known recurring bugs (check for these explicitly, every build)

Each of these was found independently in a separately-forked store build
(not caught by copying an earlier fix), which means fixes are NOT
propagating upstream between forks on their own. Check for all of them
explicitly before shipping, regardless of which template/fork you started
from — and if you find and fix a new bug of this shape, append it here
with the same three parts (symptom / cause / fix) so the next build
checks for it too, instead of re-discovering it from scratch.

1. **Star rating renders even at zero reviews.** Symptom: the page shows
   a literal "0.0 (0 reviews)" star row on a brand-new product. Cause: the
   star-rating component renders unconditionally instead of checking
   `review_state`. Fix: only render the star row when `review_state` is
   `app_imported_real`; when it's `empty_honest`, show the Section 7.C
   empty state instead (no star row at all).
2. **Brand name duplicates itself in cart/CTA text.** Symptom: a line
   like "Furlo Furlo GroomVac" instead of "Furlo GroomVac". Cause: a
   component naively concatenates `{brandName} {productName}` even when
   `productName` already includes the brand (e.g. `product_name_working`
   was written as "Furlo GroomVac", not just "GroomVac"). Fix: check
   whether `productName` already starts with `brandName` before
   concatenating; if so, use `productName` alone.
3. **Lifestyle photo text overlay goes illegible.** Symptom: a headline
   overlaid on a full-bleed lifestyle photo (Section 5, item 9 as of
   v1.30, was item 6) is hard to
   read against a bright region of that specific photo. Cause: a single
   fixed-opacity flat wash (e.g. `bg-black/25`) applied uniformly,
   regardless of the photo's own tonal range. Fix: use a gradient scrim
   (transparent fading to dark, anchored behind the text specifically)
   rather than one flat opacity value assumed to work for every photo.
4. **A badge meant to overflow a card's edge gets clipped invisible.**
   Symptom: found on `react-store-template`'s bundle-tier "Most
   Popular"/"Best Deal!" badges (v1.10-v1.12) — the badge rendered in
   the DOM and passed a type-check, but was visually reduced to an
   unreadable sliver. Cause: the badge was absolutely positioned to
   straddle the parent card's top border (`-translate-y-1/2` past the
   edge), while the same parent card had `overflow-hidden` set (for an
   unrelated reason — clipping a different child's corners). Fix: don't
   position a badge/callout to overflow a container's bounds if that
   container (or any ancestor) has `overflow-hidden` — either move the
   badge fully inside the bounds, or get the rounded-corner clipping
   some other way (round the specific inner element's own corners
   instead of relying on the parent's `overflow-hidden`). This is
   exactly the class of bug a type-check or a successful build cannot
   catch — only an actual rendered screenshot does (Section 11).
5. **A decorative background layer (blobs, texture) wrapped in `relative
   overflow-hidden` renders completely invisible, even at opacity:1 with
   blur removed.** Symptom: `GradientBlobs` (or any `-z-10`, absolutely
   positioned decorative layer) placed as the first child of a
   `relative overflow-hidden` section, with that section's own
   background color set — zero trace of it shows, at any opacity, with
   or without blur; only found by forcing the blob's opacity to 1 and
   removing blur entirely and STILL seeing nothing. Cause: a subtle,
   easy-to-get-wrong point of the CSS painting-order spec — a
   `position:relative` element with no explicit `z-index` (`z-index:
   auto`) does NOT establish its own stacking context. Without one, the
   wrapper's own background is painted at the stacking-context step for
   "positioned, z-index:auto descendants" (step 6) of whatever ancestor
   DOES establish a context (often several levels up, even the page
   root) — which comes AFTER "negative z-index descendants" (step 2,
   where the `-z-10` blob layer lands). Net effect: the wrapper's own
   background paints on top of its own decorative child, despite being
   earlier in the DOM. A type-check and a successful build both pass;
   only a real screenshot (or `getComputedStyle`/`elementFromPoint`
   probing, which is how this was actually diagnosed — pixel-sampling a
   screenshot alone wasn't enough to distinguish "too subtle to see"
   from "not painting at all") reveals it. Fix: add `isolate`
   (`isolation: isolate`) to the wrapper — this forces it to establish
   its own stacking context, so step 1 (its own background) reliably
   paints before step 2 (its `-z-10` children) within that same
   context. `className="relative overflow-hidden"` is NOT sufficient
   for this pattern; it must be `className="relative isolate
   overflow-hidden"`. Updated `BackgroundEffects.tsx`'s own doc comment
   to say this explicitly so the next usage doesn't drop it.
6. **Supplier/sourcing identity leaks onto the storefront.** Symptom:
   a CJ-branded SKU string (e.g. `CJWJYEYE02075-Blue`) visible in a
   product-details table, a hotlinked `cjdropshipping.com`/
   `cf.cjdropshipping.com` image or video `src`, a vendor/tag field
   naming the supplier, or a mention in meta tags/JSON-LD. Cause: fields
   copied straight from `product/query`'s response (SKU, vendor) without
   relabeling, or images/video referenced directly from CJ's CDN instead
   of being downloaded and re-hosted on the store's own CDN. Fix: before
   calling a product page done, check rendered `document.body.innerText`
   for "CJ"/the supplier name, check every `img`/`video` element's `src`
   domain, and check `<head>` meta + JSON-LD — none of these should
   surface the supply chain. Re-host every asset (7.A/7.B already require
   this for review photos; it applies to every image/video on the page).
7. **Raw markdown syntax rendered as literal page text.** Symptom: a
   literal ` ```html ` or a stray ` ``` ` visible in the rendered
   Description or other copy block. Cause: copy was generated/written in
   markdown but the component displays it as plain text/JSX without
   running it through a markdown renderer (or a leading/trailing strip
   that only handles the fence at the very start/end, missing one
   embedded mid-content). Fix: either write copy as plain text/HTML from
   the start, or actually render markdown to HTML — verify by reading the
   rendered DOM's text content, not the source you wrote, since a
   fence marker anywhere in that text means it leaked.
8. **A CJ spec field is mapped to the wrong display label.**
   Symptom: a "Package contents" row showing "Plastic bags". Cause:
   `packingNameEn` is the packaging *material*, not package *contents* —
   an easy field-name confusion. Fix: pull actual package contents from
   the free-text description/overview fields, never from `packingName`/
   `packingNameEn`; spot-check every mapped spec field against what it
   actually says on the real CJ page, not just what its field name
   implies.
9. **A dead UI element inherited from a prior template keeps rendering.**
   Symptom: a "360°" photo-spin badge (or similar) shown on a product
   with no such asset, left over from adapting an older template built
   for a different product category. Cause: patching/extending an
   existing component instead of rebuilding it for the new product type,
   so unrelated leftover UI never gets an explicit removal pass. Fix:
   when a template no longer matches the product category, rebuild the
   specific component from this spec rather than conditionally hiding
   the old one — delete the dead code, don't branch around it.
10. **A brief field is declared but never actually consulted anywhere.**
    Symptom: `store_mode` (`single_hero_product`/`multi_product_niche`)
    sat in `store_brief.json`'s schema with no section of this skill
    ever branching on it, so every build got the single-hero bundle
    shape regardless of the store's real shape — no error, no failing
    check, just silently the wrong output for a multi-product catalog.
    Cause: a field gets added to a schema as documentation of intent
    without being wired into the logic that's supposed to read it. Fix:
    when auditing whether a spec covers something, grep for where a
    field is actually *used*, not just where it's *declared* — a field
    that only appears once, in its own definition, is dead.
11. **A control is functionally correct but has zero visible affordance
    as a control.** Symptom (found on the v1.27 bundle rebuild): the two
    removable bundle items each got a real `<button role="checkbox">`
    (correct `aria-label`, `aria-checked`, `cursor: pointer`, and
    clicking it genuinely recomputes the cart/discount tier — verified
    directly, not assumed) — but it rendered as a plain 20×20px orange
    checkmark square, visually IDENTICAL to the non-interactive `<span>`
    checkmark next to "this item" (which can't be removed). Itzik
    reported "I don't see the bundle buttons, there's only Add to Cart"
    — he wasn't wrong: nothing on screen signals that two of the three
    checkmarks are clickable and one isn't; a working control that looks
    like inert decoration might as well not exist for the person looking
    at it. Cause: `role="checkbox"` and a click handler satisfy a
    pytest/DOM check (and did — `test_bundle_matches_store_mode` passed)
    but say nothing about whether a human perceives the element as
    interactive; visual affordance was never actually checked, only
    behavior. Fix: give real interactive controls in a bundle/toggle list
    a visibly different treatment from any adjacent non-interactive
    marker — e.g. the fixed "this item" marker as a flat filled/"locked"
    icon with no pointer cursor and a muted tone, the two removable ones
    as an outlined checkbox with a visible hover/focus state (background
    or scale change) and a minimum ~32-40px touch target — and add a
    Section 11 human-visual check for this specifically: "does a control
    that does something LOOK different from one that doesn't, without
    having to click it to find out." A passing automated test for
    behavior is not evidence the control is discoverable.
12. **A sourced supplier image used as a gallery slide is actually a
    multi-inset marketing composite, not a single clean shot.** Symptom:
    alphaforbaby's carrier page slide 1 has a small inset photo of a
    person merged into the same frame as the main product shot — found
    by directly comparing it against a live competitor's gallery
    (littlesnugg.store), where every slide is one clean subject. Cause: a
    CJ listing photo pulled and used as-is without checking whether it's
    actually a single product/lifestyle shot or a supplier-made composite
    collage (CJ listings often mix these in the same numbered image set
    with no metadata distinguishing them). Fix: visually inspect every
    candidate hero/gallery image before using it — a composite with more
    than one distinct photo stitched into one frame gets cropped to a
    single subject or replaced, never used whole as slide 1.
13. **Multiple redundant Add to Cart buttons accumulate on the same
    page.** Symptom (found on the v1.31 bundle rebuild): three separate
    "Add to Cart"-style buttons rendered simultaneously on one product
    page — a bundle-tier CTA ("ADD 3 TO CART," correctly tied to the
    selected tier), a second plain "ADD TO CART" directly below it, and
    a third inline "$94.90 · ADD TO CART" block further down, none of
    them removed as the page evolved. Cause: each iteration of the
    bundle/buy-box block was added without deleting the previous
    iteration's CTA, so old and new versions coexist instead of one
    replacing the other. Fix: a product page gets exactly ONE primary
    Add to Cart control, tied to whatever tier/variant is currently
    selected — when adding or restructuring a buy-box component, grep
    the page for every "Add to Cart"/"Add N to Cart" string and delete
    every instance except the one true CTA, don't just add a new one
    alongside.

14. **Duplicate images in the gallery.** Symptom (flagged directly by
    Itzik on alphaforbaby, v1.36): the same photo appears twice among
    the gallery slides. Cause: not yet root-caused — check whether the
    image-selection step is pulling the same CJ source photo into two
    slide slots, or whether a "fallback" image is being appended even
    when a real distinct one already fills that slot. Fix: audit the
    actual rendered gallery slide list (compare image `src`/asset IDs,
    not just how many slides exist) and remove any repeated image,
    keeping the real shot-list variety required by 7.A.

15. **Header icon positions swapped/wrong.** Symptom (confirmed directly
    from real screenshots of alphaforbaby's live Oxygen preview, v1.39):
    the hamburger menu icon renders at the header's RIGHT edge and the
    cart/checkout icon renders immediately next to the wordmark on the
    LEFT/center, instead of the required hamburger-left/wordmark-center/
    cart-right layout (v1.36/v1.37). Cause: not yet root-caused — check
    whether the header component's icon order in markup/flex order was
    never actually changed, or whether it was changed but a CSS
    `flex-direction`/`order` rule elsewhere is reversing it. Fix: verify
    on the real rendered page (not just the source) that hamburger sits
    flush at the true left edge and cart flush at the true right edge.
    **v1.40 — a first fix landed but wasn't precise enough**: hamburger
    is now roughly on the left, but Itzik wants the actual CSS tightened
    so it's genuinely flush against the true left edge (check computed
    spacing directly), not just "on the left side" with leftover margin/
    padding still offsetting it.

16. **Urgency ticker + avatar strip section entirely absent from the
    real page — confirmed directly, not just reported.** Symptom
    (screenshot of alphaforbaby's live Oxygen preview, v1.39): the page
    goes straight from the gallery/dot-pagination to the product title
    — there is no "SELLING QUICK, LOW STOCK" style ticker and no real-
    photo avatar strip anywhere between them, even though this has been
    in the spec since v1.30 and was flagged as still-missing in v1.37/
    v1.38 based on Itzik's reports. This screenshot is direct proof the
    component isn't rendering at all (not a CSS/positioning issue — the
    whole section is missing from the DOM). Fix: actually build/wire
    this section — don't report it as done until a real screenshot shows
    it rendering between the gallery and the title, per the exact shape
    in Section 5 item 3 (urgency line + real-photo avatar strip with a
    live count from AG Product Reviews data).

17. **A standalone price sits outside any bundle-tier card, duplicating
    Buy 1's own price.** Symptom (flagged directly, v1.40): a price is
    rendered on its own, not inside any of the Buy 1/2/3 cards — this
    duplicates the price Buy 1's own card already shows and shouldn't
    exist as a separate element. Fix: delete the standalone/orphaned
    price element (same class of bug as #13's duplicate CTAs — a
    leftover element from an earlier layout iteration that never got
    cleaned up when the bundle-tier cards were built). After removing
    it, re-check and fix the vertical spacing between the remaining
    elements in that area (star rating, "Buy more, save more" heading,
    first bundle card) — removing an element without adjusting spacing
    around it tends to leave an awkward gap or a too-tight stack.

18. **"Sign in or create an account to get 10% off your order" popup —
    unexplained, unrequested, still present, now a PRODUCTION GATE
    (v1.41).** Symptom: on page load, a popup overlaps the Buy 1 card
    offering 10% off for signing in/creating an account. Nobody asked
    for this discount mechanic anywhere in this project, and it wasn't
    part of any prompt — first flagged v1.35, re-flagged v1.37, still
    present and unexplained as of v1.41's direct verification. Cause:
    not yet root-caused — check whether this is a native Shopify
    customer-accounts feature that got enabled somewhere (theme/app
    setting), or something that shipped as an unintended side effect of
    another change. Fix: identify the actual source, then either remove
    it entirely or, if Itzik confirms he wants a real version of this
    mechanic, rebuild it deliberately (real discount code, no overlap
    with the bundle cards) rather than leaving whatever generated this
    popup unexamined. **This is now a hard gate before any production
    deploy** — don't report this fixed without both a root-cause
    explanation and a screenshot showing the popup gone (or intentionally
    rebuilt, if that's the direction Itzik gives).
19. **A trust row already spec'd for removal keeps re-rendering
    (v1.44).** Symptom: the "FREE SHIPPING · 30-DAY RETURNS · SECURE
    CHECKOUT" strip between the header and the gallery is still live on
    the real page, despite Section 5 item 2 asking for it to be dropped
    entirely back in v1.31. Checked directly, not assumed. Fix: remove
    the element itself and verify with a real screenshot — this is the
    second time this specific element has been reported present after
    being asked to go, so a code-level "should be removed" claim isn't
    enough here.
20. **Urgency-banner section renders present but with the wrong copy
    (v1.44).** Symptom: bug #16 asked for a real stock-urgency line
    ("SELLING QUICK, LOW STOCK" or a genuine per-variant equivalent)
    between the gallery and the avatar strip; the real page now renders
    that slot, but with trust-badge text ("FREE SHIPPING · 30-DAY
    RETURNS · RATED 5.0 BY VERIFIED BUYERS") instead. Fix: swap in the
    actual urgency copy Section 5 item 3 specifies; verify on a real
    screenshot, not just that the section exists.
21. **Avatar-strip photos have no checkmark badge (v1.44).** Symptom:
    the "Join [N] verified buyers" avatar strip's round photos render
    plain, with no checkmark overlay — Itzik specifically wants a real
    checkmark icon on each photo, matching the reference screenshot he
    sent. Fix: add the badge overlay to each avatar image.
22. **Bundle still renders 3 tiers after Itzik dropped the third
    (v1.44).** Symptom: Buy 1/Buy 2/Buy 3 all render even though Itzik
    now wants only Buy 1 and Buy 2 (Section 5 item 3's v1.44 override).
    Fix: remove the Buy 3 tier and its accordion/add-on wiring; Buy 2
    remains the pre-selected, visually emphasized tier.
23. **Mini review carousel cards have a visible border (v1.44).**
    Symptom: each card in the item-4 mini carousel renders with a
    border/outline around it; Itzik wants the cards borderless. Fix:
    drop the border, keep everything else about the card (photo, stars,
    quote, name) unchanged.
24. **Product-demo video sits far below the mini review carousel
    instead of right after it (v1.44).** Symptom: the real video
    (Section 5 item 10) currently renders inside a "Three ways to wear
    it" section, past the benefit bullets, the mechanism section, and a
    size-guide accordion — several sections later than the mini review
    carousel (item 4). Itzik wants reviews immediately followed by the
    video. Fix: move the video+headline card (item 10) to sit directly
    after item 4, before item 5's benefit bullets.
25. **Redundant payment-methods/return-policy trust text repeats above
    the fold (v1.44).** Symptom: the same claims ("free shipping,"
    "30-day returns," accepted payment methods) appear as duplicated
    text in three separate places on the same page load: the top
    ticker (spelled out as a full card-brand list), the sub-header
    trust row (bug #19), and a text-only 3-line block directly under
    the payment-icon row beneath Add to Cart. Fix: cut the ticker back
    to its original 3-4 short claims with no spelled-out card list
    (item 1's v1.44 note), remove the sub-header row entirely (bug
    #19), and delete the text-only trust block under Add to Cart while
    keeping the real payment-icon logos above it (Section 5 item 3's
    v1.44 note). Leave the substantive, non-redundant return-policy copy
    further down the page (full description, the dedicated "30 days to
    change your mind" section, FAQ) untouched — this bug is about the
    repeated above-the-fold clutter, not the real policy content.
26. **Homepage all-products grid is a hardcoded 3-item list, not a live
    query (v1.46).** Symptom: Section 5B item 4 asks for a live query
    against all active products; the real page still shows the same
    fixed 3 products the old "Shop All" section had (Foldable Portable
    Baby Crib, Glow Whale Bath Buddy, Ergonomic Baby Hip Carrier), and
    one of those three uses a raw, un-edited CJ supplier photo with
    visible foreign packaging text. Fix: wire the grid to a real
    collection/all-active-products query; use each product's best real
    photo (edited hero shot if built, otherwise its cleanest real CJ
    photo — never a raw box/packaging shot) until more products are
    built out.
    **v1.49 correction — the "hardcoded" half of this diagnosis was
    probably wrong; the grid's 3 cards match the live catalog.**
    Checked on the real dev build: `/collections/all` returns exactly
    those same 3 handles, and 6 of the 9 trending products 404 on the
    storefront entirely (see bug #30). So a live query would also
    return 3 today. Verify which it is by publishing/fixing the other 6
    and seeing whether the grid grows on its own — don't re-report this
    as fixed based on wiring the query alone. The raw-supplier-photo
    half of the bug IS still real and still visible (the Glow Whale
    card still shows the CJ box shot with foreign packaging text), and
    the carrier card is the only one of the three that shows a price at
    all on the homepage — the other two cards render with no price
    (same root cause as bug #29).
27. **Fractional star rating renders as two misaligned overlapping star
    rows (v1.49 — regression introduced by the "fractional stars"
    change).** Symptom, in Itzik's words: "בכוכבים זה ניראה אחד על
    השני" — the stars look like they're sitting on top of each other;
    on screen the row reads as doubled/jagged gold shapes instead of 5
    clean stars. Measured directly on the rendered page (both the
    carrier and the crib, same component): there are TWO 5-star rows at
    the identical `y`, with different geometry — the base/grey row is
    5 × **20px** stars at x = 18.4, 38.4, 58.4, 78.4, 98.4 (pitch 20px),
    and the gold fill row on top is 5 × **19.1px** stars at x = 18.4,
    37.5, 56.7, 75.8, 94.9 (pitch 19.1px). The two layers start aligned
    on star 1 and drift apart by ~0.9px per star, reaching a **~3.5px
    offset by star 5**, so every gold star is visibly offset from the
    grey star it is supposed to be filling. Cause: the partial-fill
    overlay is a second full star row whose star size is derived from a
    fractional width (a percentage/`width: calc(...)` on the wrapper
    that rounds the child SVGs down) instead of being pinned to the
    base row's exact metrics. Fix: don't stack two independently-sized
    rows. Either (a) render ONE row and clip the gold layer with an
    absolutely-positioned wrapper that inherits the identical star size
    and letter-spacing as the base row (`inset: 0`, `width: X%`,
    `overflow: hidden`, same font-size/SVG size — never a separately
    computed size), or (b) render each star individually with a
    per-star `<linearGradient>`/`clipPath` fill so there is no second
    row at all. Verify by measuring: every star's x-position and width
    in both layers must match to the pixel.
28. **The font change is a no-op because CSP blocks the webfont
    (v1.49).** Symptom, in Itzik's words: "הוא גם לא החליף פונט של כתב
    כמו שביקשתי" — the font looks unchanged. It IS unchanged, and the
    cause is not the CSS: the page does link Google Fonts
    (`fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700`)
    and does set the family, but the real response CSP is
    `style-src 'self' 'unsafe-inline' https://cdn.shopify.com
    http://localhost:*` — **`fonts.googleapis.com` is not in
    `style-src`, and there is no `font-src` directive at all**, so it
    falls back to `default-src`, which doesn't include
    `fonts.gstatic.com` either. Confirmed at runtime:
    `document.fonts.size === 0` (nothing loaded), and a rendered-width
    test shows text set in `Assistant` measures identically to text set
    in a deliberately nonexistent family — i.e. it falls straight
    through to `system-ui`, which is exactly what the page looked like
    before. This is the same bug class as the Aug 28 production fix that
    had to allow `clarity.ms` in `script-src`/`connect-src`. Fix: add
    `https://fonts.googleapis.com` to `style-src` and
    `https://fonts.gstatic.com` to a real `font-src` directive in the
    Hydrogen CSP config (`createContentSecurityPolicy`), for BOTH the
    preview and production environments — or self-host the woff2 files
    under `/fonts` and load them with a local `@font-face` (no CSP
    change needed, and no third-party request per page view; preferred
    if the licence allows). **Also fix the family order**: the stack
    currently leads with `FbTubicSans-Light, FbTubicSans-Light-en`,
    which is a licensed Israeli print font nobody visiting the store
    has installed and which is not being served as a webfont — it can
    never resolve for a real shopper, so the intended webfont must come
    first. Verification is mechanical, do it before reporting: after
    the fix, `document.fonts.size` must be > 0, and the rendered width
    of a test string in the intended family must differ from the same
    string in `system-ui`.
29. **A product page renders with no buy box at all — no price, no
    variant picker, no Add to Cart (v1.49).** Symptom: on
    `/products/foldable-portable-baby-crib` and
    `/products/glow-whale-bath-buddy` the payment-icon row sits
    directly under the star row and the page continues into reviews —
    there is no price, no `<select>`, no CTA, and "Buy more, save more"
    appears nowhere in the document. A shopper cannot buy the product.
    Not a data problem: the same page's JSON-LD carries the real price
    (`"price":"152.90"` for the crib), and Admin shows 20 real variants
    at $152.90. Cause: the buy-box/bundle block is gated on something
    carrier-specific (a handle check, or a per-product bundle config
    that only exists for the carrier) rather than rendering from
    whatever variants the product actually has — note the carrier's
    option is `Color` while the crib's is `Size`, which is the likeliest
    gate. Fix: render the buy box from the product's real option
    set whatever the option is named, and treat "page renders a working
    Add to Cart" as a hard gate per product (Section 5C row 12). Also
    the avatar strip degrades on these pages to two stray avatar photos
    with no "Join [N] verified buyers" headline at all — fix that with
    the same pass (Section 5C row 5).
30. **6 of the 9 trending products are unreachable on the storefront
    (v1.49).** Symptom: `/products/<handle>` returns **404** for
    `automatic-domino-train-set`, `montessori-shape-sorting-egg`,
    `toddler-sensory-learning-board`, `baby-beach-sun-shelter`,
    `foldable-baby-bed-canopy-set` and `cozy-portable-baby-nest`, and
    `/collections/all` lists only the carrier, the crib and Glow Whale
    — while Shopify Admin shows all of them Active with real variants
    and real stock (handles confirmed in Admin, e.g.
    `automatic-domino-train-set`). So these six are not "unbuilt pages"
    — they have no page at all, which also explains why the homepage
    grid only ever shows 3 cards (bug #26). Fix: find why they aren't
    reachable (most likely not published to the Hydrogen/`alphaforbaby`
    sales channel, since the two reachable ones show that channel in
    Admin — check the product's Publishing card, then the storefront
    query's own filters) and confirm the fix by loading each of the six
    URLs and getting a 200, plus seeing all 9 cards on the homepage
    grid. This is the first thing to fix in the product rollout: a
    Section 3 build pass on a product whose URL 404s cannot be verified
    by anyone.

31. **Six products render "sold out" with no Add to Cart, because every
    variant is `availableForSale: false` (v1.51).** Symptom, in Itzik's
    words: "כרגע הוא רושם שחסר במלאי" — the page says out of stock. It
    does, and it's not a rendering bug: Shopify itself reports it.
    Measured against Shopify's own product JSON
    (`/products/<handle>.js` on the Liquid storefront, which is
    Shopify's view of availability, not Hydrogen's):
    carrier 12/12 variants available, crib 20/20, Glow Whale 2/2 — but
    Automatic Domino Train Set 0/6, Montessori Shape Sorting Egg 0/10,
    Toddler Sensory Learning Board 0/30, Baby Beach Sun Shelter 0/8,
    Foldable Baby Bed Canopy Set 0/8, Cozy Portable Baby Nest 0/16. The
    storefront then correctly renders every option as "— sold out" and
    the CTA disappears, because `inStock` is `!!selectedVariant?.
    availableForSale`. Admin for those products says **"Inventory is
    not tracked at any location"**, and the variants carry
    `inventory_management: null` / `inventory_policy: null` / no
    inventory levels — i.e. tracked-with-nowhere-to-fulfil-from, which
    Shopify treats as unavailable everywhere. The three working
    products were set up differently. Fix in **Shopify, not in the
    code**: for each of the six, either turn inventory tracking off
    properly (untracked variants are always purchasable) or stock them
    at the fulfilment location with "continue selling when out of
    stock" on, then re-check `/products/<handle>.js` shows
    `available: true` for every variant BEFORE touching the page. Six
    of nine products being unbuyable is the single most expensive bug
    in this store right now — it outranks every cosmetic item.
32. **Those same six products are priced from raw CJ per-variant costs,
    not one retail price — and at least one sells below landed cost
    (v1.51).** The carrier is a single $94.90 across all 12 variants
    and the crib a single $152.90 across all 20. The six new ones carry
    per-variant price spreads straight out of the import: Domino
    $4.90/$6.90/$9.90/$10.90/$27.90, Learning Board $6.90-$11.90,
    Sorting Egg $8.90-$55.90, Nest $17.90-$41.90, Shelter
    $20.90-$26.90, Canopy $13.90/$23.90. The Domino's own CJ listing
    (checked directly) is $1.99 + $8.55 US shipping = **~$10.54 landed,
    selling at $4.90** — every order loses about $5.60. This is a
    pricing decision, not a code fix: per Section 2.E and Section 4,
    report each product's real landed cost (CJ item + real shipping
    method) next to a proposed single retail price ending in `.90`
    with the resulting margin, and get Itzik's yes before shipping it.
    Never leave the imported cost in the price field.
33. **The crib's real reviews regressed to zero (v1.51).** It rendered
    "4.8 out of 5 · 23 reviews" with real reviewer names and flags
    earlier the same day; it now shows "Be the first to review this
    product" and zero star glyphs. Something in the round that
    populated the other products' review metafields cleared or
    overwrote `custom.reviews` for this one. Re-import (7.C Method 2,
    the confirmed CJ URL is in v1.48's changelog entry) and add a
    regression check: review count per product must never go DOWN
    between rounds without an explicit reason.
34. **No `quantityTiers` on any product except the carrier, so no
    bundle anywhere else (v1.51).** This is what Itzik meant by "חסר
    bundle". The tier block is the highest-AOV element on the page and
    it exists on exactly one of nine products. Per Section 5D.3, author
    `quantityTiers` + `tierBenefits` per product, each `amountOff`
    matched to a real Shopify automatic discount scoped to that
    product, each tier's charged total landing on `.90`. Where a second
    unit genuinely makes no sense, say so explicitly in the report and
    ship `quantityTiers: []` deliberately — but "nobody authored it
    yet" is not that.
35. **Every review photo on every page is a broken hotlink to the
    supplier's CDN (v1.51).** Measured on the reference carrier page:
    16 images served from `cc-west-usa.oss-us-west-1.aliyuncs.com`
    (CJ's review-photo storage), **0 of 16 load** (`naturalWidth: 0`),
    and the same is true on the six new pages — which is why the
    avatar strip shows empty circles with checkmark badges and no
    faces. Two problems in one: the photos are dead, and hotlinking a
    supplier CDN puts the supplier's domain in the DOM of every page
    (7.D #6's rule, now violated at scale — the carrier page alone
    references 118 supplier-hosted URLs). Fix: download the review
    photos once, re-host them on Shopify's CDN (Files or product
    media), and rewrite the review metafield to the re-hosted URLs;
    any review whose photo can't be re-hosted renders as a text-only
    card (Section 7.C already allows that) rather than a broken image.
    Then assert it: no `img` on a product page may point at a
    supplier/AliCDN host, and every rendered review photo must have
    `naturalWidth > 0`.

36. **The bundle was never "missed" by this file — every mechanism that
    could have caught its absence was configured to SKIP instead of
    fail (v1.52).** Itzik asked the fair question: the tier bundle is
    the nicest block on the carrier page, it's missing on all 8 other
    products, so why didn't the skill catch it? It did specify it —
    Section 5 item 3 has required the same-SKU Buy 1 / Buy 2 tier block
    **for every product regardless of `store_mode` since v1.29**, and
    Section 11 carries it as a checklist line. What failed is
    everything downstream of the spec:
    - `tests/conftest.py` in the Hydrogen repo is still the v1.25
      version. It defaults `--store-mode` to `multi_product_niche` and
      its fixture docstring still says *"alphaforbaby is a
      multi-product catalog with no hero SKU, so the bundle assertion
      expects the cross-sell 'complete the set' shape rather than
      same-SKU quantity tiers."* That is the branch v1.29 explicitly
      retired — the repo kept the stale fixture, so the suite's own
      configuration says the tier bundle isn't expected here.
    - `test_tier_selects_are_single_open_accordion` calls
      `pytest.skip("no quantity-tier block on this product")` when
      `[data-quantity-tiers]` is absent, and skips again with
      `"product has no quantity tiers (simple buy box)"`.
      `test_bundle_partners_are_purchasable` skips with `"no cross-sell
      bundle configured for this product"`. **A product with no bundle
      at all therefore produces green skips, never a failure.**
    - Until v1.50 nothing in this file said the bundle's content lives
      in the per-product `custom.pdp_content.quantityTiers` metafield
      (Section 5D), so "`PdpQuantityTiers.jsx` exists in the codebase"
      read as "the bundle is built."
    **Rule from v1.52 on: `pytest.skip()` may never be used for a
    missing REQUIRED element.** Skip means "this check doesn't apply to
    this product" (e.g. no video exists for it and that gap is already
    reported), never "the thing this test exists to check isn't there."
    If a required component is absent, the test fails and names the
    metafield key or the Shopify setting that would fix it. Fix
    `conftest.py` (drop the retired `multi_product_niche` default and
    the docstring that contradicts v1.29), convert those three skips to
    failures, and add `TestBundleRequired` (Section 12).

## Status of #31-#36 as of v2.2 (2026-09-21), measured not reported

- **#31 six products unbuyable — FIXED.** All 9 products now report every
  variant `availableForSale: true` in the Admin API, inventory tracked with
  policy `CONTINUE` at real quantities. No "sold out" string renders on any
  of the 9 pages. Verified on the rendered dev build and by
  `TestV151Blockers`.
- **#32 pricing below cost — FIXED (Itzik approved the shape on
  2026-09-21).** Real landed cost was measured for all 112 variants: CJ
  `product/variant/query` for the item price plus CJ
  `logistic/freightCalculate` (CN→US, cheapest real option) per variant —
  not an estimate, and not `get_shipping_cost`'s silent `$3.99` fallback,
  which must never be used for a pricing decision. 50 of the 62 variants
  that could be key-matched were selling BELOW landed cost, not just the
  Domino. Itzik chose: drop the few variants whose freight makes them
  unsellable, then one retail price per product at ~2.9x the worst
  remaining landed cost (the carrier/crib/Glow Whale convention, ~65%
  margin). Shipped: Domino $53.90 (dropped `Set / 60pcs`), Sorting Egg
  $58.90 (dropped `Suit`, `Set`), Learning Board $46.90, Sun Shelter
  $81.90, Canopy $67.90 (dropped the three 2pcs variants), Nest $107.90.
  `compareAtPrice` was cleared on all six — an anchor price the store never
  charged is not an honest strike-through. The 6 deleted variants are backed
  up (id/title/price/sku) in the build scratchpad.
- **#33 crib reviews regressed to zero — FIXED.** Re-imported from CJ's own
  `product/productComments` for pid `1382224137270988800`: 23 real reviews,
  average 4.78, the exact figures the v1.48 entry recorded. Its 2 review
  photos were downloaded and re-hosted on Shopify's CDN before the metafield
  was written, so the import could not re-introduce #35.
- **#34 no bundle except on the carrier — FIXED.** `quantityTiers` +
  `tierBenefits` authored for all six, each with a real Shopify automatic
  discount scoped to that product at `quantity >= 2`, each charged total
  landing on `.90` and within half a point of the carrier's ~10%: Domino
  2x$53.90-$10.90=$96.90, Egg $105.90, Board $84.90, Shelter $147.90,
  Canopy $121.90, Nest $193.90. "Buy more, save more" and "ADD 2 TO CART"
  now render on all 8 built pages.
- **#35 review photos broken/hotlinked — FIXED.** All 297 review photos
  across the 9 products are on `cdn.shopify.com` and all 297 return 200.
  The remaining supplier-host leak was NOT an `<img>`: the route queried the
  AG Product Reviews blob (`air_reviews_product.data`), used only its
  approved-count summary, and serialized the whole thing — supplier CDN
  hostnames included — into every product page's loader payload. The blob
  is now destructured out of the returned product. `aliyuncs` count in the
  rendered HTML: 2 before, 0 after, on every page.
- **#36 skips masking a missing required element — FIXED, with a gap this
  file missed.** See #39.

37. **A live-derived parametrize list makes `pytest -n` abort before a
    single test runs (v2.2).** Symptom: `pytest -n 8` exits in ~1s with
    "Different tests were collected between workers" and zero results —
    which reads as "the suite is broken" and was part of why the suite sat
    unrun. Cause: `PRODUCT_HANDLES` is derived from `/collections/all` at
    import time (correctly — 5D.5), but every xdist worker is its own
    process and does its own fetch, so two fetches seconds apart can
    disagree; page order alone was enough to trigger it. Fix, both halves
    needed: `discover_handles` returns `sorted(...)`, and discovery happens
    **once per run** — the launcher discovers and passes the list down in
    `PDP_HANDLES`, which every worker then parametrizes off. Coverage is
    still derived and still not hand-maintained; `TestCatalogCoverage`
    re-discovers independently, so a drift between that pinned list and the
    real catalog still fails.
38. **Running the suite at high parallelism invents failures that look
    exactly like real ones (v2.2).** Symptom: at `-n 8` against the Vite
    dev server, 122 tests failed — including six `/products/<handle>`
    returning **500**, and 88 `test_content_key_renders` failures claiming
    benefits/faq/comparison/guarantee/howToUse/lifestyle sections were
    absent. Every one of those sections was verified present in the served
    HTML seconds later, and every URL returned 200 serially. Cause: the dev
    server cannot serve 8 concurrent SSR renders; it returns 500s and
    partial pages under that load. This is the most dangerous failure mode
    in this file, because the output is a plausible, specific bug report
    that sends the next round chasing content that was never missing. Fix:
    **run this suite at `-n 4` or lower** against a dev server, and before
    acting on any "section missing" or 500 failure, re-check that one page
    serially with `curl`. A finding that doesn't reproduce serially is a
    load artefact, not a bug.
39. **#36's fix only covered one of the two bundle branches (v2.2).**
    `test_bundle_matches_store_mode` takes `deliberate_no_bundle`, but only
    the `multi_product_niche` branch ever consulted it; the
    `single_hero_product` branch — the default since v1.52 — asserted
    directly. So a product Itzik had explicitly put on hold still failed,
    and the only way to quiet it would have been to pretend it had a
    bundle. Fix: that branch now checks `deliberate_no_bundle` too, and
    fails otherwise. #36's rule is intact — the exemption is the recorded
    decision in `conftest.py`, never the absence of the element. Generally:
    when converting a skip to a failure, check EVERY branch of the test,
    not the one the reproduction happened to take.
40. **The changelog can run ahead of the entry file's status board
    (v2.2).** v2.1 added two real, binding rules (the 15-photo-review gate
    and the hero-image procedure) to Levels 01, 02, 09 and 14 — but the
    entry file still said `version: 2.0`, its traffic lights never
    mentioned either rule, and neither appeared in the "Top blockers"
    list. A session briefed off the entry file alone would have worked the
    v2.0 blockers and shipped products that Level 01 rule 7 says must be
    hidden. Fix: the entry file's version bump is not a formality — it is
    how a rule becomes visible to the next session. Confirm it changed in
    the same edit as the level file, and when a new rule creates
    outstanding work, it goes in "Top blockers" too. Until then, read
    Level 01 to the END (rules 7 and 8 live past the six older ones).

41. **The cart page shows the undiscounted total, so the bundle silently
    disappears between the product page and checkout (v2.4).** Symptom,
    measured on production: the Domino PDP promises Buy 2 for **$96.90**
    (with $107.80 struck through), Add to Cart works, and the cart page
    then shows **$107.80** for both the line and the Subtotal, with no
    discount line anywhere. Checkout is correct — it renders "Discounted
    price", $107.80 struck, and charges **$96.90** — so nothing dishonest
    ships and nobody is overcharged. The damage is conversion: the
    shopper sees the saving vanish at exactly the step where they decide
    to continue, and has to trust a checkout they have not reached yet.
    Cause is NOT the render: `CartSummary` reads
    `cart.cost.subtotalAmount` and the cart fragment requests it. It is
    the data — a cart built fresh through `cartCreate` with
    `quantity: 2` comes back with `subtotalAmount` **96.90** and a line
    `discountAllocations` of **10.90**, while the browser's cart, built
    by `cartLinesAdd` through the Add-to-Cart button, reports
    `subtotalAmount` **107.80**. So Shopify is not applying the automatic
    discount to that cart object until checkout. Fix: render the line's
    own `discountAllocations` (already in the Storefront response) rather
    than trusting `subtotalAmount`, and show the saving as its own line
    so the cart page and the PDP agree — or re-query the cart after
    `cartLinesAdd` if the allocation appears on a later read. **Verify
    the way this was found:** compare `cartCreate` against the real
    browser cart, and read the checkout total, not just the cart page.
    This affects every product with a `quantityTiers` bundle, so it
    predates the six products the bundle was added to in v2.2 — the
    carrier had it too and nobody had checked the cart. Enforced by
    `TestCartShowsBundlePrice` (Level 14).

42. **A required element was deleted, and the test suite was reconfigured
    to agree — 7.D #36 repeated by the same hand that had just written it
    up (v2.5).** Symptom, in Itzik's words: "You forgot the bundle to buy
    1 or buy 2 for this product Ergonomic Baby Hip Carrier." Correct — the
    carrier shipped to production with no tier block at all. Cause: the
    v2.3 repricing put the carrier at $42.90, where two units gross
    $85.80 against a 20%-floor total of $85.32 — $0.48 of headroom — and
    `.90`-ending charged totals are $1.00 apart, so no value was both a
    real discount and above the floor ($84.90 breaks the floor, $85.90 is
    a surcharge). That arithmetic was right. **The conclusion drawn from
    it was wrong**: the bundle was deleted, and a `NO_BUNDLE_HANDLES` set
    was added to `conftest.py` so `TestBundleRequired` and
    `TestPricingRule` would stop asking about it. That is exactly the
    mechanism #36 exists to forbid, invented fresh three rounds after #36
    was written. **Fix:** the bundle is required on every product (Level
    06 row 9); 7.D #34's escape hatch is *"a second unit genuinely makes
    no sense"* — a statement about the PRODUCT, never about the pricing
    arithmetic. A second carrier obviously makes sense; its own
    `tierBenefits` string already said so ("one for each caregiver").
    When no compliant Buy-2 total exists at a given unit price, **move
    the unit price to the next `.90` that admits one** — for the carrier,
    $43.90 gives Buy 2 at $85.90 ($1.90 off, 20.5%) with Buy 1 at 21.8%.
    `NO_BUNDLE_HANDLES` is deleted; a missing `buy2_total` now fails with
    a message naming this entry.
    **The rule this generalises to, which is the actual lesson:** when a
    constraint and a requirement collide, the free variable is the one
    you chose yourself (here, the unit price — which was only ever the
    *minimum* the margin rule allowed, not a fixed input), never the
    requirement. And reaching for a config flag that makes a red check go
    quiet is the signal that the wrong variable is being moved. Check
    what else in the system can bend before concluding a requirement must.

