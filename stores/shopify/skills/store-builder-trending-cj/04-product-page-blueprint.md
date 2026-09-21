<!-- Level 4 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 5. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 5. PAGE BLUEPRINT — exact section order

This is the section order observed across all 5 reference stores,
merged into one canonical structure. Build every one of these unless
marked optional. Do not reorder them — this order itself is part of why
they convert (need → proof it works → remove risk → close).

Items 3, 8, and 13 below are written from a direct, live re-check of
starnestshop.com/products/star-nest (2026-09-06, DOM inspection +
screenshots, not from memory) — use the concrete shape described, not a
looser paraphrase of it.

1. **Announcement bar** (sticky, top of page): rotating 3-4 short claims
   separated by "✦" — e.g. `FREE SHIPPING ✦ 30-DAY GUARANTEE ✦ LOVED BY
   [X]+ CUSTOMERS ✦ [urgency line if real]`
   **v1.44 — checked directly, alphaforbaby's real ticker has drifted
   from this**: it currently rotates through six-plus items, including
   one item that spells out the full accepted-card list ("WE ACCEPT
   VISA · MASTERCARD · AMEX · JCB · DISCOVER · DINERS · PAYPAL · APPLE
   PAY · GOOGLE PAY") — remove that spelled-out payment-brand item
   entirely (the payment icon row already lower on the page, per item 3,
   is where real accepted-payment logos belong; a text list here is the
   "payment methods text" Itzik asked to delete). Cut the ticker back
   down to the original 3-4 short claims this item already specifies,
   and slow its rotation/scroll speed — Itzik flagged it as "too fast"
   to read on the real page.
2. **Header**: logo (wordmark, not a complex icon — small stores read
   as more trustworthy with a clean text logo), search icon, cart icon
   with live count. **v1.31 correction, confirmed on littlesnugg's real
   mobile page (390×844 viewport, not desktop)**: the header there is
   just a hamburger menu icon, the wordmark, and a cart icon — no search
   bar, no trust-row line at all above the gallery. On a single/few-
   product landing page, **drop the search bar and the "FREE SHIPPING ·
   30-DAY RETURNS · SECURE CHECKOUT" trust row entirely from the product
   page's header area** (search can live behind the hamburger/menu if
   it's needed at all; the trust row's content is redundant with the
   3-icon trust row that already sits lower on the page per this
   section). This supersedes v1.29's softer "move or drop it" wording —
   on mobile specifically, drop both, don't just de-prioritize them.
   **v1.36 — layout of the header row itself, confirmed on littlesnugg's
   real mobile page**: the wordmark sits CENTERED in the row, hamburger
   icon pinned left, cart icon pinned right (not left-aligned next to
   the hamburger). For alphaforbaby: center "ALPHA FOR BABY" the same
   way. The rotating announcement ticker (item 1) is a separate strip
   that sits ABOVE this header row, never merged into it or placed
   below it. Also remove the sign-in icon currently inside alphaforbaby's
   hamburger menu — not something anyone asked for; Itzik wants it gone
   (possibly related to the unexplained "sign in / 10% off" popup
   flagged in v1.35 — worth checking whether it's the same feature).
   **v1.37 — edge spacing, confirmed again directly against littlesnugg's
   real header**: the hamburger icon sits flush against the header's
   LEFT edge and the cart/checkout icon flush against the RIGHT edge —
   no extra container padding holding either icon inward from the edge.
   Check alphaforbaby's actual computed padding/margin on both icons
   against littlesnugg's real values, don't eyeball it. Itzik also
   re-confirmed directly: littlesnugg's own side/hamburger menu has NO
   sign-in button in it at all — this isn't just "Itzik doesn't want one
   on alphaforbaby," it's the reference store's own real pattern too, so
   treat "no sign-in in the hamburger" as the correct default for this
   template generally, not a one-off preference.
   **v1.40 — this is narrower than it first sounded; distinguish the
   HEADER ICON from the DRAWER CONTENT.** v1.36/v1.37 correctly removed
   a sign-in ICON that had been sitting in the header row itself (next
   to/inside the hamburger control) — that removal stays correct, don't
   re-add anything in the header row. Separately, Itzik now wants a
   "Sign In" BUTTON as a menu item INSIDE the hamburger's slide-out
   drawer/sidebar panel (the content that appears after tapping the
   hamburger) — this is a normal nav-menu item alongside whatever other
   links live there, not a header-row icon, and it doesn't conflict with
   the earlier removal. **Also, hamburger left-edge positioning needs to
   be more precise**: the previous fix (7.D bug #15) got it roughly
   left, but Itzik wants the actual CSS tightened so it's genuinely
   flush against the true left edge — check real computed spacing, not
   just "on the left side somewhere."
   **v1.44 — checked directly, this item's own v1.31 instruction is
   STILL not done (7.D bug #19).** The "FREE SHIPPING · 30-DAY RETURNS
   · SECURE CHECKOUT" trust row is still rendering as its own strip
   directly below the header, above the gallery — the exact element
   this item asked to be dropped entirely three versions ago. Remove it
   for real this time and verify on a real screenshot; don't report
   this done from reading the component code, since that's how it was
   missed twice already.
3. **Hero / product gallery + buy box** (above the fold, both desktop
   and mobile):
   - Left/top: image gallery, 5-8 images minimum (see 7.A for exact shot
     list — real CJ photos first). **Pagination, v1.31 correction**:
     confirmed directly on littlesnugg's real mobile page — there is NO
     scrollable thumbnail strip on mobile at all, just a row of small
     dot indicators under the main image (one dot per slide, current
     slide filled). Use small dot/button pagination on mobile instead of
     a thumbnail strip; a thumbnail strip is acceptable on desktop where
     there's width for it, but mobile should match the dot pattern.
     Swipeable on mobile either way. Prev/next arrows: use
     `--color-accent` (see
     8.C) — a deliberate improvement over the reference (starnestshop's
     own arrows are neutral near-black, confirmed directly; don't expect
     to find a colored-arrow example there, this is Itzik's own call).
     **Slide 1 must be a single, clean, edited shot — never a raw CJ
     multi-inset marketing collage** (v1.29, 7.D bug #12): checked
     directly, alphaforbaby's current gallery slide 1 is a CJ-sourced
     composite image with a small inset photo of a person AND the main
     product shot merged into one frame — this reads as a supplier
     catalog composite, not a store's own hero shot, and it's a
     completely different feel from littlesnugg.store's own gallery
     (confirmed directly: every slide there is one clean subject — either
     a plain product flatlay or one lifestyle shot, never both stitched
     together). If a sourced image is a multi-inset composite, either
     crop it to a single subject or replace it with a different real CJ
     photo/generated image before using it as any gallery slide, slide 1
     especially. Also keep the page chrome above this gallery minimal —
     checked directly, alphaforbaby's current header + full 3-item trust
     row (logo bar, search bar, "FREE SHIPPING · 30-DAY RETURNS · SECURE
     CHECKOUT") pushes the gallery down and shrinks it within the first
     viewport on mobile, while littlesnugg keeps only a slim scrolling
     announcement ticker + a bare logo bar above the image, so the hero
     shot dominates the very first screen a visitor sees. A search bar
     specifically doesn't need to sit above the fold on a single/few-
     product landing page — move or drop it before letting chrome
     compete with the hero image for vertical space.
   - **Urgency banner + social-proof strip (v1.30, position corrected
     v1.31, data source fixed v1.32)**: confirmed directly on
     littlesnugg's real mobile page — these sit BELOW the gallery/dot-
     pagination and ABOVE the product title, not above the image (v1.30's
     wording was corrected after actually checking mobile, not desktop).
     Order confirmed on littlesnugg: hero image → dot pagination →
     urgency ticker → buyer-avatar/social-proof strip → product title →
     stars → bundle. **v1.33 override RESCINDED in v1.35 — Itzik saw
     the built result on his real phone and reversed it.** v1.33 had
     put the product title ABOVE the gallery for alphaforbaby as a
     deliberate divergence; after testing the real build, Itzik wants
     it back to littlesnugg's actual confirmed order. For alphaforbaby
     (and by default for any store, absent a fresh explicit override):
     hero image → dot pagination → urgency ticker → avatar/social-proof
     strip → product title → stars → bundle, exactly as littlesnugg
     does it. Do not put the title above the gallery unless a NEW
     explicit instruction says so — the v1.33 note calling this "not a
     bug, don't correct it back" no longer applies; it was superseded by
     Itzik's own later message, not by a re-check of the reference.
     **Social-proof number (v1.32): drive the count from the real AG
     Product Reviews data (7.C — confirmed reachable from Hydrogen via
     the `air_reviews_product.data` metafield's `reviewSummary`), not a
     hardcoded figure like littlesnugg's own "1000+ New Mums."** Itzik's
     call: this is a real number, not a fabricated one — wire the
     component to the actual review/customer count and let it read
     whatever that real number is (it may be small in dev before
     production is wired up; that's expected and fine, it fills in for
     real once live). Never hardcode a copied competitor number. The
     avatar strip's photos: real CJ buyer-review photos already sourced
     (7.C), never generated faces presented as buyers.
     **Stock-urgency line ("low stock" style): still a SEPARATE honesty
     problem, unresolved as of v1.32** — alphaforbaby holds ~40,000
     units of this product, so an aggregate "low stock" claim would be
     false (Rule 1). Before shipping any stock-urgency line: check for a
     real PER-VARIANT signal instead of the aggregate (a specific color/
     size genuinely low or sold out is a true claim even when total
     inventory is high) — if one exists, use it, scoped to that variant
     only, not as a blanket store-wide claim. If no real signal exists at
     any level, ship the ticker slot with a different, genuinely true
     line (e.g. a real shipping/guarantee claim already used elsewhere)
     rather than an aggregate low-stock claim, or omit the ticker and say
     so plainly rather than leaving this ambiguous.
     **v1.37 — Itzik confirmed directly against a real littlesnugg
     screenshot that this whole block (urgency ticker + avatar strip) is
     still not present/correct on alphaforbaby's real build, and called
     it a must-have** ("אני חייב אותם" — I need these): treat this the
     same way v1.34 treated the missing mini carousel — as a real,
     confirmed-missing section, not a style nice-to-have to deprioritize.
     He specifically likes the avatar strip with real photos of people
     ("זה ניראה טוב עם התמונות של האנשים האלה") — the row of small round
     real buyer photos feeding into "JOIN [N] New Mums" is part of what's
     wanted, not just the urgency ticker line alone. Verify this section
     actually renders on the live page, not just that the component
     exists somewhere in the codebase.
     **v1.44 — checked directly: the section now renders, but with the
     wrong content (7.D bug #20).** It currently shows "FREE SHIPPING ·
     30-DAY RETURNS · RATED 5.0 BY VERIFIED BUYERS" — trust-badge text,
     not the urgency line this item specifies. Replace it with the real
     stock-urgency line this item already requires ("SELLING QUICK, LOW
     STOCK" or whatever real per-variant signal applies, per the honesty
     rule above) — don't leave the trust-badge copy standing in for it.
     **v1.45 — Itzik's explicit decision on the honesty question above**:
     presented with the three options (literal scarcity wording anyway,
     a real per-variant stock signal, or keep the honest-but-different
     line Sol shipped), Itzik chose to ship the literal wording. Use
     "SELLING QUICK, LOW STOCK" (or an equivalent literal scarcity line)
     on this ticker slot going forward, as a deliberate, explicit
     override of the aggregate-honesty concern above — this is Itzik
     knowingly treating it as conventional marketing copy, not a
     factual inventory claim, the same way most stores use this kind of
     line. **This override is scoped to this one urgency-ticker
     line only** — it does not relax Rule 1/Rule 2 anywhere else in this
     file (fabricated reviews, fake countdown timers, invented specs,
     etc. are all still forbidden); if a future product's urgency line
     raises the same question, that's a fresh instance to confirm with
     Itzik, not an assumed blanket permission.
     Also (7.D bug #21): the avatar photos have no checkmark badge —
     Itzik wants a real checkmark icon overlaid on each avatar (bottom-
     right corner), matching the reference screenshot he sent. And
     whatever short label sits with this block (the urgency line or the
     "Join [N] verified buyers" text) must be styled/sized so it never
     wraps to a second line on a real mobile viewport — check the actual
     rendered width, not just that the string is short in the code.
   - **No duplicate brand tag / product name (v1.31)**: only one visible
     product-title instance on the page — BELOW the gallery, per the
     littlesnugg-matched order restored in v1.35 (image → dots → urgency
     ticker → avatar strip → title → stars → bundle). Don't also render
     a small brand-name caption under the gallery/thumbnails AND the
     full title again lower down; that's a leftover-template duplication
     (same class of bug as 7.D bug #9), not a deliberate design choice —
     pick the one location (below the gallery/urgency/avatar block) and
     remove the other.
   - **No standalone color selector outside the bundle (v1.33, repeat —
     still not fixed as of the last check)**: there must be exactly ONE
     place to pick Color/Size — inside the bundle tier cards, per unit
     (above). A separate top-of-page "COLOR: [Blue ▾]" select sitting
     between the price and the bundle block is a duplicate control, not
     a second valid entry point — remove it entirely. This was already
     asked for once; if it's still there, it wasn't actually done, check
     the real DOM again rather than assuming.
   - Right/below: Brand micro-tag → Product title (with™ or brand
     suffix) → star rating + review count badge (**filled stars in a
     genuine gold/amber color — v1.31 correction, confirmed directly on
     littlesnugg's real page: their stars are gold, not the store's own
     `--color-accent` when that accent isn't itself gold/amber**; stars
     are a near-universal gold convention shoppers already read as "the
     rating," don't substitute a differently-colored accent just because
     8.A.4 says the accent should repeat across badges/CTA — rating
     stars are the one exception, e.g. "★★★★★ (108 Reviews)").
     **v1.44 — checked directly against Itzik's ask**: make the star
     glyphs themselves bigger and tighten the vertical spacing around
     this star+review-count line (both here and on the final reviews
     grid's per-card star rows, item 14) — also close up the gap between
     this line and the "Buy more, save more" bundle heading right below
     it; the real page currently has more air there than the reference. →
     social-proof line ("[Name] and [N] others bought this") → price
     block (sale price large, anchor price struck through, "SAVE X%"
     badge) → **bundle/quantity tier block** (see below — required
     whenever the product supports multi-unit purchase, not just
     optional) → variant selector → quantity selector → primary CTA
     button → **"purchase options" row directly under the CTA (v1.30)**:
     confirmed on littlesnugg — a small row of real accepted payment/
     buy-now options (e.g. the store's actual PayPal/Shop Pay/Apple Pay
     methods, whatever Shopify's own checkout already accepts) sits
     right under Add to Cart, never invented payment logos the store
     doesn't actually support → 3-icon trust row (Secure Payment /
     Guarantee / Shipping) → urgency line if real → **item 4 (mini
     review carousel), back ON for alphaforbaby as of v1.36 — see item 4
     below** — sitting right here, immediately after this whole buy-box
     block, before item 5.
     **v1.44 (7.D bug #25) — checked directly, this "3-icon trust row"
     has drifted into a text-only duplicate**: right now it renders as
     three plain text lines ("Free shipping (7–25 business days)" /
     "30-day easy returns" / "Guaranteed Safe & Secure Checkout")
     directly under the payment-icon row — this repeats claims already
     made twice above the fold (the ticker, and the header's sub-header
     trust row per bug #19) and is the "30-day return"/trust-text
     clutter Itzik asked to have removed from the product page. Delete
     this text-only line entirely; keep the real payment-icon logos
     above it (those weren't part of the complaint) and keep the
     substantive, non-redundant 30-day-return copy that already exists
     further down the page (the full description's guarantee bullets,
     the dedicated "30 days to change your mind" section, and FAQ) —
     this is about removing the repeated above-the-fold trust-badge
     clutter, not every mention of the real return policy on the page.

   **Which bundle shape to build depends on `store_mode` (v1.24) — check
   this before building anything, the two shapes are not interchangeable:**

   - **`store_mode: single_hero_product`** — same-SKU quantity-tier
     block, exact shape confirmed on starnestshop: a stack of 2-3
     selectable cards, one per quantity tier (e.g. Single / Twin /
     Family). Each card: radio-style selector, tier name, price (struck-
     through original + discounted), and a "SAVE X%" or "SAVE [amount]"
     line. The middle tier carries a **"Most Popular"** badge and is
     pre-selected by default; the top tier carries a **"Best Deal!"**
     badge and switches its paid add-ons to **"FREE"** instead (a real,
     honest incentive to size up, not a fake discount — the add-ons must
     actually be waived at checkout for that tier). Each tier nests 2-3
     add-on checkboxes directly under it (e.g. Shipping Protection,
     Extended Warranty, a small gift) — each with an icon, its own
     strikethrough-original/discounted price pair, and pre-checked by
     default. Only build this block with real, working pricing math —
     never a badge or "FREE" label that doesn't match what checkout
     actually charges (Rule 1).
   - **`store_mode: multi_product_niche`** (a catalog of several
     independent products, no single hero — e.g. alphaforbaby.com's 11
     sourced baby products) — **v1.29 REVERSAL: use the SAME same-SKU
     quantity-tier block as `single_hero_product`, not a cross-sell.**
     Earlier versions (v1.24-v1.27) assumed "nobody naturally buys 2-3 of
     the same baby carrier" and built a cross-sell "complete the set"
     bundle of 2-3 different catalog products instead. Itzik pointed at a
     second real, live, successful reference store
     (littlesnugg.store/products/baby-carrier-hoodie — confirmed directly:
     real DOM, real prices, not from memory) that proves that assumption
     wrong for exactly this product category: baby gear is bought in
     multiples all the time (gifts, siblings, baby showers, "get one for
     each grandparent's house") — littlesnugg runs a **Buy 1 / Buy 2
     (save 10%) / Buy 3 (save 35%, "BEST VALUE" badge)** same-SKU tier
     block on ONE product, on a store that is itself successful, and
     Itzik chose it explicitly over keeping the cross-sell design. So the
     `store_mode` distinction Section 5 item 3 drew in v1.24 no longer
     controls the bundle SHAPE — every product, regardless of
     `store_mode`, uses the same-SKU quantity-tier block described above
     for `single_hero_product`. (`store_mode` may still matter elsewhere
     in this skill — e.g. whether the store has one hero product driving
     the whole site vs. many independent landing pages — but it no longer
     branches Section 5 item 3.) Concretely, for alphaforbaby:
     **v1.44 override — Itzik has now dropped the third tier: build only
     Buy 1 and Buy 2, no Buy 3.** Everything below describing Buy 3 (the
     35%-off "BEST VALUE" tier and its accordion behavior) is superseded
     for alphaforbaby going forward — kept here only so old reports
     referencing it aren't misread as still-current, the same convention
     used elsewhere in this file for a rescinded item. Buy 2 stays the
     pre-selected, visually emphasized tier since there's no longer a
     Buy 3 to carry that role instead.
     - **Buy 1** — full price, no discount line.
     - **Buy 2** — **10% off**, **"MOST POPULAR"** badge (v1.31 — Itzik
       explicitly asked for this badge on Buy 2; this revises the v1.29
       note below, which read littlesnugg as having no Buy-2 badge —
       re-check littlesnugg's own live page for a Buy-2 badge before
       assuming either way, but build ours with "MOST POPULAR" on Buy 2
       regardless, that's the explicit instruction).
     - **Tier cards are a real accordion (v1.33 correction)**: v1.31 said
       a tier's per-unit selects must be "visible immediately, not behind
       an extra click" — that was misread from a static screenshot, not
       a tested interaction, and it's wrong. The actual required
       behavior, confirmed by Itzik directly testing the build: selecting
       a tier's radio is what expands ONLY that tier's per-unit Color/
       Size select rows (and its add-ons, once those exist) — any other
       tier's expanded content collapses at the same time, true
       accordion/single-open-panel behavior, not "every tier's selects
       always visible" and not "selects hidden behind a separate expand
       step distinct from selecting the radio." Selecting the radio IS
       the expand action; nothing else is needed to reveal that tier's
       rows, but an unselected tier shows no select rows at all.
     - **Per-unit preview image (v1.33)**: inside an expanded tier, each
       unit's Color/Size row gets a small preview image of THAT unit's
       currently-selected variant next to the selects (confirmed as
       wanted directly: Itzik selected different colors per unit and
       liked seeing the corresponding thumbnail update per row) — wire
       the thumbnail to update live from the real variant image data
       already used elsewhere on the page, don't hardcode one image per
       row.
     - **Buy 3** — **35% off**, **"BEST VALUE"** badge, pre-selected as
       the visually emphasized tier (matches littlesnugg's own layout —
       confirmed directly, not the starnestshop "middle tier is Most
       Popular" pattern from v1.9, since here the top tier is the one
       being pushed). Same accordion behavior as Buy 2 above: selecting
       Buy 3's radio expands its per-unit rows and collapses any other
       tier's.
     - Nest 1-2 **real, functional add-ons** under each tier (e.g.
       "Priority Delivery," "Shipping Protection") — per Rule 1 these
       must actually do something a customer is really buying (an actual
       expedited-shipping option, an actual shipping-insurance/reship
       policy), never decorative checkboxes copied from the reference
       with no real mechanism behind them; if no real version of an
       add-on exists yet, state that gap plainly rather than shipping a
       checkbox that charges for nothing.
     - **Variant pickers (Color/Size) are native `<select>` dropdowns,
       not swatch buttons or image chips** (v1.30 — confirmed directly on
       littlesnugg's live DOM: 12 real `<select>` elements, not styled
       button groups). This is a deliberate correction to whatever this
       template currently renders for variant selection — check the
       actual DOM, not just how it looks, since a styled div made to
       resemble a dropdown is not the same thing and doesn't get the
       free native mobile picker UI a real `<select>` gets for free.
       **v1.31 — this applies PER UNIT, nested inside each paid tier,
       not just once at the top of the page**: littlesnugg's Buy 2 shows
       two full rows of Color+Size `<select>` pairs (one row per unit
       being bought in that tier); Buy 3 would show three. A single
       top-of-page color picker that applies to the whole order is not
       the same thing and doesn't satisfy this — build one real
       `<select>` row per unit, nested under Buy 2 and Buy 3 specifically
       (Buy 1 only needs one row, since it's a single unit).
     - The old cross-sell "complete the set" design (2-3 DIFFERENT
       catalog products bundled together) is not being kept as a
       secondary option on this product — Itzik's decision was to fully
       replace it, not run both. If a genuinely different future product
       has no plausible "buy multiple" use case at all, flag that
       specifically to Itzik rather than defaulting back to cross-sell
       silently.

     **Margin check (kept from v1.27, same discipline, now per quantity
     tier instead of per product combination):** before calling this
     done, compute real margin — (discounted price − landed cost × qty)
     ÷ discounted price — for the Buy 2 (10% off) and Buy 3 (35% off)
     tiers, against the real landed cost of the specific product, and
     compare to the 30% floor (2.A.5). A steep discount like 35% is much
     more likely to threaten margin than 5-10% was — don't assume it's
     fine just because littlesnugg does it; their landed cost isn't
     yours. Paste the actual numbers in the report, same as before.

     **How to wire this in Shopify:** a single quantity-tiered automatic
     discount (or a small Shopify Function) on this SKU, not the
     two-separate-discounts approach from v1.27 — a same-SKU quantity
     break is simpler to get right than a cross-product one since there's
     only one product's price involved, but still verify the actual tier
     that applies at quantity 2 and quantity 3 with a real test cart
     rather than trusting the Admin discount configuration alone.
4. **Mini review carousel — back ON for alphaforbaby (v1.36), at a
   CORRECTED position.** History: v1.30 introduced it (confirmed on
   littlesnugg), v1.34 fixed it from "never actually built, leaving an
   empty gap" to a real section with reviewer photos, v1.35 removed it
   after Itzik saw it sitting in the gap between the price and the
   bundle block and didn't want it there. **v1.36: a fresh littlesnugg
   screenshot confirms this exact carousel is real and belongs on the
   page — just NOT in that gap.** The real position, confirmed directly:
   AFTER the entire buy-box block — below the primary CTA, the
   "purchase options" payment-method row, and the 3-icon trust row —
   sitting before item 5 (benefit bullets)/the video-lifestyle section.
   Do not place it between the price and the bundle block again; that
   specific gap should stay closed per v1.35. Design (unchanged from
   v1.34): a short horizontal carousel of 3-4 real review cards, each
   with a small round photo of the actual reviewer, name, 1 short real
   sentence, AND a filled gold 5-star row (confirmed present in the
   v1.36 screenshot — this reverses v1.30's original "no star row"
   wording), with dot pagination beneath the cards matching the gallery
   dots' style. Populate from the same real review source as item 14
   (7.C, Section 1 Rule 1) — pull the 3-4 shortest, punchiest real
   quotes that also have a real photo attached, rather than writing new
   ones; never fabricate a quote, a star rating, or a photo to fill
   this carousel if fewer than 3 real reviews with photos exist — ship
   it with what's real (even fewer than 3) or, only if truly zero
   exist, state that gap plainly rather than leaving an unexplained
   blank gap on the page.
   **v1.44 (7.D bug #23) — checked directly, each card currently has a
   visible border/outline around it**: remove the card border entirely,
   the cards should sit borderless (just the photo/stars/quote/name,
   no framing box), per Itzik's direct ask. **Also (7.D bug #24):
   Itzik wants the real product-demo video (item 10 below) moved to sit
   immediately after this carousel, before item 5's benefit bullets** —
   see item 10's v1.44 note for the exact new position; don't leave it
   in its old spot several sections further down the page.
5. **Benefit bullets** (3-5 items): icon + bold micro-headline + one
   sentence. Formula in 6.C. This is the single highest-leverage section
   for a 14B model to get right — see formula, do not free-write these.
6. **"Why it works" / mechanism section**: 1 short paragraph or 3-step
   visual explaining HOW the product delivers the benefit (not just that
   it does). Builds believability.
7. **Image + headline card #1 (v1.30 — NEW, confirmed on littlesnugg)**:
   one real, clean lifestyle photo in a rounded card, with a short bold
   headline overlaid or set beside it (littlesnugg's example: "YOUR
   BABY, RIGHT WHERE THEY BELONG 🤍") — one clear emotional benefit
   stated in a handful of words, not full sentences. Use a real sourced
   CJ lifestyle photo (never a composite, per 7.D bug #12) or a real
   generated image consistent with Section 1's honesty rules.
8. **Size / fit guide (v1.30 — NEW, confirmed on littlesnugg: "Let us
   find the right size for you")**: only build this for products where
   size/fit is a real variant dimension (clothing, carriers, anything
   with S/M/L-style options) — a simple size chart or a short "how to
   measure" block tied to the product's real variant options. Skip
   entirely (don't force a fake size guide) on a product with no size
   variants at all.
9. **Lifestyle / in-context image block**: large image(s) showing the
   product doing its job, with a short supporting headline overlay.
10. **Video + headline card (v1.30 — NEW, confirmed on littlesnugg)**:
    one real supplier/product video in the same card treatment as item
    7 (image + short bold headline), e.g. littlesnugg's "SOFT ENOUGH TO
    LIVE IN 🤍" card. Use the product's real `supplier_video_url`
    (Section 4) — never a stock/unrelated clip captioned as this
    product.
    **v1.44 — reposition this card (7.D bug #24).** Checked directly:
    alphaforbaby's real video currently sits inside a "Three ways to
    wear it" section, many sections below the mini review carousel
    (past benefit bullets, the mechanism section, and a size-guide
    accordion). Itzik wants the sequence to read purchase-options row →
    mini review carousel (item 4) → this video, immediately — move this
    card to sit directly after item 4 and before item 5's benefit
    bullets. The later "Three ways to wear it" content can stay where
    it is as its own explainer section if it's carrying real how-to-use
    detail beyond the video itself; only the video's own primary
    placement is what's moving.
11. **Video gallery — additional real videos (v1.30 — NEW, confirmed on
    littlesnugg: 4 total `<video>` elements across the page under a
    header like "LITTLE MOMENTS IN THE LITTLESNUG 🐻")**: a small grid
    of further real video clips. **Honesty caveat, check this every
    time**: littlesnugg's own product apparently has multiple real
    camera angles/clips to draw on; most of our CJ-sourced products
    (alphaforbaby included, per the already-compiled real-video list)
    have exactly ONE real supplier video per product. Do not pad this
    section by duplicating the single real clip multiple times or by
    inventing/generating extra "video" content to hit a 3-4 count —
    that violates Rule 1 exactly like a fake review would. If only one
    real video exists, either (a) build a genuinely smaller gallery (1
    video, honestly sized, not stretched to look like a 4-item grid) or
    (b) source/produce additional REAL footage first (e.g. a UGC-style
    unboxing/demo clip you actually shoot or commission) — state
    explicitly in your report which of these you did and why, never
    ship a padded fake gallery silently.
12. **Comparison or before/after block** (optional but strong when
    applicable): "Without X / With X" two-column, or "Us vs. the old way"
    table.
13. **FAQ accordion**: 4-6 questions, formula in 6.F. **v1.30 addition,
    confirmed on littlesnugg**: prefix each question with a relevant
    emoji (littlesnugg also shows a small check-box-style icon before
    each question) — pick a genuinely relevant emoji per question
    (🍼 for feeding-adjacent, 📏 for sizing, 🧼 for washing/care, etc.),
    not the same emoji repeated for every item. Littlesnugg's own
    question set is a good structural reference (age/weight range,
    safety, sizing, warmth, washing, delivery) — cover whichever of
    these actually apply to this product plus anything real customers
    would actually ask.
14. **Social proof — reviews grid, "reviews speak for themselves"
    (final large review section)**: a header line ("Loved By
    [Customers]" or similar) plus a "[X.X] out of 5 · [N] reviews"
    summary line, then a 3-column grid of review cards — exact shape
    confirmed on starnestshop: a real customer/lifestyle photo of the
    product in use (not a studio shot) on top, a filled 5-star row in
    `--color-accent` below it, a 1-2 sentence quote, the reviewer's bold
    first-name-plus-last-initial, a small gray line naming the specific
    variant they bought, and a "✓ Verified buyer" badge in the accent
    color. Populate per Section 1, Rule 1 — real CJ/hand-off-reported
    reviews first (2.D step 4), then a legitimate import app, then an
    honest empty state (7.C) — never fabricate the photo, name, or badge.
    **v1.30 — this is the section Itzik means by "images that speak for
    themselves"**: pay real attention to card sizing (big enough that a
    photo actually reads, not a cramped thumbnail), image clarity (use
    the real, non-compressed photo asset, not a re-scaled-down copy),
    and making the star row genuinely legible (filled, high-contrast,
    not tiny) — a technically-present-but-tiny-and-blurry version of
    this section fails the intent even if every field is populated.
    **v1.41 — confirmed via direct screenshot this is STILL a cramped-
    thumbnail version, not the spec.** Real reviews, real star rows,
    real verified badges are all present and correctly populated — the
    ONLY problem is presentation: each review's photo renders as a
    small square thumbnail sitting inline below the quote text, not a
    large photo filling the top of the card the way this item (and the
    real littlesnugg reference) describes. Treat this as a production
    gate, not a nice-to-have: don't report it fixed until a real
    screenshot shows large, photo-forward cards.
15. **Guarantee / risk-reversal block**: restated bigger — icon + 2-3
    sentence money-back / satisfaction guarantee, standalone section (not
    just the small icon row), because risk reversal deserves its own
    visual weight right before the close.
16. **Secondary CTA block**: product image + price + button again, for
    people who scrolled all the way down without buying.
17. **Footer** — comes last, after everything above, per littlesnugg's
    own structure and Itzik's explicit instruction: payment method
    icons row, policy links (Refund, Privacy, Terms, Shipping, Contact),
    email signup, copyright. **v1.44 — the Contact page itself (linked
    here) has a real content bug, checked directly**: its "Business
    details" text reads "ALPHA FOR BABY is operated by ALPHA FOR BABY,
    registered in Israel." — remove the "registered in Israel" phrase
    (Itzik asked for this directly); keep the rest of that section
    (the operating-entity name and the support contact) as-is.
18. **Sticky bottom mini-cart bar — REMOVED for alphaforbaby (v1.33)**:
    previously required (NOT mobile-only, confirmed on starnestshop
    running on desktop too, appearing once the user scrolls past the
    main buy box: mini product thumbnail + name + price + variant
    dropdown + Add-to-Cart button in one slim horizontal bar). Itzik
    explicitly asked to remove this floating bar from alphaforbaby's
    product page — with the tiered bundle already surfacing its own
    contextual "ADD [N] TO CART" button at the point of selection, a
    second persistent floating CTA reads as redundant clutter rather
    than a helpful safety net, and it was also one contributor to the
    "too many Add to Cart buttons" pattern in 7.D bug #13. Treat this
    item as OPTIONAL going forward, not a default requirement — build
    it only when a future product's page genuinely lacks any other
    persistent path to purchase (e.g. a long page with no tiered bundle
    CTA already visible on scroll), and confirm with Itzik first rather
    than defaulting it back in.
19. **Section dividers**: use a soft SVG wave/curve shape between at
    least two section backgrounds (confirmed on starnestshop, between
    the lifestyle carousel and the reviews section) rather than a hard
    flat-color edge everywhere — cheap to build (inline SVG or a CSS
    clip-path), see 8.C for the concrete pattern.

Optional additions when the product/budget supports them: "As Seen In"
press-style logo row (only with real placements — never invented press
mentions); founder/brand story block with a real or clearly-
illustrative photo (see beelyra.com's founder-story paragraph for the
tone — first-person, specific, names a real-feeling person and
situation, not generic "our mission" copy).

**v1.44 — general compactness note, applies to the whole product
page**: Itzik's own words, "הכל צריך להיות יוצר צפוף בלי הרבה רווחים"
(everything should read tight/compact, without a lot of spacing). This
isn't a single item's fix — after making the specific v1.44 changes
above, do a pass over the whole page's vertical padding/margins and
tighten them generally; the real page currently reads airier throughout
than the littlesnugg reference it's matched against.

## v1.53 shipped (v2.2, 2026-09-21) — Ratings & Reviews now sits under the video

Implemented in the one shared template `app/routes/products.$handle.jsx`,
so all products moved together. The `id="reviews"` anchor moved with the
block, so the star row's "(N Reviews)" link still lands on it, and the
`pb-[100px]` the mobile sticky bar needs moved onto the benefits/FAQ/
guarantee container, which is now the last block on the page.

Verified on the rendered page rather than in the source — byte offsets in
the carrier's served HTML: `<video>` 58883 → `id="reviews"` 59185 →
"Ratings &amp; Reviews" 59297 → "Why parents" 88783 → "Full description"
103452 → "Frequently asked" 107263 → "change your mind" 111957. Enforced
by `TestReviewsUnderVideo`.
