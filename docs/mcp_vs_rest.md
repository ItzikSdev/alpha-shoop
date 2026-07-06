# CJ: REST vs MCP — what each actually returns

Both hit the **same CJ backend**. REST is our existing path (`src/mcp_tools/sourcing.py`);
MCP is the real client (`src/cj_mcp/`). The point of MCP is **operations REST
doesn't expose** (live stock-by-country, tracking) — not richer product detail.
Product `pid` used below: `1665261893595959296` (the nursing pillow).

Raw capture: [`mcp_vs_rest_data.json`](./mcp_vs_rest_data.json).

---

## A. Product detail — REST wins (already rich)

`REST product/query` returns **55 fields**. We currently extract ~12 in
`search_trending_products` and drop the rest. Excerpt of the real payload:

```json
{
  "pid": "1665261893595959296",
  "productNameEn": "Adjustable Baby Cotton Nursing Arm Pillow ...",
  "productSku": "CJYD1770973",
  "productImageSet": ["https://.../b75f69d7...jpg", "...(47 total)"],
  "productWeight": "170.00-369.00",
  "packingWeight": "190.00-399.00",
  "categoryName": "Toys, Kids & Babies > Baby & Mother > Baby Care",
  "entryNameEn": "Polyester Breastfeed Pillow",
  "entryCode": "9404909000",            // HS customs code
  "materialNameEn": ["Cloth"],           // ← we drop this today
  "packingNameEn": ["Plastic bags"],     // ← we drop this today
  "sellPrice": "1.55-3.35",
  "suggestSellPrice": "8.62 - 34.52",
  "variants": [ /* 28 variants, each vid/variantKey/variantSellPrice */ ],
  "productVideo": ""
}
```

**Fields REST already gives us but we currently discard:** `materialNameEn`
(fabric), `packingNameEn` (box contents), `productWeight`, `packingWeight`,
`productUnit`, `supplierName`, `listedNum` (popularity), `productPro` (attributes),
`entryCode`/`entryNameEn` (customs). Extracting these is the cheapest "more data"
win — no MCP needed.

MCP's `query_sku_details` for the same `pid` returned `[]` (its id-space differs),
so **MCP is not a better source of product detail.**

---

## B. Inventory — MCP ONLY (REST subset can't do this)

`MCP get_product_inventory(pid, countryCode)` returns live per-warehouse stock —
data our REST path has no equivalent for:

```json
{
  "inventories": [
    {
      "areaEn": "China Warehouse", "countryCode": "CN",
      "totalInventoryNum": 352080, "cjInventoryNum": 2, "factoryInventoryNum": 352078
    },
    {
      "areaEn": "US Warehouse", "countryCode": "US",
      "totalInventoryNum": 332, "cjInventoryNum": 332, "factoryInventoryNum": 0
    }
  ]
}
```

So Sol can now answer "is this actually in a US warehouse?" (332 units) before
featuring or reordering — impossible via REST.

---

## C. Summary

| Capability | REST (`mcp_tools/sourcing.py`) | MCP (`src/cj_mcp/`) |
|---|---|---|
| Product detail (55 fields) | ✅ rich (underused) | ⚠️ `query_sku_details` returned `[]` |
| Catalog search | ✅ `product/list` | ✅ `query_sku_detail_page` (same backend) |
| **Stock by country** | ❌ | ✅ `get_product_inventory` |
| **Shipment tracking** | ❌ (CJ app handles) | ✅ `get_tracking_info` |
| Disputes / warehouses / webhooks | ❌ | ✅ |

**Takeaway:** MCP ≠ more product data; MCP = new *operations*. Use REST for
catalog/detail, MCP for inventory + tracking. Sol has both:
`cj_search_products` (REST) and `cj_product_inventory` / `cj_track_shipment` (MCP).
