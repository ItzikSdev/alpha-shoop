"""Fixtures for the PDP compliance suite (store-builder-skill v1.52, §12).

v1.52 replaced the v1.25 fixture that lived here. The old one defaulted
`--store-mode` to `multi_product_niche` and its docstring claimed alphaforbaby
wants a cross-sell "complete the set" bundle "rather than same-SKU quantity
tiers" — the exact branch Section 5 item 3 retired in v1.29. The suite's own
configuration therefore said the tier bundle wasn't expected on this store,
which is half of why the bundle went missing on 8 of 9 products without a
single red test (7.D #36). The other half was `pytest.skip()` standing in for
a missing required element; both are fixed together.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--store-mode",
        action="store",
        default="single_hero_product",
        choices=["single_hero_product", "multi_product_niche"],
        help=(
            "Kept only for callers that still read it. It no longer decides the "
            "bundle shape — since v1.29 every product uses the same-SKU "
            "Buy 1 / Buy 2 quantity-tier block regardless of store_mode."
        ),
    )


@pytest.fixture(scope="session")
def store_mode(request):
    """v1.29 retired the store_mode branch for the bundle: every product uses
    the same-SKU quantity-tier block. Kept only for callers that still read it.
    """
    return request.config.getoption("--store-mode")


@pytest.fixture(scope="session")
def deliberate_no_bundle():
    """Handles where `quantityTiers: []` is an intentional, reported decision.

    Section 5D.4 step 4 and 7.D #34 both allow a product to ship with no tier
    block when a second unit genuinely makes no sense — but "deliberate" has to
    be recorded somewhere a test can read, or it is indistinguishable from "not
    authored yet", which is the exact ambiguity 7.D #36 was written about.
    Adding a handle here is a claim that the build report says so explicitly.
    """
    # Paused products cannot have a bundle authored for them either — the same
    # decision covers both, so they are folded in rather than listed twice.
    return set(PAUSED_HANDLES) | set(NO_BUNDLE_HANDLES)


# Products that ARE live and built, but for which no Buy-2 discount can be
# offered — recorded with the reason, same discipline as PAUSED_HANDLES.
NO_BUNDLE_HANDLES = {
    # 2026-09-21, Level 03's 20% pricing rule (v2.3): at the repriced $42.90
    # unit, 2x gross is $85.80 and the floor total (2x landed cost, >=20%
    # margin) is $85.32 -- only $0.48 of headroom. Real charged totals must
    # end in .90 (v1.31/v1.32), and .90-ending values are $1.00 apart, so no
    # value both clears the floor and is actually below 2x gross: $84.90
    # breaks the floor, $85.90 is a surcharge, not a discount. No compliant
    # Buy-2 total exists at this price -- the bundle is removed rather than
    # either breaking the 20% floor or faking a discount.
    "ergonomic-baby-hip-carrier": "no .90-ending Buy-2 total clears the 20% floor at $42.90 (Level 03 pricing rule)",
}


# Products deliberately held out of the build pipeline by an explicit owner
# decision, with the reason on record. This is NOT the same thing as "not
# built yet" (7.D #36) — a handle only belongs here when Itzik has decided to
# hold it, and the reason is written next to it. Everything else must fail.
PAUSED_HANDLES = {
    # 2026-09-21, Itzik's call: held pending his decision on the product's real
    # 16%-defect finding (Level 02). Its page is deliberately unbuilt — no
    # custom.pdp_content at all — so every content/parity assertion on it would
    # report a gap that is already known and already owned.
    "glow-whale-bath-buddy": "paused pending the 16%-defect decision (Level 02)",
}


@pytest.fixture(scope="session")
def paused_handles():
    """Handles held out of the build pipeline by an explicit, recorded decision.

    Tests that assert a product page is *built* consult this and skip with the
    recorded reason instead of failing. 7.D #36 still holds for everything
    else: a skip here is only legitimate because the gap is owned and written
    down, not because the element happens to be missing.
    """
    return dict(PAUSED_HANDLES)
