<!-- Level 6 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 5C. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 5C. PDP PARITY GATE — every product page must match the carrier page

**Why this section exists (v1.49).** Itzik's standing instruction is
literal: *every* product page in this store must look like
`/products/ergonomic-baby-hip-carrier`. He has now had to repeat that
three times, and each time a "done" report came back while the real
non-carrier pages were still missing most of the page. The failure mode
is consistent and it is not a copy problem: **the carrier page is fully
built and the other pages render a thin subset of it, while the build
report describes the intended page rather than the rendered one.**
Checked directly on the real dev build (v1.49) — `/products/
foldable-portable-baby-crib` and `/products/glow-whale-bath-buddy`
render with **no price, no variant picker, and no Add to Cart button
anywhere in the DOM** (verified: `document.querySelectorAll('select')`
→ 0, no element matching /add .. to cart/i, no `$` anywhere in the
rendered text, "Buy more, save more" absent from the entire document),
even though the data is present — the crib's own JSON-LD on that same
page carries `"offers":{"priceCurrency":"USD","price":"152.90"}`. So
the buy box is **product-gated in the code, not missing data**: find
the conditional/handle-specific branch that renders it only for the
carrier and make it product-agnostic. A product page a shopper cannot
buy from is worse than an unbuilt page, because it looks finished.

**The parity gate is a diff, not a vibe.** Before reporting any product
page done, render BOTH that page and the carrier page at 375px width
and confirm every row below is present on the new page. Report it as
this exact table, one row per component, with present/absent measured
on the rendered page (not read off the component source):

| # | Component (as it exists on the carrier page) | Must appear |
|---|---|---|
| 1 | Announcement ticker strip above the header | yes |
| 2 | Header: centered wordmark, hamburger flush left, cart flush right | yes |
| 3 | Gallery with dot pagination (see the dot-count rule below) | yes |
| 4 | Urgency ticker line — "SELLING QUICK, LOW STOCK" (v1.45 decision) | yes |
| 5 | "Join [N] verified buyers" strip: real avatar photos, each with a checkmark badge, headline text present, no line wrap | yes |
| 6 | Product title below the gallery/urgency/avatar block | yes |
| 7 | Star row + "([N] Reviews)" — real imported count, single clean row | yes |
| 8 | "Buy more, save more" heading | yes |
| 9 | Buy 1 / Buy 2 tier cards, Buy 2 badged MOST POPULAR and pre-selected | yes |
| 10 | "CHOOSE EACH ONE" per-unit variant `<select>` row (one per unit) | yes |
| 11 | Real price per tier, `.90`-ending charged total, honest struck-through anchor | yes |
| 12 | "ADD [N] TO CART" primary CTA that actually adds to cart | yes |
| 13 | Real payment-icon row under the CTA (icons only, no repeated trust text) | yes |
| 14 | Mini review carousel, borderless cards, real name/flag/quote/stars | yes |
| 15 | Real product-demo video immediately after the mini carousel | yes |
| 15b | **"Ratings & Reviews" block (real average, count, photo-forward cards) IMMEDIATELY after the video, before the benefit sections — v1.53, Itzik's explicit order** | yes |
| 16 | Structured benefit sections (the carrier's "Why parents choose it" equivalent) — NOT a raw "Full description" dump | yes |
| 17 | Comparison block ("why ours" vs the obvious alternative) | yes |
| 18 | Guarantee / "30 days to change your mind" section | yes |
| 19 | FAQ block with real per-question emoji | yes |
| 20 | (moved — see row 15b, v1.53) | — |
| 21 | Sticky add-to-cart bar on mobile | yes |

**v1.53 — page order change, Itzik's explicit decision: the full
"Ratings & Reviews" block moves up to sit directly under the product
video**, before "Why parents choose it" and everything after it. It is
no longer the last section on the page. The resulting order below the
buy box is: mini review carousel → video → **Ratings & Reviews** →
benefits → size & shipping → how to use → why it works → lifestyle →
comparison → full description/specs → FAQ → guarantee → footer. Keep
`id="reviews"` on the moved block so the star row's "(N Reviews)"
anchor link still jumps to it, keep the bottom padding that the sticky
mobile bar needs on whatever section is now last, and apply this to
the ONE shared template (`app/routes/products.$handle.jsx`) so all 9
products change together — never per product. This supersedes every
earlier "reviews last" note in Section 5 (item 14) and in the route's
own comments. Enforced by `TestReviewsUnderVideo` (Section 12).

Measured page weights at v1.49, as a crude but useful smell test: the
carrier's SSR HTML is ~225kb, the crib's ~121kb, Glow Whale's ~44kb. A
"finished" product page that renders at half the reference page's size
is not finished — check the table before reporting.

**Gallery dot-count rule (v1.49):** the crib page renders ~21
pagination dots in one row at 375px width (the carrier has 13) — a
full-width band of dots that reads as a glitch. Cap the visible dots
(e.g. a windowed 5-7 dot group with the active one centred, or switch
to a "3 / 21" counter) instead of printing one dot per image.

## Parity status at v2.2 (2026-09-21)

8 of the 9 product pages now render every component the carrier renders —
measured with `TestPdpParityGate::test_renders_every_reference_component`,
which diffs structural hooks on the rendered page against the carrier
rather than reading component source. The 9th, Glow Whale, is deliberately
unbuilt and is recorded as such in `conftest.py`'s `PAUSED_HANDLES`.

**Row 5 ("Join [N] verified buyers") — how the count stays honest.** The
strip was rendering on the carrier only, and the cause was the data source,
not the component: `agBuyerCount` came solely from the AG Product Reviews
app's approved-count summary, and only the carrier has AG data, so the
other eight passed `0` and the component hid the count. It now falls back
to the imported `custom.reviews` count when the app has nothing — also a
real count of real reviews, so Rule 1 holds. Live: carrier 20 (the app's
own approved count), crib 23, Domino 60, Nest 27. A product with no
reviews renders no strip at all, which is the correct empty state.

**Do not read a parity failure off a parallel test run.** At `-n 8` this
gate reported entire sections missing on pages that were serving them
correctly — see 7.D #38 before acting on any such finding.
