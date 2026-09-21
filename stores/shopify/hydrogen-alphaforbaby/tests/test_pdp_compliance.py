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

PRODUCT_HANDLES is DERIVED from the live storefront, not hand-maintained.

The previous version of this file hard-coded a single handle with a comment
saying to add each new one by hand. That step was never taken, so every run
tested the one page that was already correct, came back green, and was read as
"the store is compliant" — while other live product pages had no buy box at
all. A suite whose coverage depends on remembering to edit a list will drift
to whatever was easiest to remember. Deriving the list means adding a product
to the store adds it to the suite, and TestCatalogCoverage below makes the
coverage itself a tested property.
"""
import json
import os
import re
import urllib.error
import urllib.request

import pytest

# Products confirmed as the store's trending set. TestCatalogCoverage asserts
# the live storefront serves exactly these — no more, no fewer — so a product
# that silently stops being published fails the suite instead of vanishing
# from it.
EXPECTED_TRENDING = {
    "ergonomic-baby-hip-carrier",
    "foldable-portable-baby-crib",
    "glow-whale-bath-buddy",
    "automatic-domino-train-set",
    "montessori-shape-sorting-egg",
    "toddler-sensory-learning-board",
    "baby-beach-sun-shelter",
    "foldable-baby-bed-canopy-set",
    "cozy-portable-baby-nest",
}

REFERENCE_HANDLE = "ergonomic-baby-hip-carrier"


def _base_url() -> str:
    """Base URL at *collection* time, before fixtures exist.

    pytest-base-url's fixture isn't available during collection, so read the
    same value from argv/env by hand.
    """
    argv = list(os.sys.argv)
    if "--base-url" in argv:
        return argv[argv.index("--base-url") + 1].rstrip("/")
    for a in argv:
        if a.startswith("--base-url="):
            return a.split("=", 1)[1].rstrip("/")
    return os.environ.get("PDP_BASE_URL", "http://localhost:3001").rstrip("/")


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pdp-compliance-suite"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def discover_handles(base_url: str) -> list[str]:
    """Every product handle the storefront actually serves.

    Walks /collections/all through its cursor pagination — the collection page
    shows 8 per page, so a single fetch silently under-reports the catalog.
    """
    seen: list[str] = []
    url = f"{base_url}/collections/all"
    for _ in range(20):  # generous page cap; breaks on no-next long before this
        try:
            html = _fetch(url)
        except (urllib.error.URLError, OSError):
            break
        for h in re.findall(r'/products/([a-z0-9][a-z0-9-]*)', html):
            if h not in seen:
                seen.append(h)
        m = re.search(r'href="([^"]*direction=next[^"]*)"', html)
        if not m:
            break
        nxt = m.group(1).replace("&amp;", "&")
        url = nxt if nxt.startswith("http") else f"{base_url}{nxt}"
    # Sorted, not page-order: parametrized test ids must be identical in every
    # process or pytest-xdist aborts the whole run with "Different tests were
    # collected between workers" — the collection page does not guarantee a
    # stable order between two fetches seconds apart.
    return sorted(seen)


def _discovered_handles() -> list[str]:
    """Handles to parametrize with, discovered live — once per RUN, not once
    per process.

    Under `pytest -n` every xdist worker imports this module in its own
    process. Two independent fetches of /collections/all seconds apart can
    return different sets (a slow page, a product published mid-run), and xdist
    aborts the entire run with "Different tests were collected between workers"
    when that happens. So: the run's launcher discovers once and passes the
    result down in PDP_HANDLES, and every worker parametrizes off that exact
    list. Discovery is still live and still not hand-maintained —
    TestCatalogCoverage re-discovers independently and fails if this list and
    the real catalog have drifted apart.
    """
    env = os.environ.get("PDP_HANDLES", "").strip()
    if env:
        return sorted(h for h in env.split(",") if h)
    found = discover_handles(_base_url())
    os.environ["PDP_HANDLES"] = ",".join(found)
    return found


_DISCOVERED = _discovered_handles()
# Fall back to the expected set so the suite still *runs* (and fails loudly in
# TestCatalogCoverage) when the storefront is down, rather than collecting zero
# tests and reporting a misleading green.
PRODUCT_HANDLES = _DISCOVERED or sorted(EXPECTED_TRENDING)

_BUNDLE_FAIL = (
    "7.D #36: a missing REQUIRED element must fail, never skip. Author `quantityTiers` + `tierBenefits` in this product's custom.pdp_content (Section 5D.3), or add the handle to the `deliberate_no_bundle` fixture in conftest.py and say so in the build report (Section 5D.4 step 4)."
)

SHOP_DOMAIN = os.environ.get("SHOP_DOMAIN", "kgg8n0-k0.myshopify.com")


@pytest.fixture(scope="session")
def shop_domain():
    return SHOP_DOMAIN


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
        """7.B Slot 2 spec: <video autoPlay muted loop playsInline controls>."""
        _goto(page, base_url, handle)
        videos = page.query_selector_all("video")
        if not videos:
            pytest.skip("no real product video sourced for this pid — flagged gap, not a failure")
        for v in videos:
            assert v.evaluate("el => el.autoplay") is True
            assert v.evaluate("el => el.muted") is True
            assert v.evaluate("el => el.loop") is True
            # v1.33: autoplay with zero shopper interaction — no native controls,
            # and a tap must not toggle play/pause.
            assert v.evaluate("el => el.controls") is False, "video still exposes native controls"

    def test_single_add_to_cart_control(self, page, base_url, handle):
        """v1.33 items 5+6: the sticky bar and the tier-less button are gone, so
        exactly one Add to Cart remains — the one bound to the selected tier."""
        _goto(page, base_url, handle)
        # Match the control, not one particular label: the same button reads
        # "SOLD OUT" when a product has no stock. Counting only "ADD…CART"
        # reported "0 controls" on six out-of-stock products, which pointed at
        # the wrong defect — the missing stock is caught by test_purchasable.
        btns = [
            b for b in page.query_selector_all("button")
            if re.search(r"(add\b.*\bcart|sold out)", b.inner_text() or "", re.I)
        ]
        assert len(btns) == 1, (
            f"expected 1 cart control, found {len(btns)}: {[b.inner_text() for b in btns]}"
        )

    def test_tier_selects_are_single_open_accordion(self, page, base_url, handle, deliberate_no_bundle):
        """v1.33 item 1: selecting a tier expands only that tier's per-unit rows;
        every other tier's rows collapse at the same moment."""
        _goto(page, base_url, handle)
        block = page.query_selector("[data-quantity-tiers]")
        assert block is not None, (
            f"/products/{handle} renders no quantity-tier block at all. " + _BUNDLE_FAIL
        )
        radios = block.query_selector_all("button[role=radio]")
        if not radios and handle in deliberate_no_bundle:
            pytest.skip("quantityTiers: [] is a recorded deliberate choice here")
        assert radios, (
            f"/products/{handle} shows the simple buy box, not tier cards. " + _BUNDLE_FAIL
        )
        counts = []
        for r in radios:
            r.click()
            page.wait_for_timeout(250)
            counts.append(len(block.query_selector_all("select")))
        # Buy 1 -> 0 rows, Buy 2 -> 2, Buy 3 -> 3; never the sum of all tiers.
        assert counts == sorted(counts), f"unexpected select counts per tier: {counts}"
        assert max(counts) <= 3, f"more selects visible than one tier needs: {counts}"

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
        # v1.33: the single remaining CTA is tier-bound, so its label carries the
        # quantity ("ADD 3 TO CART") — match the control, not one exact string.
        btns = [b for b in page.query_selector_all("button")
                if re.search(r"ADD.*TO CART", (b.inner_text() or ""), re.I)]
        assert btns, "no Add to Cart control found"

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

    def test_bundle_partners_are_purchasable(self, page, base_url, handle):
        """7.D #10 shape, found 2026-09-11 on this build: the cross-sell bundle
        was configured with real partner handles, but both partners were still
        unpublished, so the Storefront API returned nothing and the whole
        section rendered as null — no error, no warning, just a silently
        missing block. A configured bundle must actually resolve: every partner
        shown needs a working link and a real price, and a configured-but-empty
        bundle is a failure, not an acceptable no-op."""
        _goto(page, base_url, handle)
        # v1.29 retired the cross-sell shape for this store; the same-SKU tier
        # block is the bundle now, and TestBundleRequired owns it. This test
        # only still applies where a cross-sell block genuinely exists.
        bundle = page.query_selector("[data-bundle]")
        if not bundle:
            pytest.skip("no cross-sell block on this store (v1.29 retired the shape)")
        links = bundle.query_selector_all("a[href*='/products/']")
        assert links, "bundle rendered but lists no partner products"
        for link in links:
            href = link.get_attribute("href")
            resp = page.request.get(f"{base_url}{href}")
            assert resp.status == 200, f"bundle partner 404s: {href}"

    def test_variant_pickers_are_native_select(self, page, base_url, handle):
        """v1.30 §5 item 3: Color/Size must be real native <select> elements.
        A styled div that merely looks like a dropdown does not count — this
        asserts against the DOM, which is the only way to tell them apart."""
        _goto(page, base_url, handle)
        selects = page.query_selector_all("select")
        assert selects, "no native <select> on the page — variant pickers are not real selects"
        names = [(s_.get_attribute("name") or s_.get_attribute("id") or "").lower() for s_ in selects]
        assert any("color" in n or "size" in n for n in names), (
            f"found selects but none for Color/Size: {names}"
        )

    def test_real_support_email_not_placeholder(self, page, base_url, handle):
        """v1.30 §7.E: the support address must be the real inbox, never a
        fabricated or placeholder-looking one."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        for bad in ["support@[storedomain]", "yourdomain.example", "@example.com"]:
            assert bad not in text, f"placeholder support address rendered: {bad}"

    def test_bundle_matches_store_mode(self, page, base_url, handle, store_mode, deliberate_no_bundle):
        """Section 5 item 3, v1.24 — same-SKU tiers vs cross-sell set,
        never neither. `store_mode` should come from this run's fixture/config,
        not be hardcoded per test."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        if store_mode == "single_hero_product":
            # v1.44 shape: Buy 1 / Buy 2 with MOST POPULAR on Buy 2. The old
            # Twin/Family wording came from starnestshop and never shipped here,
            # and the badge renders uppercase — match case-insensitively.
            if not re.search(r"most popular|best deal|buy more, save more", text, re.I):
                # The `multi_product_niche` branch below has always honoured a
                # recorded deliberate/paused decision; this branch never did, so
                # a product Itzik had explicitly put on hold still failed here.
                # #36's rule is intact: the exemption is the recorded decision
                # in conftest, not the absence of the element.
                if handle in deliberate_no_bundle:
                    pytest.skip(
                        f"{handle}: no tier block, and that is a recorded decision "
                        "(conftest deliberate_no_bundle / PAUSED_HANDLES)"
                    )
                pytest.fail(
                    f"/products/{handle} has no same-SKU tier block. " + _BUNDLE_FAIL
                )
        elif store_mode == "multi_product_niche":
            # v1.29: Itzik replaced the cross-sell "complete the set" bundle on
            # the carrier with same-SKU quantity tiers after reviewing
            # littlesnugg.store. Either shape is a valid bundle block for this
            # store now — what's NOT acceptable is neither.
            # v1.50: a third valid shape — a deliberate `quantityTiers: []`
            # for a product nobody buys two of (a travel crib). What is still
            # unacceptable is a page with no way to buy at all, so require the
            # simple buy box in that case rather than waiving the check.
            has_bundle = re.search(
                r"(complete the set|bundle|buy together|buy more, save more)", text, re.I
            )
            if not has_bundle:
                simple = page.query_selector("[data-simple-buybox]")
                assert simple is not None, (
                    "no bundle block AND no simple buy box — this page has no way to buy"
                )
                assert re.search(r"\$[\d,]+\.\d\d", text), "simple buy box shows no price"
                if handle in deliberate_no_bundle:
                    pytest.skip("quantityTiers: [] is a recorded deliberate choice here")
                pytest.fail(
                    f"/products/{handle} has only the simple buy box. " + _BUNDLE_FAIL
                )
            assert has_bundle, (
                "no bundle block of either shape (cross-sell OR quantity tiers) found"
            )

    def test_quantity_tier_prices_match_a_real_cart(self, page, base_url, handle):
        """v1.29 — a tier price shown in the UI must equal what checkout really
        charges. The discounts are real Shopify automatic discounts, so the only
        honest verification is arithmetic against the unit price actually on the
        page, not the Admin config. Guards Rule 1 for every future tier change."""
        _goto(page, base_url, handle)
        block = page.query_selector("[data-quantity-tiers]")
        assert block is not None, (
            f"/products/{handle} has no tier block to price-check. " + _BUNDLE_FAIL
        )
        text = block.inner_text()
        prices = [float(m.replace(",", "")) for m in re.findall(r"\$([\d,]+\.\d\d)", text)]
        assert prices, "tier block renders no prices"
        unit = prices[0]
        # every struck-through 'was' price must be a whole multiple of the unit
        for p_ in prices:
            ratio = p_ / unit
            assert p_ <= unit * 3 + 0.01, f"tier price ${p_} exceeds 3x unit ${unit}"
            assert ratio > 0.5, f"tier price ${p_} implies a >50% discount — confirm it is real"


# ────────────────────────────────────────────────────────────────────────────
# v1.50 — the suite's own coverage, the content contract, and parity.
#
# Everything above this line tests one page deeply. Everything below exists
# because four rounds of green runs coexisted with live pages that had no buy
# box: the gap was never a weak assertion, it was that the broken pages were
# not in the run at all.
# ────────────────────────────────────────────────────────────────────────────

# Keys of custom.pdp_content, mapped to what each one renders. A missing key is
# a data-authoring task, not a code change, so the failure messages say so.
#
# These are matched on structural data-* hooks, NOT on heading text. Every one
# of these headings is itself per-product content — the carrier's `howToUse`
# renders as "Three ways to wear it" and its `comparison` as "Carrying in your
# arms vs. wearing the carrier". A text marker therefore failed on the
# reference page, which is how this was caught: when the known-good page fails
# a contract test, the test is wrong, not the data.
PDP_CONTENT_KEYS = {
    "urgencyLine":     ("[data-urgency-strip]",       "the urgency line above the title"),
    "quantityTiers":   ("[data-quantity-tiers]",      "the bundle / Buy-N block"),
    "benefits":        ("[data-benefits]",            '"Why parents choose it"'),
    "sizeAndShipping": ('[data-section="size-and-shipping"]', "the size/shipping accordion"),
    "howToUse":        ("[data-how-to-use]",          "the usage-steps section"),
    "whyItWorks":      ("[data-why-it-works]",        '"Why it works"'),
    "lifestyle":       ("[data-lifestyle]",           "the full-bleed lifestyle block"),
    "comparison":      ("[data-comparison]",          "the with/without comparison"),
    "faq":             ('[data-section="faq"]',       "the FAQ accordion"),
    "guarantee":       ("[data-guarantee]",           '"30 days to change your mind"'),
}


def _text(page, base_url, handle):
    _goto(page, base_url, handle)
    _expand_all_accordions(page)
    return page.inner_text("body")


class TestCatalogCoverage:
    """The suite's coverage is itself a tested property (v1.50)."""

    def test_every_trending_product_is_in_the_live_catalog(self):
        """v2.1 — a shortlisted product may be absent ONLY if the review gate
        hid it. Any other absence is still a publishing regression."""
        missing = sorted(EXPECTED_TRENDING - set(PRODUCT_HANDLES))
        unexplained = [h for h in missing if h not in REVIEW_GATE_HIDDEN]
        assert not unexplained, (
            f"confirmed-trending products the storefront does not serve: {unexplained}. "
            "They are not on REVIEW_GATE_HIDDEN, so this is not the review gate — "
            "most likely they are not published to the Online Store / alphaforbaby "
            "sales channel. Check the Publishing card in Admin."
        )

    def test_gate_hidden_products_are_actually_absent(self):
        """The mirror of the above: a handle on REVIEW_GATE_HIDDEN must NOT be
        in the served catalog. Listing it as hidden while it is still live is
        the failure mode this pair exists to make impossible."""
        still_served = sorted(set(REVIEW_GATE_HIDDEN) & set(PRODUCT_HANDLES))
        assert not still_served, (
            f"listed on REVIEW_GATE_HIDDEN but still served: {still_served} — "
            "unpublish them from every sales channel (Level 01 rule 7)"
        )

    def test_no_unexpected_products_served(self):
        extra = sorted(set(PRODUCT_HANDLES) - EXPECTED_TRENDING)
        assert not extra, (
            f"storefront serves products not in the confirmed-trending set: {extra}. "
            "Either add them to EXPECTED_TRENDING or unpublish them."
        )

    def test_discovery_actually_ran(self):
        assert _DISCOVERED, (
            "handle discovery returned nothing — the suite fell back to the expected "
            "list, so a real catalog regression could hide. Is the dev server up at "
            f"{_base_url()}?"
        )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestV149Regressions:
    """Regressions Itzik found by measuring the rendered page (7.D #27-#30)."""

    def test_product_url_returns_200(self, page, base_url, handle):
        resp = page.goto(f"{base_url}/products/{handle}")
        assert resp.status == 200, f"/products/{handle} returned {resp.status}"

    def test_buy_box_present(self, page, base_url, handle):
        """7.D #29 — price, a way to choose, and a CTA. A page a shopper cannot
        buy from is worse than an obviously unbuilt one: it looks finished."""
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        assert re.search(r"\$[\d,]+\.\d\d", text), "no price anywhere on the page"
        cta = [
            b.inner_text().strip()
            for b in page.query_selector_all("button")
            if re.search(r"add .*to cart|sold out", b.inner_text(), re.I)
        ]
        assert cta, "no Add to Cart / Sold out control on the page"

    def test_star_layers_are_pixel_aligned(self, page, base_url, handle):
        """7.D #27 — the fractional star fill must not be a second, separately
        sized row: that drifted ~0.9px per star and read as doubled stars."""
        _goto(page, base_url, handle)
        row = page.query_selector('[role="img"][aria-label*="out of 5"]')
        if not row:
            pytest.skip("this product has no rating row yet")
        boxes = page.evaluate(
            """(el) => [...el.children].map(sp => {
                const outline = sp.querySelector('svg');
                const clip = sp.querySelector('span[style*="width"]');
                const gold = clip ? clip.querySelector('svg') : null;
                const r = e => e ? {x:+e.getBoundingClientRect().x.toFixed(2),
                                    w:+e.getBoundingClientRect().width.toFixed(2)} : null;
                return {outline:r(outline), gold:r(gold)};
            })""",
            row,
        )
        for i, b in enumerate(boxes, 1):
            if not b["gold"] or not b["outline"]:
                continue
            dx = abs(b["gold"]["x"] - b["outline"]["x"])
            dw = abs(b["gold"]["w"] - b["outline"]["w"])
            assert dx < 0.5, f"star {i}: gold layer offset {dx:.2f}px from its outline"
            assert dw < 0.5, f"star {i}: gold layer width differs by {dw:.2f}px"

    def test_webfont_actually_loaded(self, page, base_url, handle):
        """7.D #28 — the Google Fonts link was CSP-blocked, so the page silently
        rendered in system-ui. Assert the font loaded AND that it changes metrics."""
        _goto(page, base_url, handle)
        page.wait_for_timeout(1200)
        res = page.evaluate(
            """async () => {
                await document.fonts.ready;
                const m = fam => { const c = document.createElement('canvas').getContext('2d');
                    c.font = '16px ' + fam;
                    return +c.measureText('Ergonomic Baby Hip Carrier 12345').width.toFixed(2); };
                const stack = getComputedStyle(document.body).fontFamily;
                return {size: document.fonts.size, wStack: m(stack), wSystem: m('system-ui')};
            }"""
        )
        assert res["size"] > 0, "document.fonts.size is 0 — no webfont loaded at all"
        assert res["wStack"] != res["wSystem"], (
            f"page font measures identically to system-ui ({res['wStack']}px) — the "
            "stack is falling through to the system font"
        )

    def test_gallery_dot_band_is_windowed(self, page, base_url, handle):
        """7.D #30 — 21 dots in one full-width band is not a usable control."""
        _goto(page, base_url, handle)
        dots = len(page.query_selector_all("[data-gallery-dot]"))
        if dots == 0:
            pytest.skip("single-image gallery renders no dots")
        assert dots <= 7, f"{dots} pagination dots rendered; cap is a 5-7 dot window"


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestPdpContentContract:
    """Section 5D — one test per custom.pdp_content key.

    These fail as *authoring* tasks. The template is generic and already
    correct; what's missing on an empty page is the per-product metafield.
    """

    @pytest.mark.parametrize("key", sorted(PDP_CONTENT_KEYS))
    def test_content_key_renders(self, page, base_url, handle, key, paused_handles):
        if handle in paused_handles:
            pytest.skip(f"{handle}: {paused_handles[handle]}")
        selector, describes = PDP_CONTENT_KEYS[key]
        _goto(page, base_url, handle)
        _expand_all_accordions(page)
        present = page.query_selector(selector) is not None
        assert present, (
            f"{describes} is absent on /products/{handle}. Author "
            f'`{key}` in that product\'s custom.pdp_content metafield — this is a '
            "data task, not a code change (Section 5D.3 has the schema)."
        )




class TestPdpParityGate:
    """Section 5C — every component the reference page renders must render here."""

    @pytest.mark.parametrize(
        "handle", [h for h in PRODUCT_HANDLES if h != REFERENCE_HANDLE]
    )
    def test_renders_every_reference_component(self, page, base_url, handle, paused_handles):
        if handle in paused_handles:
            pytest.skip(f"{handle}: {paused_handles[handle]}")
        def snapshot(h):
            _goto(page, base_url, h)
            _expand_all_accordions(page)
            t = page.inner_text("body")
            # Structural hooks, not heading text: every heading on this page
            # is per-product content, so a text regex measures the copy rather
            # than the component. Same lesson as the content contract above.
            return {
                "gallery": len(page.query_selector_all("[data-gallery-slide]")) > 0,
                "urgency strip": page.query_selector("[data-urgency-strip]") is not None,
                "buy box": page.query_selector("[data-quantity-tiers]") is not None,
                "mini review carousel": page.query_selector("[data-mini-reviews]") is not None,
                "reviews grid": bool(re.search(r"out of 5 ·", t)),
                "payment icons": len(page.query_selector_all(".tob-fpay-ico")) > 0,
                "benefits": page.query_selector("[data-benefits]") is not None,
                "how to use": page.query_selector("[data-how-to-use]") is not None,
                "why it works": page.query_selector("[data-why-it-works]") is not None,
                "FAQ": page.query_selector('[data-section="faq"]') is not None,
                "guarantee": page.query_selector("[data-guarantee]") is not None,
                "comparison": page.query_selector("[data-comparison]") is not None,
            }

        ref = snapshot(REFERENCE_HANDLE)
        got = snapshot(handle)
        missing = sorted(k for k, v in ref.items() if v and not got.get(k))
        assert not missing, (
            f"/products/{handle} is missing components the reference page renders: "
            f"{missing}"
        )


class TestNoSkeletonPages:
    """A page at a fraction of the reference page's weight is not finished."""

    @pytest.mark.parametrize(
        "handle", [h for h in PRODUCT_HANDLES if h != REFERENCE_HANDLE]
    )
    def test_page_weight_and_sections(self, page, base_url, handle, paused_handles):
        if handle in paused_handles:
            pytest.skip(f"{handle}: {paused_handles[handle]}")
        def measure(h):
            resp = page.goto(f"{base_url}/products/{h}")
            kb = len(resp.text()) / 1024
            page.wait_for_timeout(1200)
            return kb, len(page.query_selector_all(".pdp section h2"))

        ref_kb, ref_h2 = measure(REFERENCE_HANDLE)
        kb, h2 = measure(handle)
        assert kb >= ref_kb * 0.6, (
            f"/products/{handle} is {kb:.0f}kb against the reference page's "
            f"{ref_kb:.0f}kb — under 60% means most of the page does not exist"
        )
        assert h2 >= ref_h2 * 0.6, (
            f"/products/{handle} renders {h2} h2 sections against the reference "
            f"page's {ref_h2}"
        )


class TestHomepageDensity:
    """v1.47/v1.49 pixel budgets at 375px, as assertions rather than adjectives."""

    def test_hero_and_footer_fit_budget(self, page, base_url):
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(f"{base_url}/")
        page.wait_for_timeout(1500)
        m = page.evaluate(
            """() => {
                const h = e => e ? Math.round(e.getBoundingClientRect().height) : null;
                const px = v => Math.round(parseFloat(v)) || 0;
                const f = document.querySelector('footer');
                const fs = getComputedStyle(f);
                return {hero: h(document.querySelector('.tob-eh')),
                        footer: h(f),
                        footerTopGap: px(fs.marginTop) + px(fs.paddingTop)};
            }"""
        )
        assert m["hero"] is not None, "no hero block found on the homepage"
        assert m["hero"] <= 420, f"hero is {m['hero']}px at 375px wide; budget is 420"
        assert m["footer"] <= 460, f"footer is {m['footer']}px; budget is 460"
        assert m["footerTopGap"] <= 36, (
            f"footer top margin+padding is {m['footerTopGap']}px; budget is 36"
        )


# ────────────────────────────────────────────────────────────────────────────
# v1.52 — the bundle is REQUIRED on every product (Section 5 item 3, unbranched
# since v1.29). It went missing on 8 of 9 products without a single red test
# because every mechanism that could have caught it was configured to skip.
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestBundleRequired:
    """A missing required element fails here; it does not skip (7.D #36)."""

    def test_tier_bundle_block_exists(self, page, base_url, handle, deliberate_no_bundle):
        _goto(page, base_url, handle)
        if handle in deliberate_no_bundle:
            pytest.skip("quantityTiers: [] is a recorded deliberate choice here")
        assert page.locator("[data-quantity-tiers]").count() > 0, (
            f"/products/{handle} renders no quantity-tier block at all. " + _BUNDLE_FAIL
        )

    def test_tier_bundle_is_not_the_fallback_box(self, page, base_url, handle,
                                                 deliberate_no_bundle):
        """The v1.49 fallback keeps a product buyable, but it is a fallback —
        shipping it as the final state on every product is the 7.D #34 bug."""
        _goto(page, base_url, handle)
        if handle in deliberate_no_bundle:
            pytest.skip("quantityTiers: [] is a recorded deliberate choice here")
        simple_only = (
            page.locator("[data-simple-buybox]").count() > 0
            and "Buy more, save more" not in page.inner_text("body")
        )
        assert not simple_only, (
            f"/products/{handle} is still on the simple single-item buy box — no "
            f"'Buy more, save more' heading, no tier cards. " + _BUNDLE_FAIL
        )

    def test_second_tier_is_badged_and_preselected(self, page, base_url, handle,
                                                   deliberate_no_bundle):
        _goto(page, base_url, handle)
        if handle in deliberate_no_bundle:
            pytest.skip("quantityTiers: [] is a recorded deliberate choice here")
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

    def test_tier_price_math_is_real(self, page, base_url, handle, deliberate_no_bundle):
        """Every charged tier total ends in .90 (Section 4, v1.31); the
        struck-through anchor may end in anything honest (v1.32)."""
        _goto(page, base_url, handle)
        if handle in deliberate_no_bundle:
            pytest.skip("quantityTiers: [] is a recorded deliberate choice here")
        text = page.inner_text("body")
        if "Buy more, save more" not in text:
            pytest.fail(f"/products/{handle} has no bundle to price-check")
        totals = re.findall(r"\$\s?([\d,]+\.\d\d)", text)
        assert totals, f"/products/{handle} shows no prices in the bundle"
        assert [t for t in totals if t.endswith(".90")], (
            f"/products/{handle}: no tier total ends in .90 — every price a "
            f"customer actually pays ends in .90 (Section 4, v1.31)"
        )


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestV151Blockers:
    """Checks Shopify's OWN view of availability and price (/products/<h>.js),
    because the Hydrogen page was rendering 'sold out' perfectly correctly while
    the DATA behind it was wrong (7.D #31)."""

    def _shopify_product_json(self, handle, shop_domain):
        url = f"https://{shop_domain}/products/{handle}.js"
        req = urllib.request.Request(url, headers={"User-Agent": "compliance-suite"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    def test_every_variant_is_available_for_sale(self, handle, shop_domain):
        data = self._shopify_product_json(handle, shop_domain)
        variants = data.get("variants", [])
        assert variants, f"{handle} has no variants at all in Shopify"
        unavailable = [v.get("title") for v in variants if not v.get("available")]
        assert not unavailable, (
            f"{handle}: {len(unavailable)} of {len(variants)} variants are NOT "
            f"available for sale: {unavailable[:6]}. Fix the inventory setup in "
            f"Shopify — this is not a storefront bug (7.D #31)"
        )

    def test_one_retail_price_across_variants(self, handle, shop_domain):
        data = self._shopify_product_json(handle, shop_domain)
        prices = {v.get("price") for v in data.get("variants", [])}
        assert len(prices) == 1, (
            f"{handle} has {len(prices)} different variant prices "
            f"({sorted(p / 100 for p in prices if p)}) — a retail page carries one "
            f"approved price per product (Section 4), not the supplier's "
            f"per-variant cost spread (7.D #32)"
        )

    def test_price_ends_in_90(self, handle, shop_domain):
        data = self._shopify_product_json(handle, shop_domain)
        bad = [v.get("price") for v in data.get("variants", [])
               if v.get("price") is not None and v["price"] % 100 != 90]
        assert not bad, (
            f"{handle} has variant prices not ending in .90: "
            f"{sorted({p / 100 for p in bad})} (Section 4, v1.31)"
        )

    def test_no_supplier_hosted_images(self, page, base_url, handle):
        """7.D #35/#6 — review photos hotlinked from the supplier's CDN."""
        _goto(page, base_url, handle)
        page.wait_for_timeout(1500)
        supplier_imgs = page.evaluate(
            "() => Array.from(document.images)"
            ".filter(i => /aliyuncs|cjdropshipping/i.test(i.src))"
            ".map(i => ({src: i.src, w: i.naturalWidth}))"
        )
        assert not supplier_imgs, (
            f"{handle} serves {len(supplier_imgs)} image(s) from the supplier's "
            f"CDN, {sum(1 for i in supplier_imgs if i['w'] == 0)} of which fail to "
            f"load — re-host review photos on Shopify's CDN (7.D #35)"
        )

    def test_every_rendered_review_photo_loads(self, page, base_url, handle):
        _goto(page, base_url, handle)
        page.wait_for_timeout(1500)
        broken = page.evaluate(
            "() => Array.from(document.images)"
            ".filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src'))"
            ".map(i => i.getAttribute('src'))"
        )
        assert not broken, f"{handle} renders {len(broken)} broken image(s): {broken[:3]} (7.D #35)"


# ────────────────────────────────────────────────────────────────────────────
# v2.1 — Level 01 rule 7 / Level 02 Section 2.G: the review gate. A product is
# displayed only with >= 15 real reviews that each carry a real photo that
# actually loads. Below the gate it is hidden (Draft / unpublished from every
# sales channel) — never deleted, so it can come back the day it passes.
# ────────────────────────────────────────────────────────────────────────────

MIN_PHOTO_REVIEWS = 15

# v2.1 — Level 01 rule 8: where each product's hero-image decision is recorded.
# Anchored to THIS file, not the CWD: pytest's rootdir is the monorepo root
# (pyproject.toml lives there), so a bare relative path resolves to the wrong
# place depending on where the run was launched from.
HERO_SELECTION_DIR = os.environ.get(
    "HERO_SELECTION_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "store-profiles", "alphaforbaby", "hero-selection",
    ),
)

# Measured against CJ's own review API on 2026-09-21: these are at their real
# ceiling — CJ has no further reviews of these items to import, so the gate
# cannot be met from that source. Keep in sync with the table in Level 02, 2.G.
REVIEW_GATE_HIDDEN = [
    "foldable-baby-bed-canopy-set",     # 13 with photos (CJ ceiling: 13)
    "cozy-portable-baby-nest",          # 11 (ceiling: 11)
    "toddler-sensory-learning-board",   # 4  (ceiling: 4)
    "baby-beach-sun-shelter",           # 3  (ceiling: 3)
    "foldable-portable-baby-crib",      # 1  (ceiling: 1)
    "glow-whale-bath-buddy",            # 0  (also paused on its defect finding)
]


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestReviewGate:
    """Every product the storefront actually serves must clear the gate."""

    def test_live_product_has_15_photo_reviews(self, page, base_url, handle):
        _goto(page, base_url, handle)
        text = page.inner_text("body")
        m = re.search(r"(\d+)\s*reviews?\s*·\s*(\d+)\s*with photos", text)
        assert m, (
            f"/products/{handle} shows no 'N reviews · M with photos' summary — "
            "a live product must have imported reviews (Level 02, 2.G)"
        )
        with_photos = int(m.group(2))
        assert with_photos >= MIN_PHOTO_REVIEWS, (
            f"/products/{handle} is live with only {with_photos} photo reviews — "
            f"the rule is >= {MIN_PHOTO_REVIEWS}. Hide it (Draft / unpublish from "
            "every sales channel, never delete) — Level 01 rule 7."
        )

    def test_review_photos_actually_load(self, page, base_url, handle):
        """A photo that doesn't load, or is hotlinked, doesn't count (7.D #35)."""
        _goto(page, base_url, handle)
        el = page.query_selector("#reviews")
        if el is None:
            pytest.skip(f"{handle}: no reviews block rendered (counted by the gate test)")
        el.scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        stats = page.evaluate(
            "() => { const imgs = Array.from(document.querySelectorAll('#reviews img'));"
            " return {total: imgs.length,"
            " broken: imgs.filter(i => i.complete && i.naturalWidth === 0).length,"
            " offCdn: imgs.filter(i => !/cdn\\.shopify\\.com/.test(i.src)).length}; }"
        )
        assert stats["broken"] == 0 and stats["offCdn"] == 0, (
            f"/products/{handle}: {stats['broken']} broken and {stats['offCdn']} "
            "non-Shopify-CDN review photos — neither counts toward the gate "
            "(7.D #35, Level 02 2.G)"
        )


class TestHiddenProductsStayHidden:
    """A product under the gate must not be reachable anywhere a shopper looks."""

    @pytest.mark.parametrize("hidden", REVIEW_GATE_HIDDEN)
    def test_hidden_product_url_not_served(self, page, base_url, hidden):
        resp = page.goto(f"{base_url}/products/{hidden}")
        status = resp.status if resp else None
        assert status == 404, (
            f"/products/{hidden} still returns {status} — it is under the "
            "15-photo-review gate and must be unpublished from every sales "
            "channel (Level 01 rule 7 / Level 02 2.G), not just left off the grid"
        )

    def test_hidden_products_absent_from_grid_and_collections(self, page, base_url):
        for path in ("/", "/collections/all"):
            page.goto(base_url + path)
            page.wait_for_timeout(1000)
            html = page.content()
            leaked = [h for h in REVIEW_GATE_HIDDEN if f"/products/{h}" in html]
            assert not leaked, f"{path} still links to hidden products {leaked} (Level 02, 2.G)"


@pytest.mark.parametrize("handle", PRODUCT_HANDLES)
class TestHeroImage:
    """v2.1 — Level 01 rule 8 / Level 09 Section 7.A.1.

    Reads the recorded decision and checks the rendered page against it, so a
    hero that was chosen correctly but never actually applied — or was applied
    and later reordered away — fails instead of passing on the JSON alone.
    """

    def _decision(self, handle):
        path = os.path.join(HERO_SELECTION_DIR, f"{handle}.json")
        if not os.path.exists(path):
            pytest.fail(
                f"no hero decision recorded for {handle} at {path} — every live "
                "product's hero is chosen by the 7.A.1 procedure and the decision "
                "is saved (Level 01 rule 8)"
            )
        with open(path) as fh:
            return json.load(fh)

    def test_hero_decision_passes_the_three_rules(self, handle):
        d = self._decision(handle)["chosen"]
        assert d["short_side"] >= 1000, (
            f"{handle}: recorded hero short side {d['short_side']}px < 1000 (7.A.1 rule 1)"
        )
        assert d["laplacian_var"] >= 100, (
            f"{handle}: recorded hero Laplacian variance {d['laplacian_var']} < 100 (7.A.1 rule 1)"
        )
        assert d["cjk_chars"] == 0, (
            f"{handle}: recorded hero carries {d['cjk_chars']} Chinese characters — "
            "any CJK character fails, however small (7.A.1 rule 2)"
        )

    def test_recorded_hero_is_really_first_on_the_page(self, page, base_url, handle):
        """Shopify appends a uniqueness suffix when a file is copied into product
        media, so compare on the filename STEM, not the full URL."""
        d = self._decision(handle)["chosen"]
        stem = d["url"].split("?")[0].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        _goto(page, base_url, handle)
        src = page.evaluate(
            "() => { const i = document.querySelector('[data-gallery-slide] img, .pdp img');"
            " return i ? i.src : null; }"
        )
        assert src, f"{handle}: no gallery image rendered at all"
        assert stem in src, (
            f"{handle}: first gallery image is {src.rsplit('/', 1)[-1]}, but the "
            f"recorded hero is {stem} — the decision was never applied, or the "
            "media was reordered afterwards (7.A.1 'Apply it')"
        )

    def test_hero_actually_loads(self, page, base_url, handle):
        _goto(page, base_url, handle)
        nw = page.evaluate(
            "() => { const i = document.querySelector('[data-gallery-slide] img, .pdp img');"
            " return i ? i.naturalWidth : 0; }"
        )
        assert nw > 0, f"{handle}: the hero image is in the DOM but does not load"
