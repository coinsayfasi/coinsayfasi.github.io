#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apps.tabserve.com.tr blog yazılarını Pinterest'e pinler (profesyonel dikey görsel + SEO açıklama + link).
Mevcut Pinterest altyapısını (pin_image, pinterest_api, secrets) kullanır. Dedup state.
Env: PINTEREST_APP_ID/SECRET/REFRESH_TOKEN, PEXELS_API_KEY. Yoksa DRY-RUN."""
import os, re, json, html, urllib.request
from pathlib import Path
from pin_image import build_pin_image, fetch_pexels_photo
from pinterest_api import PinterestClient, refresh_access_token

HERE = Path(__file__).resolve().parent
STATE = HERE / "blog_pins_state.json"
SITEMAP = "https://apps.tabserve.com.tr/sitemap.xml"
MAX_PER_RUN = int(os.environ.get("BLOG_PINS_PER_RUN", "2"))
esc = html.unescape

APP_CFG = {
    "onebag":   {"board": "Travel Packing Tips",       "bdesc": "Smart packing guides — pack light, travel better.", "cta": "Read the guide", "pexels": "travel suitcase packing"},
    "routevia": {"board": "Türkiye Gezilecek Yerler",  "bdesc": "Türkiye gezi rehberleri ve rotalar.",               "cta": "Keşfet",         "pexels": "turkey travel landscape"},
    "rentflow": {"board": "Landlord & Rental Tips",    "bdesc": "Practical guides for landlords and rentals.",       "cta": "Read the guide", "pexels": "apartment house keys"},
}

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tabserve-blogpin/1.0"}), timeout=25).read().decode("utf-8", "ignore")

def blog_urls():
    try:
        xml = fetch(SITEMAP)
        return [u for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml)
                if "/blog/" in u and u.rstrip("/").split("/blog/")[-1].strip("/")]  # /blog/ index hariç, slug olanlar
    except Exception as e:
        print(f"sitemap alınamadı: {e}"); return []

def meta(h, *pats):
    for p in pats:
        m = re.search(p, h, re.I | re.S)
        if m: return esc(re.sub(r"\s+", " ", m.group(1)).strip())
    return ""

def detect_app(h):
    if "coinsayfasi.github.io/onebag/" in h: return "onebag"
    if "coinsayfasi.github.io/routevia-app/" in h: return "routevia"
    if "coinsayfasi.github.io/rentflow/" in h: return "rentflow"
    return "onebag"

def bullets(h, n=3):
    out = []
    for m in re.findall(r"<h2[^>]*>(.*?)</h2>", h, re.S):
        t = re.sub(r"<[^>]+>", "", m).strip()
        if 4 <= len(t) <= 42: out.append(t)
        if len(out) >= n: break
    return out

def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {"pinned": []}
    pinned = set(state.get("pinned", []))
    urls = [u for u in blog_urls() if u not in pinned]
    if not urls:
        print("yeni blog yazısı yok"); return
    app_id, secret, rt = (os.environ.get("PINTEREST_APP_ID"), os.environ.get("PINTEREST_APP_SECRET"), os.environ.get("PINTEREST_REFRESH_TOKEN"))
    pexels = os.environ.get("PEXELS_API_KEY", "")
    dry = not (app_id and secret and rt)
    client = None; boards = {}
    if not dry:
        client = PinterestClient(refresh_access_token(app_id, secret, rt))
    made = 0
    for url in urls:
        if made >= MAX_PER_RUN: break
        try:
            h = fetch(url)
        except Exception as e:
            print(f"  {url} alınamadı: {e}"); continue
        title = meta(h, r'og:title["\']\s+content=["\'](.*?)["\']', r"<title>(.*?)</title>").split(" | ")[0]
        desc = meta(h, r'og:description["\']\s+content=["\'](.*?)["\']', r'name=["\']description["\']\s+content=["\'](.*?)["\']')
        app = detect_app(h); cfg = APP_CFG[app]
        bl = bullets(h)
        photo = fetch_pexels_photo(cfg["pexels"], pexels) if pexels else None
        img = build_pin_image(title, app, subtitle=cfg["cta"], photo=photo, bullets=bl)
        tags = {"onebag": "#travel #packing #traveltips", "routevia": "#türkiye #gezi #seyahat", "rentflow": "#landlord #realestate #property"}[app]
        pin_desc = f"{desc} {tags}"[:480]
        print(f"\n• [{app}] {title}\n  board: {cfg['board']}")
        if dry:
            (HERE / f"preview-blog-{app}-{made}.png").write_bytes(img); print("  (DRY-RUN: önizleme yazıldı)")
        else:
            if cfg["board"] not in boards:
                boards[cfg["board"]] = client.ensure_board(cfg["board"], cfg["bdesc"])
            pid = client.create_pin(boards[cfg["board"]], title, pin_desc, url, img, alt_text=title)
            print(f"  ✓ pinlendi: {pid}")
        pinned.add(url); made += 1
    state["pinned"] = list(pinned)[-2000:]
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    print(f"\n✓ {made} blog pini")

if __name__ == "__main__":
    main()
