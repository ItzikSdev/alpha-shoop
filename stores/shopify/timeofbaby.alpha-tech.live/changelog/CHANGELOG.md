# TIMEOF BABY — Store Changelog

Every change to the store is recorded here. **Newest on top.** Format and rules:
see [README.md](./README.md). Times are Asia/Jerusalem.

---

## 2026-06-28 08:30 (Asia/Jerusalem) — הפעילי scan_store כדי לקבל את ה-store_id המדויק של timeofbaby_kgg, ואז הפעילי ap
**By:** Grace
**Context:** שלום! אני Grace. קיבלתי את המשימה מלינוס: להפעיל scan_store כדי לקבל את ה-store_id המדויק של timeofbaby_kgg, ואז להפעיל apply_design עם ה-store_id שהוחזר בפועל ועם מבנה site.json בסיסי.

אני מציעה את 
**Changed:** Re-rendered site.json (v3) → live homepage (theme 142662238279).

## 2026-06-28 08:27 (Asia/Jerusalem) — הפעילי scan_store כדי לקבל את ה-store_id המדויק של timeofbaby_kgg, ואז הפעילי ap
**By:** Grace
**Context:** שלום! אני Grace. קיבלתי את המשימה מלינוס: להפעיל scan_store כדי לקבל את ה-store_id המדויק של timeofbaby_kgg, ואז להפעיל apply_design עם ה-store_id שהוחזר בפועל ועם מבנה site.json בסיסי (sections: hero
**Changed:** Re-rendered site.json (v3) → live homepage (theme 142662238279).

## 2026-06-28 08:26 (Asia/Jerusalem) — Reorganized store folder → stores/shopify/<domain>/{style,readme,changelog}
**By:** Itzik + Claude
**Context:** Folders were disorganized; consolidating to one clean per-store source-of-truth tree.
**Changed:** Moved design files from styles/shopify/timeofbaby/ to stores/shopify/timeofbaby.alpha-tech.live/style/; README→readme/, CHANGELOG→changelog/. Deleted junk raw-theme dump stores/shopify/kgg8n0-k0. Repointed render code (design_files, shopify_design, delegation) + prompts; mounted ./stores RW in docker-compose.dev.yml.

## 2026-06-28 07:58 (Asia/Jerusalem) — Restored premium homepage + product page after overnight revert
**By:** system (Itzik + Claude)
**Context:** Overnight, the autonomous agents (Grace/Linus) reverted the live store
toward a near-default Spotlight theme — the homepage lost its dark scrolling
marquee, hero carousel, trust/free-shipping bar and product grid. There was no
record of the change, so it could only be diagnosed by comparing the live store to
the local files. The products and their variants were NOT affected.
**Changed:**
- Re-applied `site.json` (v3) → live homepage via `apply_site_design` (main theme
  142662238279 "Spotlight"). Marquee, 7-image hero, trust pills and product grid
  are back.
- Re-applied `product.json` → live product page via `apply_product_design`.
- Fixed a crash in `src/org/heartbeat.py` (`_DEV_SYS.format` hit `KeyError '"file"'`
  from an unescaped `{` in the prompt) that was crash-looping every Grace turn.
- Authored the first `README.md` + this `CHANGELOG.md` so the store now has a
  source-of-truth record. From now on every change must be logged here.

## 2026-06-28 ~00:54 (Asia/Jerusalem) — [INCIDENT] Homepage reverted to near-default, unlogged
**By:** Grace/Linus (autonomous, unintended)
**Context:** The agents overwrote the live main theme's homepage, dropping the
approved premium sections. No changelog existed, so the change was invisible until
Itzik noticed in the morning. This incident is *why* this changelog now exists.
**Changed:** Live `templates/index.json` / home section reverted away from the
`site.json` v3 design (later restored — see entry above).

## 2026-06-27 (Asia/Jerusalem) — Color + Size variants from CJ (pipeline + backfill)
**By:** system (Itzik + Claude)
**Context:** Customers couldn't choose a color on multi-color products (e.g. the
Bamboo Baby Lounger Romper) — color exists in CJ's `variantKey` ("{Color}-{Size}")
but the pipeline only kept Size. Each variant must also bind to its exact CJ SKU so
the right color/size is fulfilled.
**Changed:**
- Sourcing/ecommerce/Shopify pipeline now emits a **Color** selector alongside
  Size for every new product, stamping each variant's SKU with its CJ vid so
  `cj_connect` binds the exact color/size.
- The ecommerce worker now **self-heals** older products each cycle (adds the Color
  selector + binds CJ SKUs), bounded per cycle. Manual tool:
  `backfill_product_color(shopify_product_id, store_id)`.
- Backfilled the live **Bamboo Baby Lounger Romper**: now 5 colors × 5 sizes = 25
  variants, each bound to its CJ SKU; removed the non-CJ "2-3Y" size that couldn't
  be fulfilled.
- `product.liquid` already renders the Color selector; no design change needed.
