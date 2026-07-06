"""Tests: the min-3-images sourcing gate (src/mcp_tools/sourcing.py).

Store rule (owner): a product must have at least 3 real supplier images to be
published — no single-image product pages on the storefront. The gate lives in
`search_trending_products(..., min_images=3)` so weak candidates are dropped
during sourcing and never reach the Shopify publisher.

These tests stub CJ's HTTP layer (`_cj_get`) with controlled products whose
image counts we choose, then assert the gate keeps only 3+ image products.
No network, no CJ credentials, fully deterministic.
"""
import pytest

from src.mcp_tools import sourcing


def _detail_with_images(n_images: int) -> dict:
    """A minimal-but-valid CJ product-detail payload carrying `n_images` photos."""
    return {
        "sellPrice": "5.00",
        "suggestSellPrice": "12.00",  # 12/5 = 2.4x → within the 3x cap → 58% margin
        "description": "Soft cotton baby bodysuit. 59cm fits 6M.",
        "productImageSet": [f"https://cf.cjdropshipping.com/img_{i}.jpg" for i in range(n_images)],
        "productVideo": "",
        # One variant is enough — single-variant products still get published.
        "variants": [
            {"vid": "V-0", "variantKey": "Beige-59cm", "variantSellPrice": "5.00"},
        ],
    }


@pytest.fixture
def fake_cj(monkeypatch):
    """Patch `_cj_get` so product/list + product/query return our fixtures.

    `image_counts` maps a pid -> how many images that product should have. The
    product list is derived from its keys so the two endpoints stay in sync.
    """
    def _install(image_counts: dict[str, int]):
        async def fake_get(client, path, params, token, retries=4):
            if path == "product/list":
                return {
                    "result": True,
                    "data": {
                        "list": [
                            {
                                "pid": pid,
                                "productNameEn": f"Baby Bodysuit {pid}",
                                "productImage": "https://cf.cjdropshipping.com/main.jpg",
                                "categoryName": "Baby Clothing",
                                "listingCount": 5,
                            }
                            for pid in image_counts
                        ]
                    },
                }
            if path == "product/query":
                pid = params["pid"]
                return {"result": True, "data": _detail_with_images(image_counts[pid])}
            raise AssertionError(f"unexpected CJ path: {path}")

        monkeypatch.setattr(sourcing, "_cj_get", fake_get)

    return _install


@pytest.mark.asyncio
async def test_drops_products_with_fewer_than_three_images(fake_cj):
    # A: 5 imgs (keep), B: 3 imgs (keep, boundary), C: 2 imgs (drop), D: 1 img (drop)
    fake_cj({"A": 5, "B": 3, "C": 2, "D": 1})

    products = await sourcing.search_trending_products(
        category="baby bodysuit", max_results=20, min_margin=0.30, min_images=3,
    )

    kept = {p["product_id"] for p in products}
    assert kept == {"A", "B"}, f"only 3+ image products should survive, got {kept}"
    # And every survivor genuinely carries 3+ images.
    assert all(len(p["images"]) >= 3 for p in products)


@pytest.mark.asyncio
async def test_boundary_exactly_three_images_is_kept(fake_cj):
    fake_cj({"EXACT3": 3})
    products = await sourcing.search_trending_products(
        category="baby bodysuit", min_images=3,
    )
    assert [p["product_id"] for p in products] == ["EXACT3"]


@pytest.mark.asyncio
async def test_min_images_zero_disables_the_gate(fake_cj):
    # With the gate off, even a single-image product comes through.
    fake_cj({"ONLY1": 1})
    products = await sourcing.search_trending_products(
        category="baby bodysuit", min_images=0,
    )
    assert [p["product_id"] for p in products] == ["ONLY1"]


@pytest.mark.asyncio
async def test_default_min_images_is_three(fake_cj):
    # Caller omits min_images entirely → the 3-image rule still applies.
    fake_cj({"HAS2": 2, "HAS4": 4})
    products = await sourcing.search_trending_products(category="baby bodysuit")
    assert [p["product_id"] for p in products] == ["HAS4"]
