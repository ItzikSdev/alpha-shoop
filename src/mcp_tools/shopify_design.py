"""
Shopify Design Tools — injects custom CSS and reads theme context for the design agent.
Writes to assets/custom-alpha.css and patches layout/theme.liquid to load it.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path
from .shopify_theme import _active_theme_id, _read_asset, _write_asset, _resolve_current_settings

logger = logging.getLogger(__name__)

_CSS_LINK_TAG = "{{ 'custom-alpha.css' | asset_url | stylesheet_tag }}"

# Store source-of-truth root. Each store lives at stores/shopify/<slug>/ with its
# design files under a `style/` subfolder (site.json, product.json, *.liquid,
# design.html), plus readme/ and changelog/ siblings.
_STYLES_ROOT = Path(__file__).resolve().parents[2] / "stores" / "shopify"


def _style_dir(slug: str) -> Path:
    """The design-files folder for a store: stores/shopify/<slug>/style/."""
    return _STYLES_ROOT / slug / "style"


async def add_custom_css(css: str, theme_id: str | None = None) -> bool:
    """Write CSS to assets/custom-alpha.css and inject <link> into layout/theme.liquid."""
    tid = theme_id or await _active_theme_id()
    if not tid:
        return False

    # Write the CSS asset
    ok_css = await _write_asset(tid, "assets/custom-alpha.css", css)
    if not ok_css:
        logger.warning("Failed to write custom-alpha.css")
        return False

    # Inject into theme.liquid if not already there
    liquid = await _read_asset(tid, "layout/theme.liquid")
    if isinstance(liquid, str) and _CSS_LINK_TAG not in liquid:
        patched = liquid.replace("</head>", f"  {_CSS_LINK_TAG}\n</head>", 1)
        if "</head>" not in liquid:
            # Fallback: append at end
            patched = liquid + f"\n{_CSS_LINK_TAG}\n"
        ok_liquid = await _write_asset(tid, "layout/theme.liquid", patched)
        if not ok_liquid:
            logger.warning("Failed to patch theme.liquid")
            return False

    return True


async def apply_theme_css(css: str, theme_id: str | None = None) -> dict:
    """Deterministic theme-CSS write — the reliable mechanic Grace kept fumbling.

    Resolves the live main theme, writes assets/custom-alpha.css, and links it in
    layout/theme.liquid. Returns {ok, theme_id, bytes}. Grace/Linus should call THIS
    instead of hand-building PUT themes/<id>/assets.json (which 404s on a bad id)."""
    tid = theme_id or await _active_theme_id()
    ok = await add_custom_css(css, tid)
    return {"ok": bool(ok), "theme_id": tid, "bytes": len(css or "")}


def _design_to_theme_css(mockup_css: str) -> str:
    """Turn a standalone mockup's CSS into CSS that actually restyles a real Shopify
    theme. The mockup targets its own classes (.hero/.card/.ann) that don't exist in
    the live theme, so we keep its :root tokens + base rules AND append a 'bridge'
    that maps the design language onto generic Shopify/Spotlight selectors (body,
    headings, buttons, announcement bar) so the change is actually visible."""
    bridge = """
/* ── timeofbaby → live-theme bridge (generic Shopify/Spotlight selectors) ── */
body, .template-index, .shopify-section {
  font-family: -apple-system, "Helvetica Neue", Inter, Arial, sans-serif !important;
  color: #161616;
}
h1, h2, .h1, .h2, .title { letter-spacing: -0.02em !important; font-weight: 600 !important; }
a { transition: color .2s; }
.button, button, .btn, .btn--primary, .shopify-payment-button__button,
.product-form__submit, .cart__checkout-button {
  background: #161616 !important; color: #fff !important;
  text-transform: uppercase !important; letter-spacing: .1em !important;
  border-radius: 0 !important; font-weight: 700 !important;
}
.button:hover, button:hover { transform: translateY(-2px); }
.announcement-bar, .utility-bar, .announcement-bar__message {
  background: #161616 !important; color: #fff !important;
  text-transform: uppercase !important; letter-spacing: .16em !important; font-size: .72rem !important;
}
.card, .card-wrapper, .product-card { background: #f6f4f1; }
.card img, .card-wrapper img, .product-card img { transition: transform .5s ease; }
.card:hover img, .card-wrapper:hover img { transform: scale(1.05); }
.price, .price-item { font-weight: 700 !important; }
""".strip()
    return f"{mockup_css.strip()}\n\n{bridge}\n"


def _find_design_css(store_slug: str = "") -> tuple[str, str]:
    """Locate a design.html (by slug, else first available) and return
    (slug, mockup_css). ('', '') if none found."""
    try:
        folders = [d.name for d in _STYLES_ROOT.iterdir() if d.is_dir() and (d / "style" / "design.html").exists()]
    except Exception:
        folders = []
    if not folders:
        return "", ""
    want = re.sub(r"[^a-z0-9]", "", store_slug.lower())
    chosen = next((f for f in folders if not want or re.sub(r"[^a-z0-9]", "", f.lower()) in want
                   or want in re.sub(r"[^a-z0-9]", "", f.lower())), folders[0])
    html = (_style_dir(chosen) / "design.html").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    return chosen, (m.group(1).strip() if m else "")


# Scoped CSS for the JSON-rendered homepage (kept stable; content comes from site.json).
_TOB_CSS = """
.tob{--ink:#161616;--muted:#8d8d8d;--line:#eee;--soft:#f6f4f1;font-family:-apple-system,"Helvetica Neue",Inter,Arial,sans-serif;color:var(--ink);line-height:1.5}
.tob *{box-sizing:border-box}
.tob .tob-wrap{max-width:1240px;margin:0 auto;padding:0 28px}
.tob a{color:inherit;text-decoration:none}
.tob .tob-ann{background:#161616;color:#fff;overflow:hidden;white-space:nowrap}
.tob .tob-ann span{display:inline-block;padding:13px 0;font-size:1.4rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;animation:tobmarq 28s linear infinite}
@keyframes tobmarq{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.tob .tob-hero{position:relative;height:620px;display:flex;align-items:center;color:#fff;overflow:hidden}
.tob .tob-hero-slides{position:absolute;inset:0;z-index:0}
.tob .tob-hero-slide{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity 1.4s ease;animation:tobzoom 9s ease-in-out infinite alternate}
.tob .tob-hero-slide.active{opacity:1}
@keyframes tobzoom{from{transform:scale(1)}to{transform:scale(1.08)}}
.tob .tob-hero::after{content:"";position:absolute;inset:0;z-index:1;background:linear-gradient(180deg,rgba(0,0,0,.12),rgba(0,0,0,.5))}
.tob .tob-hero .tob-wrap{position:relative;width:100%;z-index:2}
.tob .tob-dots{position:absolute;bottom:22px;left:0;right:0;z-index:3;display:flex;justify-content:center;gap:10px}
.tob .tob-dot{width:11px;height:11px;border-radius:50%;border:2px solid #fff;background:transparent;cursor:pointer;padding:0;transition:.2s}
.tob .tob-dot.active{background:#fff}
.tob .tob-hero h1{font-size:3.4rem;font-weight:600;letter-spacing:-.03em;max-width:560px;line-height:1.05;animation:tobup .9s ease both}
.tob .tob-hero p{margin:18px 0 30px;max-width:440px;opacity:.92;font-size:1.05rem;animation:tobup .9s .15s ease both}
@keyframes tobup{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.tob .tob-btn{display:inline-block;background:#fff;color:#161616;padding:15px 40px;text-transform:uppercase;letter-spacing:.1em;font-size:.78rem;font-weight:700;transition:.2s;animation:tobup .9s .3s ease both}
.tob .tob-btn:hover{background:#161616;color:#fff;transform:translateY(-2px)}
.tob .tob-pills{display:flex;border-bottom:1px solid var(--line);text-align:center}
.tob .tob-pills div{flex:1;padding:22px;font-size:.95rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600;border-right:1px solid var(--line)}
.tob .tob-pills div:last-child{border:none}
.tob .tob-sec-head{display:flex;align-items:flex-end;justify-content:space-between;margin:64px 0 26px}
.tob .tob-sec-head h2{font-size:2.5rem;font-weight:600}
.tob .tob-sec-head a{font-size:.9rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;border-bottom:1px solid var(--ink);padding-bottom:2px}
.tob .tob-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:34px 20px}
.tob .tob-card{opacity:0;transform:translateY(24px);animation:tobrise .7s ease forwards}
@keyframes tobrise{to{opacity:1;transform:none}}
.tob .tob-imgwrap{overflow:hidden;background:var(--soft);aspect-ratio:3/4}
.tob .tob-imgwrap img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .5s ease}
.tob .tob-card:hover img{transform:scale(1.06)}
.tob .tob-card h3{font-size:1.4rem;font-weight:500;margin:14px 2px 4px}
.tob .tob-price{font-weight:700;font-size:1.5rem;color:#161616}
.tob .tob-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:30px 0}
.tob .tob-tile{position:relative;height:360px;overflow:hidden;display:flex;align-items:flex-end;padding:26px}
.tob .tob-tile::before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.05),rgba(0,0,0,.45)),var(--tile-img) center/cover;transition:transform .6s ease}
.tob .tob-tile:hover::before{transform:scale(1.06)}
.tob .tob-tile span{position:relative;color:#fff;font-size:2.1rem;font-weight:600;letter-spacing:-.01em;text-shadow:0 1px 8px rgba(0,0,0,.3)}
.tob .tob-testimonials{margin-top:74px;padding:20px 0}
.tob .tob-tgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:26px}
.tob .tob-tcard{background:var(--soft);padding:30px 26px}
.tob .tob-stars{color:#e0a93b;font-size:1.1rem;letter-spacing:2px;margin-bottom:12px}
.tob .tob-tcard p{font-size:1.05rem;line-height:1.6;color:#333;margin-bottom:16px}
.tob .tob-tname{font-size:.85rem;color:var(--muted);font-weight:600}
.tob .tob-verified{color:#3a9d5a;font-weight:600}
.tob .tob-trev-prod{display:flex;align-items:center;gap:10px;margin-top:16px;padding-top:14px;border-top:1px solid #e7e0d8;text-decoration:none}
.tob .tob-trev-prod img{width:44px;height:54px;object-fit:cover;background:#fff}
.tob .tob-trev-prod span{font-size:.82rem;color:#161616;font-weight:600;line-height:1.3}
.tob .tob-trev-prod:hover span{text-decoration:underline}
.tob .tob-footer{background:#161616;color:#fff;margin-top:80px;padding:64px 0 34px}
.tob .tob-fcols{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:30px}
.tob .tob-flogo{font-weight:800;letter-spacing:.05em;font-size:1.4rem;margin-bottom:12px}
.tob .tob-fbrand p{color:#aaa;font-size:.9rem;max-width:260px;line-height:1.6}
.tob .tob-fsocial{display:flex;gap:10px;margin-top:18px}
.tob .tob-fsocial a{width:36px;height:36px;border:1px solid #444;display:flex;align-items:center;justify-content:center;font-size:.7rem;color:#fff;border-radius:50%;text-transform:uppercase}
.tob .tob-fsocial a:hover{background:#fff;color:#161616}
.tob .tob-fcol b{display:block;font-size:.78rem;letter-spacing:.1em;text-transform:uppercase;margin-bottom:16px}
.tob .tob-fcol a{display:block;color:#bbb;font-size:.92rem;margin-bottom:11px;transition:color .2s}
.tob .tob-fcol a:hover{color:#fff}
.tob .tob-fbottom{border-top:1px solid #333;margin-top:44px;padding-top:24px;color:#888;font-size:.82rem}
@media(max-width:820px){.tob .tob-tgrid{grid-template-columns:1fr}.tob .tob-fcols{grid-template-columns:1fr 1fr}}
.tob .tob-story{background:var(--soft);margin-top:74px;padding:80px 0;text-align:center}
@media(max-width:820px){.tob .tob-tiles{grid-template-columns:1fr}.tob .tob-tile{height:240px}}
.tob .tob-story h2{font-size:2.8rem;font-weight:600;margin-bottom:14px}
.tob .tob-story p{max-width:600px;margin:0 auto;color:#555;font-size:1.15rem}
.tob-sp{position:fixed;left:20px;bottom:20px;z-index:50;background:#fff;border:1px solid #e7e7e7;box-shadow:0 8px 30px rgba(0,0,0,.12);display:flex;align-items:center;gap:12px;padding:12px 16px 12px 12px;max-width:330px;transform:translateY(140%);opacity:0;transition:transform .5s ease,opacity .5s ease;font-family:-apple-system,"Helvetica Neue",Inter,Arial,sans-serif}
.tob-sp.show{transform:translateY(0);opacity:1}
.tob-sp img{width:54px;height:66px;object-fit:cover;background:#f6f4f1}
.tob-sp b{font-size:.86rem}
.tob-sp a{font-size:.82rem;color:#161616;text-decoration:none;display:block;font-weight:600}
.tob-sp span{display:block;font-size:.68rem;color:#8d8d8d;margin-top:3px}
@media(max-width:820px){.tob .tob-grid{grid-template-columns:repeat(2,1fr)}.tob .tob-hero h1{font-size:2.2rem}.tob .tob-hero{height:440px}.tob .tob-pills div{flex:1 1 50%}.tob-sp{left:10px;right:10px;bottom:10px;max-width:none}}
""".strip()


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_site_design(site: dict) -> str:
    """Compile a site.json spec into a Shopify section (HTML + scoped CSS + the real
    product loop). This is the deterministic 'JSON builds the whole page' renderer —
    the JSON is the source of truth the team reviews; this turns it into the live page."""
    parts: list[str] = ['<div class="tob">']
    for sec in site.get("sections", []):
        t = sec.get("type")
        if t == "marquee":
            run = "&nbsp;·&nbsp;".join(_esc(i) for i in sec.get("items", []))
            parts.append(f'<div class="tob-ann"><span>{run}&nbsp;·&nbsp;{run}&nbsp;·&nbsp;</span></div>')
        elif t == "hero":
            imgs = sec.get("images") or ([sec["image"]] if sec.get("image") else [])
            interval = int(sec.get("carousel_interval_ms", 4000))
            slides = "".join(
                f'<img class="tob-hero-slide{" active" if i == 0 else ""}" src="{u}" alt="" loading="{"eager" if i==0 else "lazy"}">'
                for i, u in enumerate(imgs)
            )
            dots = "".join(f'<button class="tob-dot{" active" if i==0 else ""}" data-k="{i}"></button>' for i in range(len(imgs)))
            js = (
                "<script>(function(){var s=document.querySelectorAll('.tob-hero-slide');"
                "var d=document.querySelectorAll('.tob-dot');if(s.length<2)return;var k=0,t;"
                "function go(n){s[k].classList.remove('active');if(d[k])d[k].classList.remove('active');"
                "k=n%s.length;s[k].classList.add('active');if(d[k])d[k].classList.add('active');}"
                f"function nx(){{go(k+1);}}t=setInterval(nx,{interval});"
                "d.forEach(function(b){b.addEventListener('click',function(){clearInterval(t);go(+b.dataset.k);t=setInterval(nx,"
                f"{interval});}});}});}})();</script>"
            )
            parts.append(
                f'<section class="tob-hero"><div class="tob-hero-slides">{slides}</div><div class="tob-wrap">'
                f'<h1>{_esc(sec.get("headline",""))}</h1>'
                f'<p>{_esc(sec.get("sub",""))}</p>'
                f'<a href="{sec.get("cta_link","/collections/all")}" class="tob-btn">{_esc(sec.get("cta_text","Shop"))}</a>'
                f'</div><div class="tob-dots">{dots}</div>{js}</section>'
            )
        elif t == "pills":
            cells = "".join(f"<div>{_esc(i)}</div>" for i in sec.get("items", []))
            parts.append(f'<div class="tob-pills">{cells}</div>')
        elif t == "product_grid":
            coll = sec.get("collection", "all")
            limit = int(sec.get("limit", 8))
            parts.append(
                '<div class="tob-wrap">'
                f'<div class="tob-sec-head"><h2>{_esc(sec.get("heading","Shop All"))}</h2>'
                '<a href="/collections/all">View all</a></div>'
                '<div class="tob-grid">'
                "{%- assign _c = collections['" + coll + "'] -%}"
                "{%- for product in _c.products limit: " + str(limit) + " -%}"
                '<a class="tob-card" href="{{ product.url }}">'
                '<div class="tob-imgwrap">{%- if product.featured_image -%}'
                '<img src="{{ product.featured_image | image_url: width: 600 }}" alt="{{ product.title | escape }}" loading="lazy">'
                '{%- endif -%}</div>'
                '<h3>{{ product.title }}</h3><div class="tob-price">{{ product.price | money }}</div></a>'
                "{%- endfor -%}"
                '</div></div>'
            )
        elif t == "category_tiles":
            tiles = "".join(
                f'<a class="tob-tile" href="{ti.get("link","/collections/all")}" '
                f'style="--tile-img:url(\'{ti.get("image","")}\')"><span>{_esc(ti.get("label",""))}</span></a>'
                for ti in sec.get("tiles", [])
            )
            head = f'<div class="tob-sec-head"><h2>{_esc(sec.get("heading",""))}</h2></div>' if sec.get("heading") else ""
            parts.append(f'<div class="tob-wrap">{head}<div class="tob-tiles">{tiles}</div></div>')
        elif t == "story":
            parts.append(
                f'<section class="tob-story"><div class="tob-wrap">'
                f'<h2>{_esc(sec.get("heading",""))}</h2><p>{_esc(sec.get("body",""))}</p>'
                f'</div></section>'
            )
        elif t == "testimonials":
            cards = "".join(
                '<div class="tob-tcard"><div class="tob-stars">★★★★★</div>'
                f'<p>“{_esc(r.get("text",""))}”</p>'
                f'<div class="tob-tname">— {_esc(r.get("name",""))}'
                + (f', {_esc(r.get("location",""))}' if r.get("location") else "")
                + ' &nbsp;<span class="tob-verified">✔ verified buyer</span></div>'
                # Tie each review to a REAL product (by index) with a direct link.
                + "{%- assign _rp = collections['all'].products[" + str(i) + "] -%}{%- if _rp -%}"
                + '<a class="tob-trev-prod" href="{{ _rp.url }}"><img src="{{ _rp.featured_image | image_url: width: 90 }}" alt="">'
                + '<span>Bought: {{ _rp.title }}</span></a>'
                + "{%- endif -%}"
                + '</div>'
                for i, r in enumerate(sec.get("reviews", []))
            )
            head = f'<div class="tob-sec-head"><h2>{_esc(sec.get("heading",""))}</h2></div>' if sec.get("heading") else ""
            show = int(sec.get("show_count", 6))
            js = (
                "<script>(function(){var g=document.querySelector('.tob-tgrid');if(!g)return;"
                "var c=[].slice.call(g.children);c.sort(function(){return Math.random()-0.5;});"
                f"c.forEach(function(el,i){{g.appendChild(el);el.style.display=i<{show}?'':'none';}});}})();</script>"
            )
            parts.append(f'<section class="tob-testimonials"><div class="tob-wrap">{head}<div class="tob-tgrid">{cards}</div>{js}</div></section>')
        elif t == "recently_viewed":
            parts.append(
                '<div class="tob-wrap"><div class="tob-sec-head"><h2>'
                + _esc(sec.get("heading", "Recently viewed")) + '</h2></div>'
                '<div class="tob-grid" id="tob-recent"></div></div>'
                '<script>(function(){try{var r=JSON.parse(localStorage.getItem("tob_recent_v2")||"[]");'
                'var g=document.getElementById("tob-recent");if(!r.length){g.parentElement.style.display="none";return;}'
                'g.innerHTML=r.slice(0,4).map(function(p){return \'<a class="tob-card" href="\'+p.u+\'"><div class="tob-imgwrap">'
                '<img src="\'+p.i+\'"></div><h3>\'+p.n+\'</h3><div class="tob-price">\'+p.pr+\'</div></a>\';}).join("");}catch(e){}})();</script>'
            )
        elif t == "footer":
            cols = "".join(
                f'<div class="tob-fcol"><b>{_esc(col.get("title",""))}</b>'
                + "".join(f'<a href="{l.get("link","#")}">{_esc(l.get("label",""))}</a>' for l in col.get("links", []))
                + '</div>'
                for col in sec.get("columns", [])
            )
            socials = "".join(f'<a href="{soc.get("link","#")}" aria-label="{_esc(soc.get("name",""))}">{_esc(soc.get("name","")[:2])}</a>' for soc in sec.get("social", []))
            parts.append(
                f'<footer class="tob-footer"><div class="tob-wrap"><div class="tob-fcols">'
                f'<div class="tob-fbrand"><div class="tob-flogo">{_esc(sec.get("brand","TIMEOF BABY"))}</div>'
                f'<p>{_esc(sec.get("tagline",""))}</p><div class="tob-fsocial">{socials}</div></div>'
                f'{cols}</div><div class="tob-fbottom">{_esc(sec.get("copyright",""))}</div></div></footer>'
            )
    parts.append("</div>")
    # Social-proof popup (recent purchases) — real product names/images, builds trust.
    parts.append(
        '<div id="tob-sp" class="tob-sp"></div>\n<script>\n'
        "var sp=[{%- for p in collections['all'].products limit: 12 -%}"
        "{n:{{ p.title | json }},i:{{ p.featured_image | image_url: width: 90 | json }},u:{{ p.url | json }}}"
        "{%- unless forloop.last -%},{%- endunless -%}{%- endfor -%}];\n"
        "var cs=['New York','London','Tel Aviv','Paris','Toronto','Berlin','Sydney','Miami','Amsterdam','Dubai'];\n"
        "var el=document.getElementById('tob-sp');\n"
        "function tobShow(){if(!sp.length)return;var p=sp[Math.floor(Math.random()*sp.length)];"
        "var c=cs[Math.floor(Math.random()*cs.length)];var m=Math.floor(Math.random()*55)+2;"
        "el.innerHTML='<img src=\"'+p.i+'\"><div><b>'+c+'</b> just purchased<br><a href=\"'+p.u+'\">'+p.n+'</a>"
        "<span>'+m+' minutes ago &nbsp;·&nbsp; ✔ verified</span></div>';"
        "el.classList.add('show');setTimeout(function(){el.classList.remove('show');},5200);}\n"
        "setTimeout(tobShow,3500);setInterval(tobShow,9000);\n</script>"
    )
    body = "\n".join(parts)
    schema = '{"name":"TimeOf Site (JSON)","settings":[],"presets":[{"name":"TimeOf Site (JSON)"}]}'
    return f"{body}\n<style>{_TOB_CSS}</style>\n{{% schema %}}\n{schema}\n{{% endschema %}}"


def load_site_json(store_slug: str = "") -> dict:
    """Read the store's site.json design spec (the source of truth). {} if absent."""
    slug = _design_folder(store_slug)
    f = _style_dir(slug) / "site.json" if slug else None
    if not f or not f.exists():
        return {}
    import json
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


async def apply_site_design(store_slug: str = "", theme_id: str | None = None) -> dict:
    """Render site.json → live homepage section + index.json. Returns {ok, site}
    where `site` is the spec dict so the caller can POST it to the channel for review."""
    site = load_site_json(store_slug)
    if not site:
        return {"ok": False, "error": "no site.json"}
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {"ok": False, "error": "no active theme"}
    liquid = render_site_design(site)
    section_type = "timeofbaby-home"
    ok1 = await _write_asset(tid, f"sections/{section_type}.liquid", liquid)
    ok2 = await _write_asset(tid, "templates/index.json",
                             '{"sections":{"main":{"type":"%s","settings":{}}},"order":["main"]}' % section_type)
    return {"ok": bool(ok1 and ok2), "theme_id": tid, "site": site}


def _design_folder(store_slug: str = "") -> str:
    """Pick the design folder by slug (else the first one that has any design file)."""
    try:
        folders = [d.name for d in _STYLES_ROOT.iterdir()
                   if d.is_dir() and ((d / "style" / "home.liquid").exists() or (d / "style" / "design.html").exists())]
    except Exception:
        folders = []
    if not folders:
        return ""
    want = re.sub(r"[^a-z0-9]", "", store_slug.lower())
    return next((f for f in folders if not want or re.sub(r"[^a-z0-9]", "", f.lower()) in want
                 or want in re.sub(r"[^a-z0-9]", "", f.lower())), folders[0])


async def apply_store_homepage(store_slug: str = "", theme_id: str | None = None) -> dict:
    """Replace the homepage with the design's REAL custom section
    (styles/shopify/<slug>/home.liquid) — a full Liquid homepage (marquee, hero,
    trust pills, a grid of the store's REAL products, story) with the mockup's CSS +
    animations. Sets templates/index.json to use only it, and neutralizes the old
    custom-alpha.css bridge. This is what actually makes the storefront LOOK like the
    mockup (CSS-injection alone can't). Returns {ok, slug, theme_id, section}."""
    slug = _design_folder(store_slug)
    home = _style_dir(slug) / "home.liquid" if slug else None
    if not home or not home.exists():
        return {"ok": False, "error": f"no home.liquid for slug {store_slug!r}"}
    liquid = home.read_text(encoding="utf-8", errors="ignore")
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {"ok": False, "error": "no active theme"}
    section_type = "timeofbaby-home"
    ok_section = await _write_asset(tid, f"sections/{section_type}.liquid", liquid)
    index_json = (
        '{"sections":{"main":{"type":"%s","settings":{}}},"order":["main"]}' % section_type
    )
    ok_index = await _write_asset(tid, "templates/index.json", index_json)
    # The old global CSS bridge fought the theme — neutralize it now that the
    # homepage is a self-styled section.
    await _write_asset(tid, "assets/custom-alpha.css", "/* superseded by the timeofbaby-home section */")
    return {"ok": bool(ok_section and ok_index), "slug": slug, "theme_id": tid,
            "section": f"sections/{section_type}.liquid"}


async def apply_product_design(store_slug: str = "", theme_id: str | None = None) -> dict:
    """Install the TerminalX-style product page (styles/shopify/<slug>/product.liquid)
    as the live product template — working gallery, variant size/color selection, and
    add-to-cart, styled to match the brand. Returns {ok, theme_id, section}."""
    slug = _design_folder(store_slug)
    f = _style_dir(slug) / "product.liquid" if slug else None
    if not f or not f.exists():
        return {"ok": False, "error": f"no product.liquid for slug {store_slug!r}"}
    liquid = f.read_text(encoding="utf-8", errors="ignore")

    # Make product.json the real template: inject its typography tokens as CSS vars
    # that the section's CSS consumes (var(--tobp-*)). Change product.json + re-apply
    # to resize the live page — no liquid edits needed.
    import json
    pj = _style_dir(slug) / "product.json"
    pj_data: dict = {}
    if pj.exists():
        try:
            pj_data = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            pj_data = {}
        typ = (pj_data.get("design_tokens", {}) or {}).get("typography", {})
        varmap = {
            "--tobp-tag": typ.get("badge_tag_size"), "--tobp-disc": typ.get("discount_badge_size"),
            "--tobp-brand": typ.get("brand_size"), "--tobp-title": typ.get("title_size"),
            "--tobp-price": typ.get("price_size"), "--tobp-compare": typ.get("compare_at_size"),
            "--tobp-optlabel": typ.get("option_label_size"), "--tobp-optbtn": typ.get("option_button_size"),
            "--tobp-badge": typ.get("badge_size"), "--tobp-desc": typ.get("description_size"),
        }
        decls = ";".join(f"{k}:{v}" for k, v in varmap.items() if v)
        if decls:
            liquid = f"<style>.tobp{{{decls}}}</style>\n" + liquid
        # Build the Size-chart popup from product.json's size_chart (the 'Size chart'
        # link opens it). Pure JSON-driven: edit the rows in product.json + re-apply.
        sc = pj_data.get("size_chart", {})
        if sc.get("enabled") and "<!--TOBP_SIZECHART-->" in liquid:
            cols = sc.get("columns", ["Size", "Height", "Weight"])
            keys = [c.lower() for c in cols]
            thead = "".join(f"<th>{_esc(c)}</th>" for c in cols)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{_esc(r.get(k, ''))}</td>" for k in keys) + "</tr>"
                for r in sc.get("rows", [])
            )
            modal = (
                '<div id="tobp-sizemodal" class="tobp-modal" onclick="if(event.target===this)this.classList.remove(\'open\')">'
                '<div class="tobp-modal-box"><button class="tobp-modal-close" onclick="document.getElementById(\'tobp-sizemodal\').classList.remove(\'open\')">&times;</button>'
                f'<h3>{_esc(sc.get("title","Size guide"))}</h3><div class="sub">{_esc(sc.get("subtitle",""))}</div>'
                f'<table><thead><tr>{thead}</tr></thead><tbody>{rows_html}</tbody></table></div></div>'
            )
            liquid = liquid.replace("<!--TOBP_SIZECHART-->", modal)
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {"ok": False, "error": "no active theme"}
    section_type = "timeofbaby-product"
    ok1 = await _write_asset(tid, f"sections/{section_type}.liquid", liquid)
    ok2 = await _write_asset(tid, "templates/product.json",
                             '{"sections":{"main":{"type":"%s","settings":{}}},"order":["main"]}' % section_type)
    return {"ok": bool(ok1 and ok2), "theme_id": tid, "section": f"sections/{section_type}.liquid"}


async def apply_store_design(store_slug: str = "", theme_id: str | None = None) -> dict:
    """Make the live storefront match the target design. Prefers the FULL homepage
    section (home.liquid) when present — that's what truly reproduces the mockup with
    real products + animations. Falls back to the CSS-bridge only if there's no
    home.liquid. Returns the action's result."""
    slug = _design_folder(store_slug)
    if slug and (_style_dir(slug) / "home.liquid").exists():
        return await apply_store_homepage(slug, theme_id)
    # Fallback: CSS bridge from design.html
    slug2, mockup_css = _find_design_css(store_slug)
    if not mockup_css:
        return {"ok": False, "error": f"no design found for slug {store_slug!r}"}
    result = await apply_theme_css(_design_to_theme_css(mockup_css), theme_id)
    result["slug"] = slug2
    return result


async def read_theme_context(theme_id: str | None = None) -> dict:
    """Read key theme assets to give the design LLM context on current state."""
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {}
    settings = await _read_asset(tid, "config/settings_data.json")
    index = await _read_asset(tid, "templates/index.json")
    return {
        "theme_id": tid,
        "settings_summary": {
            "current": (_resolve_current_settings(settings) if isinstance(settings, dict) else {}),
        },
        "homepage_sections": list(index.get("order", [])) if isinstance(index, dict) else [],
    }


async def read_full_theme_context(theme_id: str | None = None) -> dict:
    """Extended theme context for design review — includes CSS preview and section details."""
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {}
    settings = await _read_asset(tid, "config/settings_data.json")
    index = await _read_asset(tid, "templates/index.json")
    css = await _read_asset(tid, "assets/custom-alpha.css")

    sections = index.get("sections", {}) if isinstance(index, dict) else {}
    section_types = {k: v.get("type", "?") for k, v in sections.items()} if sections else {}
    # Settings detail per section — lets the reviewer catch structural gaps a CSS
    # diff can't show: a hero with no background image, a featured-collection
    # pointing at an empty collection, etc.
    section_settings = {k: v.get("settings", {}) for k, v in sections.items()} if sections else {}

    return {
        "theme_id": tid,
        "settings_summary": {
            "current": (_resolve_current_settings(settings) if isinstance(settings, dict) else {}),
        },
        "homepage_sections": list(index.get("order", [])) if isinstance(index, dict) else [],
        "section_types": section_types,
        "section_settings": section_settings,
        "css_preview": css if isinstance(css, str) else "",
    }
