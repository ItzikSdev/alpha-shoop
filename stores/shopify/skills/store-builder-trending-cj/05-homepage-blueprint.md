<!-- Level 5 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 5B. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 5B. HOMEPAGE BLUEPRINT — exact section order (new in v1.43)

This is the storefront homepage (`/`), not the product page — a
separate blueprint from Section 5 above. Itzik asked directly for a
major simplification of it; build to this exact shape, don't guess at
a fuller version.

**Real current homepage, confirmed via direct live check (2026-09-12,
mobile viewport, not from memory) before this rewrite** — this is what
exists today and what the instructions below are changing: announcement
ticker → header → hero (eyebrow "EVERYDAY BABY ESSENTIALS", headline
"Everything baby needs. All in one place.", description paragraph,
"SHOP THE COLLECTION" + "OUR STORY" buttons, "1,000+ HAPPY PARENTS"
stat, then a large hero image with visible dot pagination — this dot-
paginated image block is the "סליידר של תמונות"/image slider Itzik
means) → a 4-icon trust-bar row → "Shop by category" (3 cards: Baby
Boys / Baby Girls / Unisex — generic and stale now given the catalog
pivot to toys/gear) → an old "Shop All" section (a plain 3-column grid
using raw, unedited CJ supplier photos — one visibly still has Chinese
packaging text in it, confirming these were never the polished,
skill-built product images) → a 6-card testimonial/review grid (2 rows
× 3, 5-star quotes, "Name — City ✓ Verified buyer" format) → footer.

**New required order (v1.43):**

1. **Announcement ticker** — unchanged, keep as-is.
2. **Header** — unchanged, keep as-is (Section 5 item 2's spec still
   governs it).
3. **Hero copy block** — keep the eyebrow, headline, description
   paragraph, the "SHOP THE COLLECTION" and "OUR STORY" buttons, and
   the "1,000+ HAPPY PARENTS" stat line exactly as they are today.
   **Delete the hero image slider itself** — the large image with dot
   pagination is removed entirely; nothing replaces it in that exact
   spot, because what replaces it is the next item, immediately below
   the buttons/stat.
4. **All-products grid (new — this is what replaces the slider)**:
   directly after the hero buttons/stat, show every currently ACTIVE
   product in the store, 2 items per row on mobile. Pull this list live
   from the real Shopify catalog/collection (whatever is actually
   published and not archived per Section 2.F) — never hardcode a
   product list here, since the set of active products changes as the
   remaining 8 trending products get built out one at a time. Each card:
   the product's real photo (its edited hero shot if the product has
   already been through a full Section 3 build, otherwise its best real
   CJ photo), title, price, and a link to its PDP. Reuse whatever real
   product-card/collection-grid component already exists in the
   template (Section 10) — do not hand-roll a new card component, and
   do not reuse the old "Shop All" section's raw-image grid markup,
   which this item fully replaces. 2 columns is the explicit, literal
   ask for mobile; if a wider desktop breakpoint looks obviously
   cramped or empty at exactly 2 columns, more columns there is a
   reasonable call to make, but confirm with Itzik rather than assuming
   — don't silently redesign the mobile layout itself away from 2.
   **v1.46 — checked directly, this item wasn't actually implemented as
   specified (7.D bug #26).** The real grid still shows exactly 3
   products (Foldable Portable Baby Crib, Glow Whale Bath Buddy,
   Ergonomic Baby Hip Carrier) — the same fixed 3 as the old "Shop All"
   section this item was supposed to replace, not a live query against
   all active products. One card (Glow Whale Bath Buddy) uses a raw,
   un-edited CJ supplier photo with visible foreign packaging text —
   exactly the un-polished asset this item says to avoid unless a
   product hasn't been through Section 3 yet, in which case it should
   still be the product's *best real* photo, not a supplier box shot.
   Fix: wire the grid to a real live query (a collection or "all active
   products" query), not a hardcoded 3-item list.
5. **Footer** — comes immediately after the product grid, with nothing
   else in between. Same shape as Section 5 item 17.

**Delete entirely** (per Itzik's own words, "כל השאר למחוק" — delete
everything else): the 4-icon trust-bar row, the "Shop by category"
3-card block, the old "Shop All" raw-image 3-item grid (superseded by
item 4 above), and the 6-card testimonial/review grid. These aren't
hidden or deprioritized — remove them from the page entirely, the same
"remove, don't conditionally hide" standard as 7.D bug #9.

**v1.44 — general spacing note, independent of the rebuild above**:
Itzik separately flagged that the homepage has too much spacing/margin
throughout ("יותר מידי רוויחים"). Apply this once the rebuild above
lands: tighten vertical padding/margins across whatever sections remain
(hero, the new product grid, footer) rather than leaving the old,
airier spacing now that there's less content on the page overall.

**v1.46 — reported done in v1.44, not confirmed on re-check.** Sol's
v1.44 report claimed this was fixed ("Hero/section padding tightened
via .tob-home rules"), but checked directly on the real page, the gaps
around the stat line and the footer still read generously spaced, not
visibly tighter. Either the CSS change didn't actually ship, or it
wasn't enough to read as fixed — re-check with an actual before/after
comparison (real computed padding values, not just "rules changed")
before reporting this done again.

**v1.47 — measured directly, real progress but not enough yet.** The
next round's footer fix is genuinely real: footer `padding-top` went
60px→36px and `margin-top` 72px→32px (measured via computed styles,
not a screenshot guess) — about a 48% cut. Itzik still says it isn't
tight enough. **Concrete target this time, not open to interpretation:
cut the footer's combined top padding+margin to roughly 24-32px total**
(currently ~68px combined) — closer to how tightly littlesnugg's own
page stacks sections, per this file's usual reference standard. Apply
the same tightening logic to any other section-to-section gap on the
homepage that's still ≥50px combined, not just the footer.

**v1.49 — the footer gap target was MET; the remaining homepage
airiness is somewhere else, measured on the real dev build
(localhost:3001, 375px mobile viewport).** Footer now measures
`padding-top: 20px` + `margin-top: 12px` = **32px combined** — inside
v1.47's 24-32px target, so that specific item is closed, don't keep
re-cutting it. Itzik still reports too much space on the homepage, and
the real numbers say the space is now in two other places:
1. **The hero block is 555px tall on an 812px viewport** — nearly the
   whole first screen is hero text before a single product is visible.
   Internal gaps measured: hero `padding-top` 20px, then a 44px offset
   to the eyebrow, eyebrow→H1 gap **37px**, H1 (40px type, 124px tall
   over 3 lines), button→"OUR STORY" link gap **25px**, then a 69px
   stat block ("1,000+ / HAPPY PARENTS"). Target: get the hero block
   under ~400px at 375px width so the product grid starts above the
   fold — tighten the 37px and 25px gaps to ~12-16px, and reduce the
   H1 to 2 lines at this width (either shorter copy or a slightly
   smaller clamp), rather than shaving 2px off everything uniformly.
2. **The footer block itself is 760px tall on mobile** — bigger than
   the product grid (628px) and 37% of the whole page. It's 4 stacked
   link columns (`.tob-fcols` 534px, with 30px row gaps) plus a 54px
   payment row carrying `margin-top: 36px`, plus a 64px bottom bar
   carrying `margin-top: 20px` AND `padding-top: 22px`. On mobile,
   collapse the four columns into two side-by-side columns (or
   accordions), drop the row gap to ~16px, and cut the payment-row and
   bottom-bar margins to ~16px each. Target: footer block under ~420px
   at 375px width.
The product grid itself is already tight (`padding-top: 10px`,
`row-gap: 6px`) — leave it alone.
