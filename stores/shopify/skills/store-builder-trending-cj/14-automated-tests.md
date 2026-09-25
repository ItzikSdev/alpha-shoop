<!-- Level 14 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 12. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 12. AUTOMATED COMPLIANCE TESTS (pytest, v1.25)

Section 11 depends on remembering to check the right thing every time —
in practice, real misses got through it anyway (the v1.24 `store_mode`
gap, the v1.23 CJ-text-hidden-in-an-accordion near-miss). Whatever in
Section 11 can be checked mechanically now has a real, runnable test
instead of a remembered step. This does not replace human judgment on
subjective items (color pop, motion variety, layout order, copy
quality) — it owns the objective, checkable ones.

Setup once per environment: `pip install pytest pytest-playwright &&
playwright install chromium`. Run with `pytest tests/test_pdp_compliance.
py -v --base-url http://localhost:3001` (or whatever the real dev-server
URL is) before calling any product page done, and again after any fix
claimed to address a failure — a fix isn't done until its test passes,
not until you believe it should pass.

**v1.50 — what this suite now covers, and the two rules that make it
mean something.** It grew from 4 classes to 10 (47 tests) because the
old shape could pass while the store was visibly broken:

| Class | Owns |
|---|---|
| `TestCatalogCoverage` | the suite's own coverage — fails if a confirmed-trending product isn't served by the storefront, or an unexpected product is |
| `TestSection11Compliance` | the long-standing Section 11 mechanics (supplier identity, one video, purchasable, review lightbox, …) |
| `TestPdpContentContract` | one test per `custom.pdp_content` key (Section 5D) — each failure names the metafield field to author |
| `TestPdpParityGate` | Section 5C — every component the reference page renders must render on the page under test |
| `TestNoSkeletonPages` | h2-section count and page weight versus the reference page |
| `TestV149Regressions` | 7.D #27-#30 (star alignment, webfont actually loading, buy box present, every product URL 200) |
| `TestV144ProductPageFixes` | 7.D #19-#25 |
| `TestHomepageCompliance` / `TestHomepageDensity` | Section 5B structure, plus hero/footer pixel budgets at 375px |
| `TestContactPage` | the business-details copy |
| `TestReviewGate` / `TestHiddenProductsStayHidden` | v2.1: live products have ≥ 15 photo reviews that load; hidden products 404 and appear nowhere |
| `TestHeroImage` | v2.2: gallery + hero come only from CJ images, every uploaded image passed the pixel/Chinese-text checks, the hero is really position 1, no review photo in the gallery |

Rule 1: **coverage is derived, never typed.** `PRODUCT_HANDLES` comes
from `/collections/all` at collection time. Every run tests every
product the store actually serves. Adding a product and not adding a
test is no longer possible, and a catalog that's missing a product
fails `TestCatalogCoverage` instead of quietly narrowing the run.

Rule 2: **a "done" report pastes real `pytest -v` output, not a
paraphrase.** If the suite can't run in your environment, that is the
first thing to fix and to say out loud — an unrunnable suite is why
four rounds of "fixed" reports and four rounds of Itzik finding the
same problems could coexist. `requirements.txt` already pins
`playwright>=1.62.0` and notes that `playwright install chromium` is
not run automatically; run it once, then run the suite.

Starter file — extend this, don't rewrite it from scratch each time; add
a new test the same day you find a new bug worth checking for
permanently, the same way 7.D's bug list grows:

```python
"""
Section 11 compliance, as executable pytest tests (store-builder-skill.md v1.25).

Why this exists: manual "I checked and it's fine" reports have been wrong
multiple times on real builds in this session alone — CJ text hidden inside
collapsed accordions that a plain innerText check missed, a canonical-host
redirect that silently bounced localhost to production, autoplay attributes
assumed set without reading the actual DOM property. A pytest suite removes
the ambiguity: a test either passes or it doesn't, the assertion message says
exactly what failed, and `pytest -v` output is what gets pasted into a "done"
report — not a paraphrase of it.

Requires: pip install pytest pytest-playwright && playwright install chromium
Run against a live dev server: pytest tests/test_pdp_compliance.py -v \
    --base-url http://localhost:3001

v1.50 — PRODUCT_HANDLES is NO LONGER a hand-maintained list. Every run before
this one tested exactly one product (the carrier) and came back green while
other live product pages had no buy box at all; a hand-maintained coverage list
is a coverage lie waiting to happen, because the step that gets skipped is
always "add the new handle." The list is now derived from the real storefront
catalog at collection time, and TestCatalogCoverage fails when the live catalog
and the trending shortlist disagree.
"""
import json
import os
import re
import urllib.request

import pytest

# Shopify's own view of price/availability comes from the Liquid storefront's
# product JSON, which is public and needs no token: /products/<handle>.js.
# v1.51 added tests against it because the Hydrogen page was rendering
# "sold out" perfectly correctly while the DATA behind it was wrong (7.D #31).
SHOP_DOMAIN = os.environ.get("SHOP_DOMAIN", "kgg8n0-k0.myshopify.com")


@pytest.fixture(scope="session")
def shop_domain():
    return SHOP_DOMAIN

# The 9 products Itzik confirmed as the trending shortlist (Section 2.F). This
# is the EXPECTATION; the live catalog is the REALITY; TestCatalogCoverage
# compares them and fails on any gap in either direction.
TRENDING_SHORTLIST = [
    "ergonomic-baby-hip-carrier",
    "foldable-portable-baby-crib",
    "glow-whale-bath-buddy",
    "automatic-domino-train-set",
    "montessori-shape-sorting-egg",
    "toddler-sensory-learning-board",
    "baby-beach-sun-shelter",
    "foldable-baby-bed-canopy-set",
    "cozy-portable-baby-nest",
]

REFERENCE_HANDLE = "ergonomic-baby-hip-carrier"

# v2.1 — Level 01 rule 7: a product needs >= 15 reviews WITH a real,
# loading photo to be displayed. Products below the gate are hidden
# (Draft / unpublished), never deleted. Keep this list in sync with the
# table in Level 02, Section 2.G.
MIN_PHOTO_REVIEWS = 15
REVIEW_GATE_HIDDEN = [
    "foldable-baby-bed-canopy-set",     # 13 with photos
    "cozy-portable-baby-nest",          # 11
    "toddler-sensory-learning-board",   # 4
    "baby-beach-sun-shelter",           # 3
    "foldable-portable-baby-crib",      # 1
    "glow-whale-bath-buddy",            # 0 (also paused on its defect finding)
]
HERO_SELECTION_DIR = os.environ.get(
    "HERO_SELECTION_DIR", "store-profiles/alphaforbaby/hero-selection"
)
VARIANT_IMAGES_DIR = os.environ.get(
    "VARIANT_IMAGES_DIR", "store-profiles/alphaforbaby/variant-images"
)


def _catalog_handles(base_url):
    """Every product handle the storefront actually serves right now.

    Read from /collections/all rather than a literal list, so a product that
    exists in the store but was never added to a test list still gets tested,
    and a product that 404s shows up as missing instead of silently untested.
    """
    try:
        with urllib.request.urlopen(f"{base_url}/collections/all", timeout=20) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — a dev server that isn't up is a skip, not a pass
        return []
    seen = []
    for match in re.finditer(r"/products/([a-z0-9][a-z0-9-]*)", html):
        handle = match.group(1)
        if handle not in seen:
            seen.append(handle)
    return seen


def _base_url_for_collection():
    """pytest fixtures aren't available at import time, where parametrization
    happens — read the same --base-url value straight off sys.argv, falling
    back to the usual dev-server URL."""
    import sys

    for i, arg in enumerate(sys.argv):
        if arg == "--base-url" and i + 1 < len(sys.argv):
            return sys.argv[i + 1].rstrip("/")
        if arg.startswith("--base-url="):
            return arg.split("=", 1)[1].rstrip("/")
    return "http://localhost:3001"


# Coverage = whatever the live storefront serves, union the reference product so
# the parity baseline is always in the run even on a broken catalog.
_LIVE = _catalog_handles(_base_url_for_collection())
PRODUCT_HANDLES = _LIVE or [REFERENCE_HANDLE]

SUPPLIER_MARKERS = ["cjdropshipping", "cf.cjdropshipping", "video-cf.cjdropshipping"]


def _goto(page, base_url, handle):
    page.goto(f"{base_url}/products/{handle}")
    page.wait_for_timeout(1500)


def _expand_all_accordions(page):
    # 7.D bug #6 lesson: supplier-identity text can hide inside a collapsed
    # accordion/FAQ panel that innerText still returns once expanded — click
    # every disclosure control before scanning text, don't scan the
    # collapsed-by-default state.
    for trigger in page.query_selector_all(
        "[aria-expanded], button:has-text('?'), details summary"
    ):
        try:
            trigger.click(timeout=500)
        except Exception:
            pass
    page.wait_for_timeout(300)


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestSection11Compliance:
    def test_no_supplier_identity_in_text(self, page, base_url, handle):
        """7.D #6 — no 'CJ'/supplier name anywhere, incl. inside expanded accordions."""
        _goto(page, base_url, handle)
        _expand_all_accordions(page)
        text = page.inner_text("body")
        assert not re.search(r"\bCJ\b", text), "literal 'CJ' found in rendered text"
        for marker in SUPPLIER_MARKERS:
            assert marker not in text.lower()
        # also check the supply-chain *concept*, not just the string "CJ" —
        # v1.23's own incident: "Supplier demo video" caption, "The supplier
        # lists..." FAQ copy. Flag these phrases for a human to judge; a
        # false positive here is cheap, a missed leak is not.
        for phrase in ["supplier lists", "supplier demo", "from our supplier",
                       "dropship", "third-party seller"]:
            assert phrase.lower() not in text.lower(), f"supply-chain tell: '{phrase}'"

    def test_no_supplier_identity_in_assets_or_head(self, page, base_url, handle):
        _goto(page, base_url, handle)
        for el in page.query_selector_all("img, video, source"):
            src = (el.get_attribute("src") or "")
            assert not any(m in src.lower() for m in SUPPLIER_MARKERS), src
        head_html = page.eval_on_selector("head", "el => el.innerHTML")
        for marker in SUPPLIER_MARKERS:
            assert marker not in head_html.lower()

    def test_no_raw_markdown_in_rendered_text(self, page, base_url, handle):
        """7.D #7"""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "```" not in text

    def test_gallery_video_autoplay_muted_loop(self, page, base_url, handle):
        """7.B Slot 2 spec, corrected v1.33: <video autoPlay muted loop
        playsInline> with NO controls attribute — Itzik wants it
        non-interactive, not stoppable/clickable by the shopper."""
        _goto(page, base_url, handle)
        videos = page.query_selector_all("video")
        if not videos:
            pytest.skip("no real product video sourced for this pid — flagged gap, not a failure")
        for v in videos:
            assert v.evaluate("el => el.autoplay") is True
            assert v.evaluate("el => el.muted") is True
            assert v.evaluate("el => el.loop") is True
            assert v.evaluate("el => el.hasAttribute('controls')") is False, (
                "video has native controls — v1.33 requires none, shopper "
                "should not be able to pause/scrub it"
            )

    def test_exactly_one_video_instance_on_page(self, page, base_url, handle):
        """v1.23 incident: the same single real clip was embedded twice
        (gallery slide 0 + HowToUseSection) as two independent players."""
        _goto(page, base_url, handle)
        videos = page.query_selector_all("video")
        assert len(videos) <= 1, (
            f"found {len(videos)} <video> elements — if there is only one "
            "real source clip for this product, it must appear once, not "
            "duplicated across sections"
        )

    def test_purchasable(self, page, base_url, handle):
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "SOLD OUT" not in text
        assert page.query_selector("text=ADD TO CART") is not None

    def test_no_dead_write_review_form(self, page, base_url, handle):
        """7.C / 7.D — a review form must not render unless wired to a real save."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "Write a review" not in text, (
            "a review submission form is present — confirm it actually "
            "persists somewhere real, or remove it (v1.23)"
        )

    def test_review_photos_have_lightbox(self, page, base_url, handle):
        _goto(page, base_url, handle)
        photos = page.query_selector_all("[data-review-photo], .review-photo img")
        if not photos:
            pytest.skip("no review photos on this product yet")
        photos[0].click()
        page.wait_for_timeout(300)
        modal = page.query_selector("[role=dialog], .lightbox, [data-lightbox-open]")
        assert modal is not None, "clicking a review photo did not open an enlarged view"
        # close paths: Escape, click-outside, explicit close button — all three
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        assert page.query_selector("[role=dialog], .lightbox, [data-lightbox-open]") is None

    def test_review_dates_not_shown(self, page, base_url, handle):
        """v1.23 — real review dates that predate the store's launch must
        not be displayed verbatim (2021-style dates on a 2026 launch)."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert not re.search(r"\b(19|20)\d{2}\b.{0,15}(review|verified)", text, re.I), (
            "a 4-digit year appears near review content — confirm dates are "
            "hidden, not just reformatted"
        )

    def test_bundle_is_quantity_tier(self, page, base_url, handle):
        """Section 5 item 3, v1.29 — same-SKU quantity tiers (Buy 1/2/3)
        are now the required shape for EVERY product regardless of
        `store_mode` (replaces the v1.24-v1.27 store_mode-branched
        version of this test, which required a cross-sell bundle for
        multi_product_niche — that shape was explicitly retired)."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert re.search(r"buy\s*2", text, re.I) and re.search(r"buy\s*3", text, re.I), (
            "no same-SKU quantity-tier block found (expected Buy 1/Buy 2/Buy 3)"
        )
        assert "BEST VALUE" in text or "Best Value" in text.title()

    def test_gallery_slide_one_not_composite(self, page, base_url, handle):
        """7.D bug #12 — flags a likely multi-inset composite for a human
        to look at; cannot fully automate 'is this one clean subject.'"""
        _goto(page, base_url, handle)
        first_img = page.query_selector("[data-gallery] img, .gallery img")
        if not first_img:
            pytest.skip("no gallery image found via expected selector")
        # heuristic only: a composite sourced straight from CJ often keeps
        # the original supplier filename pattern; this is a smell test to
        # prompt a human look, not a substitute for one
        src = (first_img.get_attribute("src") or "").lower()
        if "cjdropshipping" in src or "cf.cjdropshipping" in src:
            pytest.fail("gallery slide 1 still points at an unhosted CJ CDN URL — "
                        "re-host per 7.D bug #6, and visually confirm it isn't a composite")

    def test_variant_pickers_are_native_select(self, page, base_url, handle):
        """Section 5 item 3, v1.30 — Color/Size must be real <select>
        elements (confirmed on littlesnugg's live DOM: 12 real selects),
        not a styled div/button-group. Skips honestly if this product has
        no variant pickers at all rather than failing a false positive."""
        _goto(page, base_url, handle)
        selects = page.query_selector_all("select")
        variant_selects = [
            s for s in selects
            if re.search(r"color|size|colour", (s.get_attribute("name") or "")
                         + (s.get_attribute("aria-label") or ""), re.I)
        ]
        any_variant_ui = page.query_selector(
            "[data-variant-picker], [class*='variant'], [class*='color'], [class*='size']"
        )
        if not any_variant_ui:
            pytest.skip("no variant picker UI found on this product at all")
        assert variant_selects, (
            "variant picker UI is present but no matching <select name=color|size> "
            "was found — likely a styled div/button-group standing in for a real "
            "dropdown (v1.30)"
        )

    def test_real_support_email_not_placeholder(self, page, base_url, handle):
        """7.E, v1.30 — alphaforbaby.com's real support inbox is on file
        (support@alphaforbaby.com); the old support@[storedomain]-style
        placeholder must not still be rendered anywhere on the page."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "support@[storedomain]" not in text and "[storedomain]" not in text, (
            "a support-email placeholder is still rendered — replace with the "
            "real inbox (7.E)"
        )
        if "alphaforbaby" in base_url:
            assert "support@alphaforbaby.com" in page.content(), (
                "expected the real support@alphaforbaby.com address (mailto link "
                "or visible text) somewhere in the page, e.g. the Nora widget"
            )


class TestHomepageCompliance:
    """Section 5B, v1.43 — the homepage was rebuilt: image slider removed,
    replaced by a real all-active-products grid; trust-bar/category/
    testimonial sections deleted entirely, not hidden. Not parametrized by
    product handle — these hit `/` once."""

    def test_no_deleted_section_text(self, page, base_url):
        page.goto(base_url + "/")
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        for phrase in ["Shop by category", "Baby Boys", "Baby Girls"]:
            assert phrase not in text, (
                f"deleted homepage section text still present: {phrase!r} "
                f"(Section 5B, v1.43)"
            )

    def test_no_hero_slider_dots(self, page, base_url):
        """The hero image slider (dot pagination) must be gone — the
        product grid takes its place instead (Section 5B, v1.43)."""
        page.goto(base_url + "/")
        page.wait_for_timeout(1500)
        hero = page.query_selector("[class*='hero'], section:first-of-type")
        assert hero, "could not locate a hero section at all on the homepage"
        dots = hero.query_selector_all(
            "[class*='dot'], [class*='pagination'], [role='tablist']"
        )
        assert not dots, (
            "hero still has slider/dot pagination controls — the image "
            "slider was supposed to be removed (Section 5B, v1.43)"
        )

    def test_product_grid_shows_multiple_real_products(self, page, base_url):
        """The homepage should show most/all active products as real
        cards linking to their own PDP — not the old 3-item raw-CJ-image
        'Shop All' grid (Section 5B, v1.43)."""
        page.goto(base_url + "/")
        page.wait_for_timeout(1500)
        product_links = page.query_selector_all("a[href*='/products/']")
        hrefs = {a.get_attribute("href") for a in product_links}
        assert len(hrefs) >= 4, (
            f"expected the homepage grid to show most/all active store "
            f"products, found only {len(hrefs)} distinct product links "
            f"(Section 5B, v1.43)"
        )

    def test_no_testimonial_grid(self, page, base_url):
        """The 6-card testimonial grid must be deleted, not just moved
        below the new product grid (Section 5B, v1.43)."""
        page.goto(base_url + "/")
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        assert "Verified buyer" not in text, (
            "testimonial grid text still present on the homepage — it was "
            "supposed to be deleted entirely (Section 5B, v1.43)"
        )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestV144ProductPageFixes:
    """v1.44 — a dense round of real fixes checked directly against the
    live hip-carrier page. Each test targets one 7.D bug (#19-#25)."""

    def test_no_subheader_trust_row(self, page, base_url, handle):
        """7.D bug #19 — the header-area trust row was already asked to
        be removed in v1.31 (Section 5 item 2) and is still rendering."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "SECURE CHECKOUT" not in text.upper() or text.upper().count("SECURE CHECKOUT") <= 1, (
            "the sub-header trust row ('FREE SHIPPING · 30-DAY RETURNS · "
            "SECURE CHECKOUT') appears to still be rendering as its own "
            "strip above the gallery (7.D bug #19)"
        )

    def test_urgency_slot_not_trust_badges(self, page, base_url, handle):
        """7.D bug #20 — the urgency-banner slot must carry a real
        urgency line, not trust-badge copy standing in for it."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "RATED 5.0 BY VERIFIED BUYERS" not in text.upper(), (
            "the urgency-banner slot (between gallery and avatar strip) "
            "still shows trust-badge text instead of a real urgency line "
            "(7.D bug #20)"
        )

    def test_bundle_has_no_buy_3(self, page, base_url, handle):
        """7.D bug #22 — Itzik dropped the third tier; only Buy 1/Buy 2
        should remain."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert "Buy 3" not in text, (
            "a 'Buy 3' tier still renders in the bundle — only Buy 1 and "
            "Buy 2 should exist now (7.D bug #22)"
        )

    def test_no_redundant_trust_text_under_cta(self, page, base_url, handle):
        """7.D bug #25 — the text-only trust block under Add to Cart
        duplicates claims already made twice above the fold."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        for phrase in ["30-day easy returns", "Guaranteed Safe & Secure Checkout"]:
            assert phrase not in text, (
                f"redundant trust-text line still present under Add to "
                f"Cart: {phrase!r} (7.D bug #25) — the real payment-icon "
                f"row above it should stay, only this text line goes"
            )

    def test_mini_carousel_cards_borderless(self, page, base_url, handle):
        """7.D bug #23 — mini review carousel cards must render with no
        border."""
        _goto(page, base_url, handle)
        cards = page.query_selector_all(
            "[class*='mini-review'], [class*='review-carousel'], [class*='MiniReview']"
        )
        if not cards:
            pytest.skip("could not locate the mini review carousel by a class hook")
        for card in cards:
            border = card.evaluate(
                "el => getComputedStyle(el).borderWidth"
            )
            assert border in ("0px", "", None), (
                f"mini review carousel card has a computed border ({border}) "
                f"— cards should be borderless (7.D bug #23)"
            )

    def test_video_immediately_after_mini_carousel(self, page, base_url, handle):
        """7.D bug #24 — the product-demo video should sit directly after
        the mini review carousel, before the benefit bullets section."""
        _goto(page, base_url, handle)
        carousel = page.query_selector(
            "[class*='mini-review'], [class*='review-carousel'], [class*='MiniReview']"
        )
        video = page.query_selector("video")
        if not carousel or not video:
            pytest.skip("could not locate both the mini carousel and a video element")
        # crude but effective: compare DOM order via bounding box Y position,
        # and check nothing with obviously different section text sits between
        carousel_y = carousel.bounding_box()["y"]
        video_y = video.bounding_box()["y"]
        assert video_y > carousel_y, "video should render below the mini carousel"
        gap_text = page.evaluate(
            """() => {
                const all = Array.from(document.querySelectorAll('h2, h3'));
                return all.map(h => h.innerText);
            }"""
        )
        assert not any("Why parents choose it" in h for h in gap_text[:1]), (
            "a benefit-bullets heading appears to precede the video — the "
            "video should come immediately after the mini carousel, before "
            "benefit bullets (7.D bug #24)"
        )


class TestContactPage:
    """v1.44 — the Contact page's business-details text names Israel
    directly; Itzik asked for that phrase removed."""

    def test_no_registered_in_israel(self, page, base_url):
        page.goto(base_url + "/pages/contact")
        page.wait_for_timeout(1000)
        text = page.inner_text("body")
        assert "registered in Israel" not in text, (
            "the Contact page's Business details section still says "
            "'registered in Israel' — Itzik asked for this phrase removed "
            "(v1.44)"
        )


TRENDING_HANDLES = [
    "ergonomic-baby-hip-carrier",
    "foldable-portable-baby-crib",
    "glow-whale-bath-buddy",
    "automatic-domino-train-set",
    "montessori-shape-sorting-egg",
    "toddler-sensory-learning-board",
    "baby-beach-sun-shelter",
    "foldable-baby-bed-canopy-set",
    "cozy-portable-baby-nest",
]


class TestV149Regressions:
    """v1.49 — every test here maps to a 7.D bug found by measuring the
    real rendered page, not by reading component source. Run these at
    375px width (the mobile viewport Itzik actually reviews on)."""

    @pytest.mark.parametrize("trending_handle", TRENDING_HANDLES)
    def test_every_trending_product_resolves(self, page, base_url, trending_handle):
        """7.D bug #30 — 6 of the 9 trending products 404 on the
        storefront, so nothing else about them can be verified."""
        resp = page.goto(f"{base_url}/products/{trending_handle}")
        assert resp is not None and resp.status == 200, (
            f"/products/{trending_handle} did not return 200 — 6 of the 9 "
            f"trending products were 404ing as of v1.49 (7.D bug #30); a "
            f"build pass cannot be verified on a page that has no URL"
        )

    def test_buy_box_renders(self, page, base_url, handle):
        """7.D bug #29 — the crib and Glow Whale pages rendered with no
        price, no variant picker and no Add to Cart at all."""
        _goto(page, base_url, handle)
        body = page.inner_text("body")
        assert page.locator("select").count() > 0, (
            "no variant <select> rendered on this product page — the buy "
            "box appears to be product-gated in code (7.D bug #29)"
        )
        assert "$" in body, (
            "no price renders anywhere on this product page, even though "
            "the page's own JSON-LD carries a real price (7.D bug #29)"
        )
        cta = page.locator("text=/add\\s+\\d*\\s*to cart/i")
        assert cta.count() > 0, (
            "no 'ADD [N] TO CART' control renders — a product page a "
            "shopper cannot buy from is worse than an unbuilt one "
            "(7.D bug #29, Section 5C row 12)"
        )

    def test_star_layers_aligned(self, page, base_url, handle):
        """7.D bug #27 — the fractional-fill overlay row and the base row
        must share identical star geometry, or the row reads as doubled
        overlapping stars (Itzik: 'the stars look one on top of the
        other')."""
        _goto(page, base_url, handle)
        boxes = page.evaluate(
            "() => Array.from(document.querySelectorAll('svg.lucide-star'))"
            ".map(s => { const r = s.getBoundingClientRect();"
            " return {x: r.left, y: r.top, w: r.width}; })"
        )
        assert boxes, "no star glyphs found on the page"
        first_row_y = boxes[0]["y"]
        row = [b for b in boxes if abs(b["y"] - first_row_y) < 3]
        widths = {round(b["w"], 1) for b in row}
        assert len(widths) == 1, (
            f"the star row mixes glyph widths {sorted(widths)} — the base "
            f"row and the gold fill overlay are sized independently, which "
            f"makes them drift apart across the row (7.D bug #27)"
        )
        xs = sorted(round(b["x"], 1) for b in row)
        pitches = {round(b - a, 1) for a, b in zip(xs, xs[1:]) if b - a > 0.5}
        assert len(pitches) <= 1, (
            f"the star row mixes horizontal pitches {sorted(pitches)} — the "
            f"two layers step by different amounts, so every star after the "
            f"first is visibly offset from the one it fills (7.D bug #27)"
        )

    def test_webfont_actually_loads(self, page, base_url, handle):
        """7.D bug #28 — declaring a font-family and linking Google Fonts
        does nothing while the CSP blocks the stylesheet and the font
        files; the page silently falls back to system-ui."""
        _goto(page, base_url, handle)
        loaded = page.evaluate("() => document.fonts.size")
        assert loaded and loaded > 0, (
            "document.fonts is empty — no webfont actually loaded, so the "
            "font-family declaration falls through to system-ui and the "
            "font looks unchanged (7.D bug #28: CSP style-src must allow "
            "fonts.googleapis.com and a real font-src must allow "
            "fonts.gstatic.com, or self-host the woff2 files)"
        )
        widths = page.evaluate(
            "() => { const mk = fam => { const s = document.createElement('span');"
            " s.textContent = 'Everything baby needs 12345';"
            " s.style.cssText = 'position:absolute;visibility:hidden;"
            "white-space:nowrap;font-size:40px;font-family:' + fam;"
            " document.body.appendChild(s);"
            " const w = s.getBoundingClientRect().width; s.remove(); return w; };"
            " return {intended: mk(getComputedStyle(document.body).fontFamily),"
            " system: mk('system-ui')}; }"
        )
        assert abs(widths["intended"] - widths["system"]) > 1, (
            "text set in the page's own font stack renders at exactly the "
            "same width as system-ui — the intended font is not resolving "
            "for real visitors (7.D bug #28)"
        )


class TestPdpParityGate:
    """Section 5C (v1.49) — Itzik's standing instruction is that every
    product page looks like the built carrier page. This compares a
    target page against the carrier page component by component instead
    of trusting a build report's prose."""

    REFERENCE_HANDLE = "ergonomic-baby-hip-carrier"
    REQUIRED_MARKERS = [
        "SELLING QUICK",          # row 4  — urgency ticker
        "verified buyers",        # row 5  — avatar strip headline
        "Reviews)",               # row 7  — star row + real review count
        "Buy more, save more",    # row 8  — bundle heading
        "MOST POPULAR",           # row 9  — Buy 2 badge
        "CHOOSE EACH ONE",        # row 10 — per-unit variant selects
    ]

    def test_target_page_has_reference_components(self, page, base_url, handle):
        """Every marker that exists on the carrier page must also exist on
        the page under test."""
        _goto(page, base_url, self.REFERENCE_HANDLE)
        reference = page.inner_text("body")
        present_on_reference = [m for m in self.REQUIRED_MARKERS if m in reference]
        _goto(page, base_url, handle)
        target = page.inner_text("body")
        missing = [m for m in present_on_reference if m not in target]
        assert not missing, (
            f"/products/{handle} is missing components that the reference "
            f"carrier page renders: {missing} — report the full Section 5C "
            f"parity table row by row before calling this page done"
        )

    def test_not_a_raw_description_dump(self, page, base_url, handle):
        """Section 5C row 16 — the non-carrier pages substituted a raw
        'Full description' dump for the carrier's structured benefit
        sections."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        if "Full description" in text:
            assert any(
                marker in text
                for marker in ("Why parents choose", "Frequently asked", "change your mind")
            ), (
                "this page shows a raw 'Full description' dump with none of "
                "the carrier page's structured sections (benefits, FAQ, "
                "guarantee) — Section 5C rows 16-19"
            )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestReviewsUnderVideo:
    """v1.53 — Itzik's explicit order: the full "Ratings & Reviews" block sits
    directly under the product video, before the benefit sections. It is not
    the last section anymore. Checked by vertical position on the rendered
    page, not by reading JSX order."""

    def _top(self, page, selector):
        return page.evaluate(
            "sel => { const el = document.querySelector(sel);"
            " return el ? el.getBoundingClientRect().top + window.scrollY : null; }",
            selector,
        )

    def _top_of_text(self, page, text):
        return page.evaluate(
            "t => { const el = Array.from(document.querySelectorAll('h2'))"
            ".find(h => h.textContent.trim().startsWith(t));"
            " return el ? el.getBoundingClientRect().top + window.scrollY : null; }",
            text,
        )

    def test_reviews_block_directly_after_video(self, page, base_url, handle):
        _goto(page, base_url, handle)
        video = self._top(page, "video")
        reviews = self._top(page, "#reviews")
        assert reviews is not None, (
            f"/products/{handle} has no #reviews block — keep id='reviews' on "
            f"the moved block so the star row's anchor still works (v1.53)"
        )
        if video is None:
            pytest.skip(
                f"{handle} has no real video (reported per product, 7.B) — "
                f"order relative to the video is not applicable"
            )
        assert reviews > video, (
            f"/products/{handle}: Ratings & Reviews renders ABOVE the video — "
            f"it must sit directly under it (v1.53)"
        )
        benefits = self._top_of_text(page, "Why parents choose")
        if benefits is not None:
            assert reviews < benefits, (
                f"/products/{handle}: Ratings & Reviews still renders below "
                f"'Why parents choose it' — v1.53 moves it up to sit between "
                f"the video and the benefit sections"
            )

    def test_reviews_not_last_section(self, page, base_url, handle):
        _goto(page, base_url, handle)
        reviews = self._top(page, "#reviews")
        guarantee = self._top_of_text(page, "30 days")
        if reviews is None or guarantee is None:
            pytest.fail(
                f"/products/{handle} is missing #reviews or the guarantee "
                f"block, so the order can't be checked (Section 5C)"
            )
        assert reviews < guarantee, (
            f"/products/{handle}: reviews still render after the guarantee — "
            f"the old 'reviews last' order is superseded by v1.53"
        )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestBundleRequired:
    """v1.52 — the tier bundle is required on EVERY product page (Section 5
    item 3, unbranched since v1.29). It went missing on 8 of 9 products without
    a single red test, because the existing tier tests skip when the block is
    absent and conftest still defaults to the retired `multi_product_niche`
    shape. A missing required element fails here; it does not skip.

    Replace the repo's conftest.py fixture with:

        @pytest.fixture(scope="session")
        def store_mode():
            # v1.29 retired the store_mode branch for the bundle: every product
            # uses the same-SKU quantity-tier block. Kept only for callers that
            # still read it.
            return "single_hero_product"
    """

    def test_tier_bundle_block_exists(self, page, base_url, handle):
        _goto(page, base_url, handle)
        block = page.locator("[data-quantity-tiers]")
        assert block.count() > 0, (
            f"/products/{handle} renders no quantity-tier block at all — "
            f"Section 5 item 3 requires the same-SKU Buy 1 / Buy 2 tiers on "
            f"every product. Author `quantityTiers` + `tierBenefits` in that "
            f"product's custom.pdp_content (Section 5D.3). This must NOT be "
            f"skipped when absent (7.D #36)"
        )

    def test_tier_bundle_is_not_the_fallback_box(self, page, base_url, handle):
        """The v1.49 fallback keeps a product buyable, but it is a fallback —
        shipping it as the final state on every product is the 7.D #34 bug."""
        _goto(page, base_url, handle)
        simple_only = (
            page.locator("[data-simple-buybox]").count() > 0
            and "Buy more, save more" not in page.inner_text("body")
        )
        assert not simple_only, (
            f"/products/{handle} is still on the simple single-item buy box — "
            f"no 'Buy more, save more' heading, no tier cards. Either author "
            f"`quantityTiers` for it, or state in the build report that a "
            f"second unit makes no sense for this product and that "
            f"`quantityTiers: []` is deliberate (Section 5D.4 step 4)"
        )

    def test_second_tier_is_badged_and_preselected(self, page, base_url, handle):
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        if "Buy more, save more" not in text:
            pytest.fail(
                f"/products/{handle} has no bundle heading — see "
                f"test_tier_bundle_block_exists"
            )
        assert "MOST POPULAR" in text.upper(), (
            f"/products/{handle}'s Buy 2 tier carries no MOST POPULAR badge "
            f"(Section 5C row 9)"
        )
        assert re.search(r"ADD\s+\d+\s+TO CART", text, re.I), (
            f"/products/{handle}'s CTA doesn't name the tier quantity "
            f"('ADD 2 TO CART') — the CTA must be bound to the selected tier "
            f"(Section 5C row 12)"
        )

    def test_tier_price_math_is_real(self, page, base_url, handle):
        """Every charged tier total ends in .90 and the struck-through anchor is
        an honest qty × unit price (Section 4, v1.32)."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        if "Buy more, save more" not in text:
            pytest.fail(f"/products/{handle} has no bundle to price-check")
        totals = re.findall(r"\$\s?([\d,]+\.\d\d)", text)
        assert totals, f"/products/{handle} shows no prices in the bundle"
        charged = [t for t in totals if t.endswith(".90")]
        assert charged, (
            f"/products/{handle}: no tier total ends in .90 — every price a "
            f"customer actually pays ends in .90 (Section 4, v1.31); the "
            f"struck-through anchor may end in anything honest (v1.32)"
        )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestV151Blockers:
    """v1.51 — the audit that found six of nine products unbuyable. These four
    tests are the ones that would have caught it a round earlier.

    They deliberately check Shopify's OWN view of availability and price
    (`/products/<handle>.js` on the Liquid storefront) as well as the rendered
    Hydrogen page, because the storefront was rendering "sold out" perfectly
    correctly — the data behind it was wrong (7.D #31).
    """

    def _shopify_product_json(self, handle, shop_domain):
        url = f"https://{shop_domain}/products/{handle}.js"
        req = urllib.request.Request(url, headers={"User-Agent": "compliance-suite"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    def test_every_variant_is_available_for_sale(self, handle, shop_domain):
        """7.D #31 — 0-of-N available variants renders a page nobody can buy
        from, and it looks finished while doing it."""
        data = self._shopify_product_json(handle, shop_domain)
        variants = data.get("variants", [])
        assert variants, f"{handle} has no variants at all in Shopify"
        unavailable = [v.get("title") for v in variants if not v.get("available")]
        assert not unavailable, (
            f"{handle}: {len(unavailable)} of {len(variants)} variants are NOT "
            f"available for sale, so the page renders 'sold out' with no Add "
            f"to Cart: {unavailable[:6]}. Fix the inventory setup in Shopify "
            f"(untracked, or stocked at the fulfilment location with "
            f"continue-selling on) — this is not a storefront bug (7.D #31)"
        )

    def test_one_retail_price_across_variants(self, handle, shop_domain):
        """7.D #32 — the carrier and crib each carry ONE retail price across
        every variant; the imported products kept CJ's per-variant cost
        spread, which is how a $4.90 price on a ~$10.54 landed cost shipped."""
        data = self._shopify_product_json(handle, shop_domain)
        prices = {v.get("price") for v in data.get("variants", [])}
        assert len(prices) == 1, (
            f"{handle} has {len(prices)} different variant prices "
            f"({sorted(p / 100 for p in prices if p)}) — a retail page should "
            f"carry one approved price per product (Section 4), not the "
            f"supplier's per-variant cost spread (7.D #32). If a genuine "
            f"price difference per variant is intended, state it explicitly"
        )

    def test_price_ends_in_90(self, handle, shop_domain):
        """Section 4's pricing convention, mechanically."""
        data = self._shopify_product_json(handle, shop_domain)
        bad = [
            v.get("price")
            for v in data.get("variants", [])
            if v.get("price") is not None and v["price"] % 100 != 90
        ]
        assert not bad, (
            f"{handle} has variant prices not ending in .90: "
            f"{sorted({p / 100 for p in bad})} — every price a customer "
            f"actually pays ends in .90 (Section 4, v1.31)"
        )

    def test_no_supplier_hosted_images(self, page, base_url, handle):
        """7.D #35/#6 — review photos are hotlinked from the supplier's CDN and
        none of them load; they also leak the supplier into the DOM."""
        _goto(page, base_url, handle)
        page.wait_for_timeout(1500)
        supplier_imgs = page.evaluate(
            "() => Array.from(document.images)"
            ".filter(i => /aliyuncs|cjdropshipping/i.test(i.src))"
            ".map(i => ({src: i.src, w: i.naturalWidth}))"
        )
        assert not supplier_imgs, (
            f"{handle} serves {len(supplier_imgs)} image(s) from the "
            f"supplier's CDN (e.g. {supplier_imgs[0]['src'][:70] if supplier_imgs else ''}), "
            f"of which {sum(1 for i in supplier_imgs if i['w'] == 0)} fail to "
            f"load — re-host review photos on Shopify's CDN and drop the ones "
            f"that can't be re-hosted (7.D #35)"
        )

    def test_every_rendered_review_photo_loads(self, page, base_url, handle):
        _goto(page, base_url, handle)
        page.wait_for_timeout(1500)
        broken = page.evaluate(
            "() => Array.from(document.images)"
            ".filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src'))"
            ".map(i => i.getAttribute('src'))"
        )
        assert not broken, (
            f"{handle} renders {len(broken)} broken image(s): {broken[:3]} "
            f"(7.D #35)"
        )


class TestCatalogCoverage:
    """v1.50 — the suite's own coverage is now a tested property.

    Root cause this exists for: PRODUCT_HANDLES used to be a hand-maintained
    list containing only the carrier, so every run was green while other live
    pages shipped with no buy box. Coverage gaps must fail, not pass quietly.
    """

    def test_dev_server_is_up(self, base_url):
        assert _LIVE, (
            f"no product handles could be read from {base_url}/collections/all "
            f"— the suite would otherwise silently fall back to testing only "
            f"the reference product and report green (v1.50). Start the dev "
            f"server, or point --base-url at the real deployment"
        )

    def test_every_trending_product_is_in_the_live_catalog(self, base_url):
        """v2.1: the 9 shortlisted products are no longer all expected live —
        Level 01 rule 7 hides any product under 15 photo reviews. What must
        hold now: every product that IS live passes the review gate
        (TestReviewGate), and every shortlisted product that is NOT live is
        hidden deliberately (listed in REVIEW_GATE_HIDDEN), not by accident.
        7.D #30's accidental 404s would show up here as unlisted absences."""
        missing = [
            h for h in TRENDING_SHORTLIST
            if h not in _LIVE and h not in REVIEW_GATE_HIDDEN
        ]
        assert not missing, (
            f"these shortlisted products are not served by the storefront "
            f"and are not on the deliberate review-gate hidden list: "
            f"{missing} — either they're hidden by accident (check the "
            f"Hydrogen channel publication, 7.D #30) or they failed the "
            f"review gate and REVIEW_GATE_HIDDEN wasn't updated (Level 02, 2.G)"
        )

    def test_catalog_has_no_unexpected_products(self):
        """The inverse guard: a legacy or test product creeping back into the
        live catalog should be noticed here, not by a customer."""
        unexpected = [h for h in _LIVE if h not in TRENDING_SHORTLIST]
        assert not unexpected, (
            f"the storefront serves products that are not on the confirmed "
            f"trending shortlist: {unexpected} — either add them to "
            f"TRENDING_SHORTLIST deliberately, or archive them (Section 2.F)"
        )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestPdpContentContract:
    """Section 5D (v1.50) — every persuasion section on a PDP is rendered from
    one key of that product's `custom.pdp_content` metafield. These tests check
    the RENDERED consequence of each key, so a product whose metafield was
    never authored fails loudly instead of shipping as a polite skeleton.

    Each assertion names the metafield key to write, because that — not a code
    change — is the fix.
    """

    def test_urgency_line_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        text = page.inner_text("body").upper()
        assert "LOW STOCK" in text or "SELLING QUICK" in text, (
            f"no urgency line on /products/{handle} — write "
            f"`urgencyLine` in that product's custom.pdp_content "
            f"(Section 5D.2/5D.3, v1.45's literal-wording decision)"
        )

    def test_buyer_avatar_strip_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert re.search(r"Join\s+\d+\s+verified buyers", text), (
            f"the 'Join [N] verified buyers' strip is missing on "
            f"/products/{handle} — it needs the real AG review count AND the "
            f"strip's own copy; two orphan avatar photos with no headline is "
            f"the broken state seen in v1.49 (Section 5C row 5)"
        )

    def test_benefits_section_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        assert "Why parents choose it" in page.inner_text("body"), (
            f"no benefit grid on /products/{handle} — write the `benefits` "
            f"array (3-5 items, each {{icon,title,text}}, icon one of "
            f"baby/repeat/shield/umbrella/zap) in custom.pdp_content "
            f"(Section 5D.3)"
        )

    def test_faq_section_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        assert "Frequently asked questions" in page.inner_text("body"), (
            f"no FAQ on /products/{handle} — write the `faq` array of "
            f"{{question,answer}} in custom.pdp_content (Section 5D.3); "
            f"answers must come from that product's real specs/reviews"
        )

    def test_guarantee_section_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        assert "change your mind" in page.inner_text("body").lower(), (
            f"no guarantee block on /products/{handle} — write "
            f"`guarantee.heading` AND `guarantee.text` in custom.pdp_content; "
            f"the component renders nothing when `text` is absent "
            f"(Section 5D.3)"
        )

    def test_comparison_section_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        html = page.content()
        assert re.search(r"Compare|Without it|With it", html), (
            f"no comparison block on /products/{handle} — `comparison` needs "
            f"BOTH `with` and `without`, each with a title and an items "
            f"array; half a comparison renders nothing (Section 5D.3)"
        )

    def test_how_to_use_section_rendered(self, page, base_url, handle):
        _goto(page, base_url, handle)
        assert re.search(
            r"How to use|Three ways", page.inner_text("body"), re.I
        ), (
            f"no how-to-use steps on /products/{handle} — write "
            f"`howToUse.steps` (each {{n,title,text,imageIndex}}) in "
            f"custom.pdp_content, with imageIndex counted against THIS "
            f"product's own gallery order (Section 5D.3)"
        )

    def test_quantity_tiers_or_deliberate_single_box(self, page, base_url, handle):
        """`quantityTiers: []` is a legitimate, deliberate choice for a product
        nobody needs two of (5D.4 step 4) — but then the simple buy box must be
        the thing that renders, and it must be complete."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        has_tiers = "Buy more, save more" in text
        if not has_tiers:
            assert page.locator("[data-simple-buybox]").count() > 0, (
                f"/products/{handle} has neither the bundle tier block nor "
                f"the simple buy-box fallback — this is the 7.D #29 state "
                f"(a page a shopper cannot buy from). Either write "
                f"`quantityTiers` in custom.pdp_content or make sure the "
                f"fallback box renders"
            )
            assert re.search(r"\$\s?\d", text), (
                f"/products/{handle} renders no price at all (7.D #29)"
            )
        else:
            assert "MOST POPULAR" in text.upper(), (
                f"/products/{handle} has tiers but no MOST POPULAR badge on "
                f"the Buy 2 tier — write it via `quantityTiers`/`tierBenefits` "
                f"(Section 5D.3, Section 5C row 9)"
            )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestNoSkeletonPages:
    """v1.50 — a cheap structural smell test for 'looks finished, isn't'."""

    MIN_SECTION_RATIO = 0.6

    def _section_headings(self, page):
        return [
            h.strip()
            for h in page.locator("h2").all_inner_texts()
            if h.strip()
        ]

    def test_section_count_close_to_reference(self, page, base_url, handle):
        _goto(page, base_url, REFERENCE_HANDLE)
        reference = self._section_headings(page)
        _goto(page, base_url, handle)
        target = self._section_headings(page)
        assert len(target) >= len(reference) * self.MIN_SECTION_RATIO, (
            f"/products/{handle} renders {len(target)} h2 sections vs "
            f"{len(reference)} on the reference carrier page — it is a "
            f"skeleton of the reference layout. Missing: "
            f"{[h for h in reference if h not in target]} "
            f"(Section 5C parity gate, Section 5D content contract)"
        )

    def test_page_weight_close_to_reference(self, page, base_url, handle):
        """Measured at v1.49: carrier ~225kb, crib ~121kb, Glow Whale ~44kb —
        page weight tracked 'how much of the page actually exists' closely
        enough to be worth asserting on."""
        _goto(page, base_url, REFERENCE_HANDLE)
        reference_kb = len(page.content()) / 1024
        _goto(page, base_url, handle)
        target_kb = len(page.content()) / 1024
        assert target_kb >= reference_kb * 0.5, (
            f"/products/{handle} renders at {target_kb:.0f}kb vs the "
            f"reference page's {reference_kb:.0f}kb — under half the "
            f"reference weight means most sections aren't there (Section 5C)"
        )


class TestHomepageDensity:
    """v1.49/v1.50 — Itzik has reported homepage spacing four rounds running.
    Each fix was reported done and each time the number moved somewhere else,
    so the targets are now assertions with real pixel budgets at 375px width.
    """

    MOBILE = {"width": 375, "height": 812}

    def _goto_home(self, page, base_url):
        page.set_viewport_size(self.MOBILE)
        page.goto(base_url + "/")
        page.wait_for_timeout(1200)

    def test_footer_top_gap_within_budget(self, page, base_url):
        """v1.47's target, met at v1.49 (20px padding + 12px margin = 32px).
        This test exists to keep it met, not to keep shrinking it."""
        self._goto_home(page, base_url)
        gap = page.evaluate(
            "() => { const f = document.querySelector('footer');"
            " if (!f) return null; const c = getComputedStyle(f);"
            " return parseFloat(c.paddingTop) + parseFloat(c.marginTop); }"
        )
        assert gap is not None, "no <footer> found on the homepage"
        assert gap <= 36, (
            f"footer's combined top padding+margin is {gap}px — budget is "
            f"24-32px (Section 5B, v1.47)"
        )

    def test_hero_block_within_budget(self, page, base_url):
        """v1.49: the hero measured 555px on an 812px viewport, pushing the
        product grid entirely below the fold."""
        self._goto_home(page, base_url)
        height = page.evaluate(
            "() => { const el = document.querySelector('.tob-eh')"
            " || document.querySelector('main section');"
            " return el ? Math.round(el.getBoundingClientRect().height) : null; }"
        )
        assert height is not None, "could not find the hero section"
        assert height <= 420, (
            f"hero block is {height}px tall at 375px width — budget is ~400px "
            f"so the product grid starts above the fold (Section 5B, v1.49)"
        )

    def test_footer_block_within_budget(self, page, base_url):
        """v1.49: the footer block measured 760px on mobile — bigger than the
        product grid it follows."""
        self._goto_home(page, base_url)
        height = page.evaluate(
            "() => { const f = document.querySelector('footer');"
            " return f ? Math.round(f.getBoundingClientRect().height) : null; }"
        )
        assert height is not None, "no <footer> found on the homepage"
        assert height <= 460, (
            f"footer block is {height}px tall at 375px width — budget is "
            f"~420px; collapse the four stacked link columns into two and cut "
            f"the payment-row/bottom-bar margins (Section 5B, v1.49)"
        )

    def test_all_catalog_products_appear_in_grid(self, page, base_url):
        """7.D #26/#30 — the grid must show the real catalog, and the real
        catalog must be the full shortlist."""
        self._goto_home(page, base_url)
        hrefs = page.eval_on_selector_all(
            "a[href*='/products/']", "els => els.map(e => e.getAttribute('href'))"
        )
        shown = {h.split("/products/")[-1].split("?")[0] for h in hrefs if h}
        missing = [h for h in _LIVE if h not in shown]
        assert not missing, (
            f"the homepage grid omits products the storefront serves: "
            f"{missing} — the grid must query the live catalog (7.D #26)"
        )

@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestReviewGate:
    """v2.1 — Level 01 rule 7 / Level 02 Section 2.G: a product is displayed
    only with >= 15 real reviews that each carry a real photo that loads.
    Every live product is checked; hidden products must be truly hidden."""

    def test_live_product_has_15_photo_reviews(self, page, base_url, handle):
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        m = re.search(r"(\d+)\s*reviews?\s*·\s*(\d+)\s*with photos", text)
        assert m, (
            f"/products/{handle} shows no 'N reviews · M with photos' summary "
            f"— a live product must have imported reviews (Level 02, 2.G)"
        )
        with_photos = int(m.group(2))
        assert with_photos >= MIN_PHOTO_REVIEWS, (
            f"/products/{handle} is live with only {with_photos} photo "
            f"reviews — the rule is >= {MIN_PHOTO_REVIEWS}. Hide it (Draft / "
            f"unpublish, never delete) and add it to REVIEW_GATE_HIDDEN "
            f"(Level 01 rule 7)"
        )

    def test_review_photos_actually_load(self, page, base_url, handle):
        """A photo that doesn't load doesn't count toward the gate."""
        _goto(page, base_url, handle)
        page.locator("#reviews").scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        stats = page.evaluate(
            "() => { const imgs = Array.from(document.querySelectorAll('#reviews img'));"
            " return {total: imgs.length,"
            " broken: imgs.filter(i => i.complete && i.naturalWidth === 0).length,"
            " offCdn: imgs.filter(i => !/cdn\\.shopify\\.com/.test(i.src)).length}; }"
        )
        assert stats["broken"] == 0 and stats["offCdn"] == 0, (
            f"/products/{handle}: {stats['broken']} broken and "
            f"{stats['offCdn']} non-Shopify-CDN review photos — neither "
            f"counts toward the 15-photo gate (7.D #35, Level 02 2.G)"
        )


class TestHiddenProductsStayHidden:
    """Products under the gate must not leak anywhere a shopper can reach."""

    @pytest.mark.parametrize("hidden", REVIEW_GATE_HIDDEN)
    def test_hidden_product_url_not_served(self, page, base_url, hidden):
        resp = page.goto(f"{base_url}/products/{hidden}")
        assert resp is not None and resp.status == 404, (
            f"/products/{hidden} still returns {resp.status if resp else None} "
            f"— it's under the 15-photo-review gate and must be hidden "
            f"(Draft / unpublished), not just left off the homepage"
        )

    def test_hidden_products_absent_from_grid_and_collections(self, page, base_url):
        for path in ("/", "/collections/all"):
            page.goto(base_url + path)
            page.wait_for_timeout(1000)
            html = page.content()
            leaked = [h for h in REVIEW_GATE_HIDDEN if f"/products/{h}" in html]
            assert not leaked, (
                f"{path} still links to hidden products {leaked} "
                f"(Level 02, 2.G)"
            )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestHeroImage:
    """v2.1 — Level 01 rule 8 / Level 09 Section 7.A.1: the hero image is
    chosen by markitdown + OCR, is not pixelated, carries no Chinese text,
    and shows someone using the product when such a photo exists. The
    selection is recorded per product; this checks the record AND the page."""

    CJK = re.compile(
        "[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002a6df]"
    )

    def _record(self, handle):
        path = os.path.join(HERO_SELECTION_DIR, f"{handle}.json")
        assert os.path.exists(path), (
            f"no hero-selection record for {handle} at {path} — run the "
            f"Level 09 7.A.1 procedure (markitdown + OCR) and save it"
        )
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_record_meets_the_three_rules(self, handle):
        chosen = self._record(handle)["chosen"]
        assert chosen["short_side"] >= 1000 and chosen["laplacian_var"] >= 100, (
            f"{handle}'s hero is pixelated or soft: short side "
            f"{chosen['short_side']}px, Laplacian {chosen['laplacian_var']} "
            f"(need >= 1000px and >= 100)"
        )
        assert chosen["cjk_chars"] == 0, (
            f"{handle}'s hero contains {chosen['cjk_chars']} Chinese "
            f"character(s) — hard fail (Level 09 7.A.1)"
        )

    def test_hero_and_gallery_come_only_from_cj(self, handle):
        """v2.2 — product images come only from the product's own CJ
        listing. v2.1 let review photos compete and all three heroes ended
        up being customer review photos; that is now a hard fail."""
        rec = self._record(handle)
        entries = [rec["chosen"]] + rec.get("uploaded", [])
        not_cj = [
            e.get("url", "")[:80] for e in entries
            if e.get("source") != "cj" or "/review-" in e.get("url", "")
        ]
        assert not not_cj, (
            f"{handle} uses non-CJ images as product images: {not_cj} — "
            f"review photos stay in the reviews section only (Level 01 "
            f"rule 8, Level 09 7.A.1 v2.2)"
        )

    def test_every_uploaded_image_passed_stage_1(self, handle):
        rec = self._record(handle)
        bad = [
            e.get("url", "")[:70] for e in [rec["chosen"]] + rec.get("uploaded", [])
            if e.get("cjk_chars", 1) != 0
            or e.get("short_side", 0) < 1000
            or e.get("laplacian_var", 0) < 100
        ]
        assert not bad, (
            f"{handle} uploaded images that fail the pixelation or Chinese-"
            f"text check: {bad} — they must not be uploaded at all "
            f"(Level 09 7.A.1 stage 1)"
        )

    def test_person_preferred_when_available(self, handle):
        rec = self._record(handle)
        if not rec["chosen"].get("person_using_product"):
            person_shots = [
                e for e in rec.get("uploaded", [])
                if e.get("person_using_product") and e.get("source") == "cj"
            ]
            assert not person_shots, (
                f"{handle}'s hero is a bare product shot, but an uploaded CJ "
                f"image shows someone using it: "
                f"{[e['url'][:60] for e in person_shots]} (7.A.1 stage 2)"
            )

    def test_no_review_photo_in_product_gallery(self, page, base_url, handle):
        _goto(page, base_url, handle)
        gallery_review_imgs = page.evaluate(
            "() => Array.from(document.images)"
            ".filter(i => /\\/review-/.test(i.src) && !i.closest('#reviews')"
            " && !i.closest('[data-avatar-strip]') && !i.closest('[data-mini-reviews]'))"
            ".map(i => i.src)"
        )
        assert not gallery_review_imgs, (
            f"/products/{handle} shows review photos outside the reviews "
            f"sections: {gallery_review_imgs[:3]} (Level 01 rule 8)"
        )

    def test_page_hero_is_the_recorded_choice(self, page, base_url, handle):
        chosen_url = self._record(handle)["chosen"]["url"].split("?")[0]
        _goto(page, base_url, handle)
        first = page.evaluate(
            "() => { const i = document.querySelector('img');"
            " return i ? {src: i.currentSrc.split('?')[0], w: i.naturalWidth} : null; }"
        )
        assert first and first["src"].rsplit("/", 1)[-1].split("_")[0] in chosen_url, (
            f"/products/{handle}'s first gallery image {first and first['src']} "
            f"is not the recorded hero {chosen_url} — reorder the product "
            f"media so the chosen image is position 1"
        )

@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestPricingRule:
    """v2.3 — Itzik's pricing decision: ~20% gross margin, never above the
    market median, Buy 2 also >= 20%, approved by Itzik before shipping."""

    FEE_PCT, FEE_FIXED, MIN_MARGIN = 0.029, 0.30, 0.20

    def _record(self, handle):
        path = os.path.join(
            os.path.dirname(HERO_SELECTION_DIR.rstrip("/")), "pricing", f"{handle}.json"
        )
        assert os.path.exists(path), (
            f"no pricing record for {handle} at {path} — run the Level 03 "
            f"pricing rule (landed cost, market check, 20% floor)"
        )
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _margin(self, price, landed):
        return (price - price * self.FEE_PCT - self.FEE_FIXED - landed) / price

    def test_price_approved_and_matches_shopify(self, handle, shop_domain):
        rec = self._record(handle)
        assert rec.get("approved_by_itzik") is True, (
            f"{handle}'s price hasn't been approved by Itzik yet"
        )
        data = TestV151Blockers()._shopify_product_json(handle, shop_domain)
        live = {v["price"] / 100 for v in data["variants"]}
        assert live == {rec["price"]}, (
            f"{handle}: Shopify price {sorted(live)} != approved {rec['price']}"
        )

    def test_margin_at_least_20_percent(self, handle):
        rec = self._record(handle)
        worst = max(v["landed"] for v in rec["variant_costs"])
        m1 = self._margin(rec["price"], worst)
        m2 = self._margin(rec["buy2_total"], 2 * worst)
        assert m1 >= self.MIN_MARGIN and m2 >= self.MIN_MARGIN, (
            f"{handle}: margin Buy 1 {m1:.0%}, Buy 2 {m2:.0%} on the most "
            f"expensive variant (landed ${worst}) — both must be >= 20%"
        )

    def test_not_above_market_median(self, handle):
        rec = self._record(handle)
        market = rec.get("market", [])
        assert len(market) >= 3, f"{handle}: need >= 3 market comparables"
        assert rec["price"] <= rec["market_median"], (
            f"{handle}: ${rec['price']} is above the market median "
            f"${rec['market_median']} (Level 03 pricing rule)"
        )


def _img_key(url):
    """Shopify serves one file under many sizes/params; compare the file name."""
    return (url or "").split("?")[0].rsplit("/", 1)[-1].lower()


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestVariantImages:
    """v2.6 — Level 01 rule 9 / Level 09 Section 7.A.2 / 7.D #43: the
    picture always matches what the customer chose. Every variant has its
    own verified CJ image, the main gallery follows the Buy 1 dropdown and
    every Buy 2 unit, and each Buy 2 unit row shows that unit's image.
    A missing image FAILS — it is never skipped (7.D #36)."""

    def _record(self, handle):
        path = os.path.join(VARIANT_IMAGES_DIR, f"{handle}.json")
        assert os.path.exists(path), (
            f"no variant-image record for {handle} at {path} — run Level 09 "
            f"7.A.2 and save it"
        )
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_every_variant_has_its_own_image_in_shopify(self, handle, shop_domain):
        data = TestV151Blockers()._shopify_product_json(handle, shop_domain)
        variants = data["variants"]
        if len(variants) < 2:
            return
        missing = [v["title"] for v in variants if not v.get("featured_image")]
        assert not missing, (
            f"{handle}: {len(missing)} variant(s) have no image, so Buy 2 "
            f"shows a grey box for them: {missing[:8]} (7.D #43)"
        )
        rec = {str(v["variant_id"]): v for v in self._record(handle)["variants"]}
        by_img = {}
        for v in variants:
            by_img.setdefault(_img_key(v["featured_image"]["src"]), []).append(v)
        for group in by_img.values():
            if len(group) < 2:
                continue
            for v in group:
                r = rec.get(str(v["id"]), {})
                assert r.get("shares_image_with"), (
                    f"{handle}: variants {[g['title'] for g in group]} share "
                    f"one image. Different colours or contents need different "
                    f"images; if they truly look identical, record "
                    f"shares_image_with and the reason (Level 09 7.A.2 step 3)"
                )

    def test_record_is_cj_checked_and_vision_matched(self, handle, shop_domain):
        data = TestV151Blockers()._shopify_product_json(handle, shop_domain)
        if len(data["variants"]) < 2:
            return
        rec = self._record(handle)
        ids = {str(v["variant_id"]) for v in rec["variants"]}
        live = {str(v["id"]) for v in data["variants"]}
        assert live <= ids, f"{handle}: variants not in the record: {live - ids}"
        for v in rec["variants"]:
            assert v.get("cj_source_url"), f"{handle}/{v['title']}: not from CJ"
            assert v["short_side"] >= 1000 and v["laplacian_var"] >= 100, (
                f"{handle}/{v['title']}: variant image is pixelated/soft"
            )
            assert v["cjk_chars"] == 0, f"{handle}/{v['title']}: Chinese text"
            assert v.get("vision_match") is True, (
                f"{handle}/{v['title']}: the image does not show this variant "
                f"({v.get('vision_answer')!r}) — fix the image or remove the "
                f"variant (Level 01 rule 9)"
            )

    def test_gallery_follows_buy1_choice(self, page, base_url, handle, shop_domain):
        data = TestV151Blockers()._shopify_product_json(handle, shop_domain)
        variants = [v for v in data["variants"] if v.get("available")]
        if len(variants) < 2:
            return
        _goto(page, base_url, handle)
        page.locator("[data-tier-card='1']").first.click()
        select = page.locator("[data-quantity-tiers] select").first
        for v in variants[:4]:
            value = select.locator(f"option[value$='{v['id']}']").first.get_attribute("value")
            select.select_option(value)
            page.wait_for_timeout(400)
            active = page.locator("[data-gallery-active] img").first
            assert active.count() > 0, (
                f"/products/{handle}: gallery has no [data-gallery-active] slide"
            )
            assert _img_key(active.get_attribute("src")) == _img_key(
                v["featured_image"]["src"]
            ), (
                f"/products/{handle}: chose {v['title']!r} but the main "
                f"gallery didn't move to its image (7.D #43)"
            )

    def test_buy2_unit_rows_show_the_chosen_variant(self, page, base_url, handle, shop_domain):
        data = TestV151Blockers()._shopify_product_json(handle, shop_domain)
        variants = [v for v in data["variants"] if v.get("available")]
        if len(variants) < 2:
            return
        _goto(page, base_url, handle)
        page.locator("[data-tier-card='2']").first.click()
        page.wait_for_timeout(300)
        for unit in (0, 1):
            sel = page.locator(f"#tier2-u{unit}-color")
            assert sel.count() > 0, f"/products/{handle}: no Buy 2 unit #{unit + 1} dropdown"
            for v in variants[:4]:
                value = sel.locator(f"option[value$='{v['id']}']").first.get_attribute("value")
                sel.select_option(value)
                page.wait_for_timeout(300)
                thumb = sel.locator("xpath=..").locator("[data-unit-preview]")
                assert thumb.count() > 0, (
                    f"/products/{handle}: Buy 2 unit #{unit + 1} shows a grey "
                    f"placeholder for {v['title']!r}, not its image (7.D #43)"
                )
                assert _img_key(thumb.get_attribute("src")) == _img_key(
                    v["featured_image"]["src"]
                ), f"/products/{handle}: unit #{unit + 1} thumbnail != {v['title']!r}"
                active = page.locator("[data-gallery-active] img").first
                assert _img_key(active.get_attribute("src")) == _img_key(
                    v["featured_image"]["src"]
                ), (
                    f"/products/{handle}: changed Buy 2 unit #{unit + 1} to "
                    f"{v['title']!r} but the main gallery didn't follow"
                )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestSupplyPriceGate:
    """v3.1 — Level 02 Section 2.H: we may not sell a product we buy for more
    than the customer can buy it for, and we may not put ad budget behind an
    order that is too thin to pay for a click. The gate lives in each pricing
    record's `supply_check` block. A missing block FAILS (7.D #36)."""

    AD_PROFIT_FLOOR = 12.0

    def _check(self, handle):
        path = os.path.join("store-profiles/alphaforbaby/pricing", f"{handle}.json")
        assert os.path.exists(path), f"no pricing record for {handle} at {path}"
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        sc = rec.get("supply_check")
        assert sc, (
            f"{handle}: no `supply_check` block — run the Level 02 2.H price "
            f"reality gate (cheapest CJ shipping, Temu/AliExpress consumer "
            f"price, verdict)"
        )
        return rec, sc

    def test_consumer_prices_were_actually_checked(self, handle):
        _, sc = self._check(handle)
        sites = {c["site"].lower() for c in sc.get("consumer_prices", [])}
        assert {"temu", "aliexpress"} <= sites, (
            f"{handle}: 2.H step 2 needs the regular Temu AND AliExpress price "
            f"for the same item, not only western retail (have: {sites})"
        )
        for c in sc["consumer_prices"]:
            assert c.get("url") and c.get("regular_price") and c.get("checked_at"), (
                f"{handle}: {c.get('site')} entry is missing url/regular_price/date"
            )
        assert sc.get("methods_considered"), (
            f"{handle}: 2.H step 1 — list the CJ shipping methods you compared "
            f"before accepting {sc.get('cheapest_method')}"
        )

    def test_we_are_not_undercut_at_source(self, handle):
        rec, sc = self._check(handle)
        cheapest_consumer = min(
            c["regular_price"] + c.get("shipping", 0) for c in sc["consumer_prices"]
        )
        landed = sc.get("landed", rec.get("worst_landed"))
        if landed >= cheapest_consumer:
            assert sc.get("verdict") in {"drop", "no_ads"} and sc.get("decided_by_itzik"), (
                f"{handle}: landed ${landed} >= ${cheapest_consumer} that the "
                f"customer pays on Temu/AliExpress (2.H fail (a)). Fix the "
                f"shipping or take the product down — it may not stay live on "
                f"an undecided record"
            )

    def test_ad_products_clear_the_profit_floor(self, handle):
        rec, sc = self._check(handle)
        profit = rec.get("profit_per_order")
        assert profit is not None, f"{handle}: pricing record has no profit_per_order"
        if profit < self.AD_PROFIT_FLOOR:
            assert sc.get("verdict") in {"no_ads", "drop"}, (
                f"{handle}: ${profit} profit per order is under the "
                f"${self.AD_PROFIT_FLOOR} ads floor (2.H fail (c)), but the "
                f"record still says verdict={sc.get('verdict')!r} — mark it "
                f"`no_ads` so no budget goes behind it, or fix the cost"
            )


class TestNavMatchesCatalog:
    """v3.2 — Level 05 Section 5B.1: the menu may only offer categories that
    actually hold a live product, and a product we approved may not quietly
    vanish from the catalog (7.D #50)."""

    NAV_CONFIG = os.environ.get("NAV_CONFIG", "app/theme.config.json")
    PRICING_DIR = "store-profiles/alphaforbaby/pricing"

    def _nav(self):
        assert os.path.exists(self.NAV_CONFIG), f"no {self.NAV_CONFIG}"
        with open(self.NAV_CONFIG, encoding="utf-8") as fh:
            return json.load(fh).get("nav", [])

    def _collection_count(self, shop_domain, handle):
        url = f"https://{shop_domain}/collections/{handle}/products.json?limit=50"
        req = urllib.request.Request(url, headers={"User-Agent": "compliance-suite"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return len(json.loads(resp.read().decode("utf-8", "replace"))["products"])
        except Exception:
            return -1

    def test_every_nav_link_has_products(self, shop_domain):
        empty = []
        for item in self._nav():
            url = item.get("url", "")
            if "/collections/" not in url:
                continue
            handle = url.rstrip("/").split("/collections/")[-1]
            n = self._collection_count(shop_domain, handle)
            if n <= 0:
                empty.append(f"{item.get('label')} -> /collections/{handle} ({n} products)")
        assert not empty, (
            f"the menu offers categories with nothing in them: {empty}. Remove "
            f"them from `nav` in theme.config.json until they hold a product "
            f"(Level 05 Section 5B.1)"
        )

    def test_no_account_link_in_the_menu(self):
        labels = {i.get("label", "").strip().lower() for i in self._nav()}
        assert not ({"sign in", "log in", "login", "account"} & labels), (
            f"the menu carries an account link ({labels}) — the store sells to "
            f"guests (Level 05 Section 5B.1 rule 3)"
        )

    def test_nav_is_not_bigger_than_the_catalog(self, base_url):
        live = len(_catalog_handles(base_url))
        cats = [i for i in self._nav() if "/collections/" in i.get("url", "")]
        if live < 6:
            assert not cats, (
                f"{live} live products but {len(cats)} category links — with "
                f"fewer than 6 products the nav is Home / Shop All / Contact "
                f"(Level 05 Section 5B.1 rule 2)"
            )

    def test_approved_products_are_still_live(self, base_url, shop_domain):
        if not os.path.isdir(self.PRICING_DIR):
            pytest.fail(f"no pricing records at {self.PRICING_DIR}")
        live = set(_catalog_handles(base_url))
        missing = []
        for name in sorted(os.listdir(self.PRICING_DIR)):
            if not name.endswith(".json"):
                continue
            handle = name[:-5]
            with open(os.path.join(self.PRICING_DIR, name), encoding="utf-8") as fh:
                rec = json.load(fh)
            approved = rec.get("approved_by_itzik") is True
            dropped = (rec.get("supply_check") or {}).get("verdict") == "drop" and (
                rec.get("supply_check") or {}
            ).get("decided_by_itzik")
            gated = handle in set(REVIEW_GATE_HIDDEN)
            if approved and not dropped and not gated and handle not in live:
                missing.append(handle)
        assert not missing, (
            f"approved, priced, built product(s) are not in the live catalog: "
            f"{missing}. Either Itzik decided to drop them (record it in "
            f"`supply_check`) or they were deleted by accident — restore them "
            f"from the repo records (Level 05 Section 5B.1 rule 5, 7.D #50)"
        )
```




Extend this file, don't replace it, as new bug patterns get added to 7.D
— each new 7.D entry should get a matching test here the same day, so
the next build checks for it mechanically instead of relying on someone
remembering to look.
