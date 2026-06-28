# TIMEOF BABY — Store Source of Truth

> **קצר בעברית:** התיקייה הזאת היא **מקור-האמת** של חנות TIMEOF BABY. כל מה
> שרואים בחנות החיה נבנה מהקבצים כאן. **אסור** לשנות את החנות בלי לערוך את הקבצים
> כאן, ו**חובה** לרשום כל שינוי ב-`CHANGELOG.md`. לפני שמשנים — קוראים את הקובץ
> הזה ואת ה-CHANGELOG.

This folder **is** the TIMEOF BABY storefront. The live Shopify store is *rendered
from* these files — they are the single source of truth. If it isn't represented
here, it isn't real, and it will be overwritten on the next render.

**Read this file and `CHANGELOG.md` before you touch the store.** Then log what you
did. This is how anyone (Itzik, Linus, Grace) can know what happened to the store
and recover it. We lost the premium homepage once because a change was made with no
record — never again.

---

## Folder layout

```text
stores/shopify/timeofbaby.alpha-tech.live/
├── style/        ← the design files (edit these): site.json, product.json,
│                   product.liquid, home.liquid, design.html
├── readme/       ← this README.md (the rules)
└── changelog/    ← CHANGELOG.md (every change, newest on top)
```

The design files all live under **`style/`**. The render tools resolve this folder
automatically — reference files by name (e.g. `site.json`) or by the relative path
`shopify/timeofbaby.alpha-tech.live/style/site.json`.

---

## The files in `style/` (and what each one becomes live)

| File | What it is | Renders to (live Shopify) |
|------|------------|---------------------------|
| `site.json` | **Homepage spec** — the single source of truth for the homepage. Sections: dark scrolling marquee, 7-image hero carousel, category tiles, product grid, social-proof. | `sections/timeofbaby-home.liquid` + `templates/index.json`, via `apply_site_design`. |
| `product.json` | **Product-page spec** — typography tokens (drive the live font sizes), size-chart rows, badges. | injected into `sections/timeofbaby-product.liquid` via `apply_product_design`. |
| `product.liquid` | The product-page section markup (gallery, **Color + Size** selectors, add-to-cart). Edit `product.json` to restyle; only touch this for structural markup. | `sections/timeofbaby-product.liquid`. |
| `home.liquid` | Hand-written full homepage section (reference/fallback). The live homepage normally comes from `site.json`, not this. | `sections/timeofbaby-home.liquid` (only via `apply_store_homepage`). |
| `design.html` | The approved visual mockup — the target look the live theme must match. | nothing (reference only). |
| `CHANGELOG.md` | **Append one entry for every change.** Newest on top. | nothing (the record). |

The live **main theme** is resolved automatically (`_active_theme_id`). You never
need a theme id or a raw asset PUT — the `apply_*` tools resolve everything.

---

## The golden rules

1. **These JSON files are the source of truth.** To change the homepage, edit
   `site.json` and run `apply_site_design`. To change the product page, edit
   `product.json` and run `apply_product_design`. **Never** hand-edit the live
   `.liquid` on Shopify — the next render wipes it.
2. **Read before you write.** Open this README + the top of `CHANGELOG.md` so you
   know the current intended design and recent history before changing anything.
3. **Log every change** in `CHANGELOG.md` (format below) — title, timestamp
   (Asia/Jerusalem), who, context (why), and exactly what changed.
4. **Don't redo what's already done.** Color+Size variants, 7-image hero, free
   shipping, social-proof, real CJ descriptions are all live. The real lever to
   revenue is **traffic (ads)**, not redesign loops.
5. **Don't revert the approved design.** `design.html` + `site.json` v3 are the
   approved look. If the live store ever doesn't match, re-apply — don't redesign
   from scratch.

---

## How to change the design (the only correct way)

```text
1. Read README.md + CHANGELOG.md (top entries).
2. Edit the JSON value(s) in site.json / product.json.
3. apply_site_design()  (homepage)   or   apply_product_design()  (product page).
4. Add a CHANGELOG.md entry describing the change.
```

## CHANGELOG entry format

```markdown
## YYYY-MM-DD HH:MM (Asia/Jerusalem) — <short title>
**By:** <Grace | Linus | Itzik | system>
**Context:** <why this change — one or two lines>
**Changed:** <exactly what changed: which file/section/field, old → new>
```

Newest entry goes at the **top**. One entry per change. If you applied a design
without editing a file (just re-rendered), say so.
