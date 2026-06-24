#!/usr/bin/env python3
"""SEO sayfalarından Google Web Story (AMP) üretici — 3 app, benzersiz, telif-güvenli.

make_short.py temalarını yeniden kullanır ama VİDEO yerine AMP web story HTML üretir.
Görseller uzak URL (Wikimedia lisans-doğrulanmış / Pexels) → amp-img layout=fill (indirme yok).
Çıktı: web-stories/<app>/<slug>/index.html. Google Discover/Arama'da görünür.

Kullanım:
  page <index.html> <out_dir_slug>
  app  <routevia|onebag|rentflow> <out_dir_slug>
Env: PEXELS_API_KEY (ops).
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

import make_short as ms   # THEMES, extract_points, place_of, _commons_license, UA, GO, REPO_ROOT

REPO_ROOT = ms.REPO_ROOT
STORIES_DIR = REPO_ROOT / "web-stories"
ASSETS = REPO_ROOT / "assets"
BASE = "https://coinsayfasi.github.io"
GA4 = "G-EDZWXP6EEG"                              # site geneli GA4 (go/ sayfalarıyla aynı)
INDEXNOW_KEY = "6b2c33a8ee47462a9c217f29a99ada33"  # site-geneli IndexNow anahtarı (/<key>.txt kökte)

# Web Story analytics (GA4/gtag) — görüntülenme, tamamlanma ve CTA(İndir) tıklaması
ANALYTICS = (
    '<amp-analytics type="gtag" data-credentials="include"><script type="application/json">'
    '{"vars":{"gtag_id":"%s","config":{"%s":{"groups":"default"}}},'
    '"triggers":{'
    '"sPage":{"on":"story-page-visible","vars":{"event_name":"story_page_view"}},'
    '"sEnd":{"on":"story-last-page-visible","vars":{"event_name":"story_complete"}},'
    '"sCta":{"on":"story-page-attachment-enter","vars":{"event_name":"story_cta_open"}}'
    '}}</script></amp-analytics>'
) % (GA4, GA4)


def wiki_image_url(query, size=1200):
    """Telif-doğrulanmış Wikipedia görsel URL'si + atıf. (img indirmez, URL döner)"""
    for lang in ("tr", "en"):
        try:
            r = requests.get(f"https://{lang}.wikipedia.org/w/api.php",
                             params={"action": "query", "titles": query, "prop": "pageimages",
                                     "pithumbsize": size, "format": "json", "redirects": 1},
                             headers=ms.UA, timeout=15)
            for p in r.json().get("query", {}).get("pages", {}).values():
                fname, src = p.get("pageimage"), p.get("thumbnail", {}).get("source")
                if fname and src:
                    attr = ms._commons_license(fname)
                    if attr:
                        return src, attr
        except Exception as e:
            print(f"[wiki] {query} ({lang}): {e}")
    return None, None


def pexels_image_url(query):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None, None
    try:
        import random
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait", "per_page": 15}, timeout=15)
        photos = r.json().get("photos", [])
        if photos:
            ph = random.choice(photos)
            return ph["src"].get("portrait"), f"{ph.get('photographer','')} (Pexels)"
    except Exception as e:
        print(f"[pexels] {query}: {e}")
    return None, None


def get_img(theme, point, place):
    if theme["img"] == "wiki":
        for q in (point, f"{point} {place}"):
            u, a = wiki_image_url(q)
            if u:
                return u, a
        return pexels_image_url(f"{place} turkey")
    q = point if theme["match"].startswith("/rentflow") else f"{place} {point}"
    u, a = pexels_image_url(q)
    return (u, a) if u else pexels_image_url(place)


def publisher_logo(theme) -> str:
    """Kare marka logosu üret (amp-story publisher-logo-src zorunlu). Döner: site-relative path."""
    ASSETS.mkdir(exist_ok=True)
    app = theme["label"].lower()
    p = ASSETS / f"storylogo_{app}.png"
    if not p.exists():
        img = Image.new("RGB", (192, 192), theme["brand"])
        d = ImageDraw.Draw(img)
        try:
            f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 90)
        except Exception:
            try:
                f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
            except Exception:
                f = ImageFont.load_default()
        ch = theme["label"][0]
        w = d.textlength(ch, font=f)
        d.text(((192 - w) / 2, 45), ch, font=f, fill=theme["accent"])
        img.save(p)
    return f"/assets/storylogo_{app}.png"


def esc(s):
    return _html.escape(str(s), quote=True)


def page_html(img_url, attr, title_html, sub_html=""):
    overlay = (f'<amp-story-grid-layer template="vertical" class="bottom">'
               f'<div class="wrap">{title_html}{sub_html}</div></amp-story-grid-layer>')
    credit = f'<div class="credit">{esc(attr)}</div>' if attr else ""
    return (f'<amp-story-page id="p{abs(hash(title_html)) % 99999}">'
            f'<amp-story-grid-layer template="fill">'
            f'<amp-img src="{esc(img_url)}" layout="fill"></amp-img></amp-story-grid-layer>'
            f'<amp-story-grid-layer template="fill"><div class="shade"></div></amp-story-grid-layer>'
            f'{overlay}{credit}</amp-story-page>')


def build_story(theme, page_path, slug, source_url):
    htmlstr = Path(page_path).read_text(encoding="utf-8", errors="ignore")
    place = ms.place_of(theme, htmlstr)
    points = ms.extract_points(htmlstr, theme["heading"], 7)
    if len(points) < 3:
        raise SystemExit("Yetersiz içerik")
    print(f"[{theme['label']}] {place} | {points}")
    acc = "#%02x%02x%02x" % theme["accent"]
    brand = "#%02x%02x%02x" % theme["brand"]
    logo = publisher_logo(theme)
    canonical = f"{BASE}/web-stories/{theme['label'].lower()}/{slug}/"

    pages, attrs = [], []
    # kapak
    cu, ca = get_img(theme, place, place)
    if ca: attrs.append(ca)
    poster = cu or ""
    n = len(points)
    cover_title = theme["title"].format(place=place, n=n).replace(" #shorts", "")
    pages.append(page_html(cu or "", ca,
                           f'<div class="brand">{esc(theme["label"])}</div><h1>{esc(place)}</h1>',
                           f'<p>{esc(theme["intro_sub"].format(n=n))}</p>'))
    # noktalar
    for i, name in enumerate(points, 1):
        iu, ia = get_img(theme, name, place)
        if ia: attrs.append(ia)
        pages.append(page_html(iu or cu or "", ia,
                               f'<div class="num">{i}</div><h2>{esc(name)}</h2>'))
    # CTA
    store = theme["store"]
    pages.append(
        f'<amp-story-page id="cta"><amp-story-grid-layer template="fill">'
        f'<div class="ctabg"></div></amp-story-grid-layer>'
        f'<amp-story-grid-layer template="vertical" class="center">'
        f'<div class="wrap"><h2>{esc(theme["cta_card"].replace(chr(10)," "))}</h2>'
        f'<p>{esc(theme["cta_sub"])}</p></div></amp-story-grid-layer>'
        f'<amp-story-page-attachment layout="nodisplay" cta-text="İndir" '
        f'href="{esc(store)}"></amp-story-page-attachment></amp-story-page>')

    css = f"""
*{{box-sizing:border-box}} amp-story{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif}}
.shade{{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.15),rgba(0,0,0,.75))}}
.ctabg{{position:absolute;inset:0;background:linear-gradient(160deg,{brand},#05060c)}}
.bottom{{align-content:end;padding:0 32px 90px}} .center{{align-content:center;padding:0 36px}}
.wrap{{color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.6)}}
.brand{{color:{acc};font-weight:800;letter-spacing:2px;font-size:20px;margin-bottom:8px}}
h1{{font-size:48px;margin:0;font-weight:800}} h2{{font-size:40px;margin:8px 0;font-weight:800}}
p{{font-size:22px;color:{acc};font-weight:700;margin:10px 0 0}}
.num{{width:64px;height:64px;border:4px solid {acc};border-radius:50%;color:{acc};
  font-size:34px;font-weight:800;display:flex;align-items:center;justify-content:center}}
.credit{{position:absolute;bottom:8px;left:10px;right:10px;color:#fff;opacity:.5;font-size:11px}}
""".strip()

    doc = f"""<!doctype html>
<html ⚡ lang="{theme['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1">
<link rel="canonical" href="{canonical}">
<title>{esc(cover_title)}</title>
<meta name="description" content="{esc(theme['desc_head'].format(place=place, n=n))}">
<script async src="https://cdn.ampproject.org/v0.js"></script>
<script async custom-element="amp-story" src="https://cdn.ampproject.org/v0/amp-story-1.0.js"></script>
<script async custom-element="amp-story-page-attachment" src="https://cdn.ampproject.org/v0/amp-story-page-attachment-0.1.js"></script>
<script async custom-element="amp-analytics" src="https://cdn.ampproject.org/v0/amp-analytics-0.1.js"></script>
<style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>
<style amp-custom>{css}</style>
</head>
<body>
<amp-story standalone title="{esc(cover_title)}" publisher="{esc(theme['label'].title())}"
  publisher-logo-src="{BASE}{logo}" poster-portrait-src="{esc(poster)}">
{ANALYTICS}
{''.join(pages)}
</amp-story>
</body></html>"""

    out_dir = STORIES_DIR / theme["label"].lower() / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(doc, encoding="utf-8")
    print(f"✓ Web Story: {out_dir/'index.html'}\n  canonical: {canonical}")
    print(f"  görseller (atıf): {list(dict.fromkeys(attrs))}")
    return canonical


def add_to_sitemap(url):
    """Web story URL'sini ana sitemap.xml'e ekle (yoksa) → Google bulsun."""
    import datetime
    sm = REPO_ROOT / "sitemap.xml"
    txt = sm.read_text(encoding="utf-8")
    if url in txt:
        return
    today = datetime.date.today().isoformat()
    entry = f"  <url><loc>{url}</loc><lastmod>{today}</lastmod></url>\n"
    txt = txt.replace("</urlset>", entry + "</urlset>")
    sm.write_text(txt, encoding="utf-8")
    print(f"  + sitemap'e eklendi: {url}")


def rebuild_hub():
    """Tüm web story'leri tarayıp /stories/ hub sayfası üretir → orphan biter, iç link + insan trafiği.
    Normal (AMP olmayan) HTML; GA4 + CollectionPage schema içerir. Döner: hub URL'si."""
    rows = []
    for idx in STORIES_DIR.glob("*/*/index.html"):
        t = idx.read_text(encoding="utf-8", errors="ignore")
        mt = re.search(r"<title>(.*?)</title>", t, re.S)
        mc = re.search(r'rel="canonical" href="([^"]+)"', t)
        mp = re.search(r'poster-portrait-src="([^"]+)"', t)
        if not (mt and mc):
            continue
        rows.append((idx.stat().st_mtime, _html.unescape(mt.group(1).strip()),
                     mc.group(1), mp.group(1) if mp else "", idx.parent.parent.name))
    if not rows:
        return None
    rows.sort(reverse=True)  # en yeni üstte
    cards = "\n".join(
        f'<a class="c" href="{esc(u)}">'
        + (f'<img loading="lazy" src="{esc(po)}" alt="{esc(ti)}">' if po else '<span class="ph"></span>')
        + f'<span class="ap">{esc(app.title())}</span><span class="t">{esc(ti)}</span></a>'
        for _, ti, u, po, app in rows)
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "Web Stories — OneBag · Routevia · RentFlow", "url": f"{BASE}/stories/",
        "hasPart": [{"@type": "ListItem", "position": i + 1, "url": u}
                    for i, (_, _, u, _, _) in enumerate(rows)],
    }, ensure_ascii=False)
    doc = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Web Stories — OneBag, Routevia, RentFlow | Tabserve</title>
<meta name="description" content="Seyahat, gezi ve kiralama uygulamalarımızdan kısa, görsel Web Stories. Pratik ipuçları, gezilecek yerler, bavul listeleri.">
<link rel="canonical" href="{BASE}/stories/">
<meta property="og:title" content="Web Stories — OneBag, Routevia, RentFlow">
<meta property="og:type" content="website">
<meta property="og:url" content="{BASE}/stories/">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4}');</script>
<script type="application/ld+json">{ld}</script>
<style>
:root{{--bg:#0a0b12;--card:#141622;--acc:#7c5cff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:#fff;font:16px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
header{{padding:48px 20px 16px;text-align:center}}h1{{margin:0 0 6px;font-size:30px}}header p{{margin:0;opacity:.7}}
.grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));max-width:1100px;margin:24px auto;padding:0 16px}}
.c{{position:relative;display:block;aspect-ratio:3/5;border-radius:14px;overflow:hidden;background:var(--card);text-decoration:none;color:#fff;box-shadow:0 6px 20px rgba(0,0,0,.35)}}
.c img,.c .ph{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.c .ph{{background:linear-gradient(160deg,#2a2350,#05060c)}}
.c::after{{content:"";position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.82),transparent 55%)}}
.c .ap{{position:absolute;top:10px;left:10px;z-index:2;font-size:11px;font-weight:800;letter-spacing:1px;color:var(--acc);background:rgba(0,0,0,.45);padding:3px 8px;border-radius:20px}}
.c .t{{position:absolute;left:12px;right:12px;bottom:12px;z-index:2;font-size:14px;font-weight:700;text-shadow:0 2px 6px rgba(0,0,0,.7)}}
footer{{text-align:center;padding:28px 16px 48px;opacity:.7}}footer a{{color:var(--acc)}}
</style>
</head>
<body>
<header><h1>Web Stories</h1><p>{len(rows)} hikâye · OneBag · Routevia · RentFlow</p></header>
<main class="grid">
{cards}
</main>
<footer><a href="/">← Ana sayfa</a></footer>
</body></html>"""
    out = REPO_ROOT / "stories"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(doc, encoding="utf-8")
    print(f"✓ Story hub: {len(rows)} story → {BASE}/stories/")
    return f"{BASE}/stories/"


def indexnow_ping(urls):
    """Yeni/değişen URL'leri IndexNow'a bildir (Bing, Yandex, Seznam anında tarar). Google IndexNow
    kullanmaz → Google için sitemap + iç link + GSC 'İndeksleme İste' geçerlidir."""
    urls = [u for u in dict.fromkeys(urls) if u]
    if not urls:
        return
    try:
        r = requests.post("https://api.indexnow.org/indexnow",
                          json={"host": "coinsayfasi.github.io", "key": INDEXNOW_KEY,
                                "keyLocation": f"{BASE}/{INDEXNOW_KEY}.txt", "urlList": urls},
                          headers={"Content-Type": "application/json"}, timeout=20)
        print(f"  IndexNow ping: HTTP {r.status_code} ({len(urls)} url)")
    except Exception as e:
        print(f"  IndexNow hata (atlandı): {e}")


def main():
    ms.STATE = ms.HERE / "webstory_state.json"   # Shorts'tan AYRI dedup (_automation/shorts/)
    mode, arg, slug = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "app":
        theme = ms.THEMES[arg]
        url = ms.pick_page(arg)
        # slug = sayfa URL'sinin son anlamlı parçalarından (çakışma olmasın)
        parts = [p for p in re.sub(r"^https?://[^/]+/", "", url).strip("/").split("/") if p]
        slug = "-".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")[:60]
        canonical = build_story(theme, ms.url_to_local(url), slug, url)
        ms.mark_used(url)
        add_to_sitemap(canonical)
    else:
        page = Path(arg)
        theme = ms.theme_for_path(page)
        canonical = build_story(theme, page, slug, "")
        add_to_sitemap(canonical)

    # Hub'ı yeniden üret (orphan'ı bitir) + sitemap'e ekle + IndexNow'a bildir
    hub = rebuild_hub()
    if hub:
        add_to_sitemap(hub)
    indexnow_ping([canonical, hub, f"{BASE}/", f"{BASE}/sitemap.xml"])


if __name__ == "__main__":
    main()
