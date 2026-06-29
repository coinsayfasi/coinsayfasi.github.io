#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bluesky otomatik paylaşım — 3 app (Routevia TR, OneBag/RentFlow EN).
Her gün sitemap'ten kanonik (çok-dilli HARİÇ, hub HARİÇ) sayfa seçer; sayfaya/ülkeye özel
ZENGİN içerik + SEO etiketleri (clickable #hashtag facet) + GÖRSEL link kartı (external embed,
algoritma görünürlüğü) + akıllı sayfa linki (store CTA'lı). Dedup state. App password (secret).
Env: BLUESKY_IDENTIFIER, BLUESKY_PASSWORD, BSKY_APPS (ops, 'onebag routevia rentflow')."""
import os, re, json, html, datetime, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SITEMAP = ROOT / "sitemap.xml"
STATE = HERE / "state.json"
BASE = "https://coinsayfasi.github.io"
PDS = "https://bsky.social"
esc = html.unescape

# match prefix -> (app, lang, hook, hashtags)
# Sadece İÇERİK-ZENGİNİ kümeler (her post dolu olsun) — baggage/calculators madde-fakiri, dışarıda.
THEMES = [
    ("/onebag/packing-list/", "onebag", "en", "🧳 What to pack for {place}", "#travel #packing #traveltips #carryon #onebag"),
    ("/routevia-app/gezilecek-yerler/", "routevia", "tr", "🚗 {place} gezilecek yerler", "#türkiye #gezi #tatil #seyahat #gezilecekyerler"),
    ("/rentflow/guides/", "rentflow", "en", "🏠 {place}", "#landlord #realestate #rental #property #rentflow"),
]
APP_LANG = {"onebag": "en", "routevia": "tr", "rentflow": "en"}


def sitemap_urls():
    urls = re.findall(r"<loc>\s*(.*?)\s*</loc>", SITEMAP.read_text(encoding="utf-8"))
    return [u for u in urls if not re.search(r"://[^/]+/(de|es|fr)/", u)]  # sadece kanonik (TR/EN)


def local_path(url):
    p = re.sub(r"^https?://[^/]+/", "", url).rstrip("/")
    return ROOT / (p + "/index.html" if p else "index.html")


def meta(htmls, *pats):
    for p in pats:
        m = re.search(p, htmls, re.I | re.S)
        if m:
            return esc(re.sub(r"\s+", " ", m.group(1)).strip())
    return ""


def place_of(theme, htmls, title):
    if theme[1] == "routevia":
        return re.split(r"\s+Gezilecek", title)[0].strip()
    if "/packing-list/" in theme[0]:
        m = re.search(r"(?:What to Pack for|Pack for)\s+(.+?)\s*(?:[—\-(|]|$)", title, re.I)
        return m.group(1).strip() if m else re.split(r"\s*[|—-]", title)[0].strip()
    return re.split(r"\s*[|—]", title)[0].strip()


def extract_items(match, htmls, n=3):
    def clean(t):
        t = esc(re.sub(r"<[^>]+>", "", t)); t = re.sub(r"\([^)]*\)", "", t)
        t = re.sub(r"[×xX]\s*\d[\d–\-]*", "", t); t = t.replace(" / ", ", ").replace("/", ", ")
        return re.sub(r"\s+", " ", t).strip(" .,&")
    out, seen = [], set()
    def add(t, lo=3, hi=30):
        if lo <= len(t) <= hi and t.lower() not in seen and not any(s in t.lower() for s in ("download", "app store", "google play", "faq")):
            seen.add(t.lower()); out.append(t)
    if "/onebag/packing-list/" in match:
        for label in ("Clothing", "essentials"):
            mm = re.search(rf'<h2[^>]*>[^<]*{label}[^<]*</h2>\s*<ul[^>]*>(.*?)</ul>', htmls, re.S | re.I)
            if mm:
                for li in re.findall(r"<li>(.*?)</li>", mm.group(1), re.S):
                    add(clean(li))
                    if len(out) >= n: break
            if len(out) >= n: break
    elif "/routevia-app/gezilecek-yerler/" in match:
        for h3 in re.findall(r'<div class="poi"><h3>(.*?)</h3>', htmls, re.S):
            t = clean(h3); ltr = [c for c in t if c.isalpha()]
            if ltr and sum(c.isupper() for c in ltr) / len(ltr) > 0.7:
                t = " ".join(w.capitalize() for w in t.split())
            add(t)
            if len(out) >= n: break
    elif "/rentflow/guides/" in match:
        for li in re.findall(r"<li>(.*?)</li>", htmls, re.S):
            add(clean(li), 6, 36)
            if len(out) >= n: break
    return out[:n]


def hashtag_facets(text):
    facets = []
    for m in re.finditer(r"#([^\s#]+)", text):
        s = len(text[:m.start()].encode("utf-8")); e = len(text[:m.end()].encode("utf-8"))
        facets.append({"index": {"byteStart": s, "byteEnd": e},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return facets


def api(method, token, body=None, raw=None, ctype="application/json"):
    url = f"{PDS}/xrpc/{method}"
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"Content-Type": ctype}
    if token: h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


def build_text(theme, place, items, lang):
    hook = theme[3].format(place=place); tags = theme[4]
    joiner = " ve dahası" if lang == "tr" else " & more"
    body = (", ".join(items) + joiner + ".") if items else ""
    cta = "Ücretsiz keşfet 👇" if lang == "tr" else "Free 👇"
    text = f"{hook}: {body} {cta}\n\n{tags}"
    if len(text) > 295:  # Bluesky 300 grafem limiti — kıs
        text = f"{hook}: {body}\n\n{tags}"
    return text[:295]


def main():
    ident = os.environ.get("BLUESKY_IDENTIFIER"); pw = os.environ.get("BLUESKY_PASSWORD")
    apps = (os.environ.get("BSKY_APPS") or "onebag routevia rentflow").split()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"posted": []}
    posted = set(state.get("posted", []))

    if not (ident and pw):
        print("⚠️ BLUESKY_IDENTIFIER/PASSWORD yok → DRY-RUN (örnek metinler):")
        dry = True; sess = None
    else:
        sess = api("com.atproto.server.createSession", None, {"identifier": ident, "password": pw})
        dry = False
        print(f"✓ giriş: {sess['handle']}")

    urls = sitemap_urls()
    for app in apps:
        themes = [t for t in THEMES if t[1] == app]
        cand = None
        for u in urls:
            if u in posted: continue
            th = next((t for t in themes if t[0] in u and u.split(t[0], 1)[1].strip("/")), None)  # hub hariç
            if th and local_path(u).exists():
                cand = (u, th); break
        if not cand:
            print(f"  {app}: yeni sayfa yok"); continue
        url, theme = cand
        hs = local_path(url).read_text(encoding="utf-8", errors="ignore")
        title = meta(hs, r'og:title["\']\s+content=["\'](.*?)["\']', r"<title>(.*?)</title>")
        desc = meta(hs, r'og:description["\']\s+content=["\'](.*?)["\']', r'name=["\']description["\']\s+content=["\'](.*?)["\']')
        ogimg = meta(hs, r'og:image["\']\s+content=["\'](.*?)["\']')
        place = place_of(theme, hs, title)
        items = extract_items(theme[0], hs)
        lang = APP_LANG[app]
        text = build_text(theme, place, items, lang)
        clean_title = re.split(r"\s+\|\s+", title)[0][:280]
        print(f"\n  📡 [{app}] {url}\n     {text}")
        if dry:
            continue
        # görsel link kartı (thumb) — algoritma görünürlüğü için
        thumb = None
        if ogimg:
            try:
                img = urllib.request.urlopen(urllib.request.Request(ogimg, headers={"User-Agent": "bsky-bot/1.0"}), timeout=25).read()
                mime = "image/png" if ogimg.lower().endswith("png") else "image/jpeg"
                blob = api("com.atproto.repo.uploadBlob", sess["accessJwt"], raw=img, ctype=mime)
                thumb = blob.get("blob")
            except Exception as e:
                print(f"     (thumb atlandı: {type(e).__name__})")
        ext = {"uri": url, "title": clean_title, "description": (desc or "")[:300]}
        if thumb: ext["thumb"] = thumb
        record = {"$type": "app.bsky.feed.post", "text": text, "facets": hashtag_facets(text),
                  "langs": [lang], "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                  "embed": {"$type": "app.bsky.embed.external", "external": ext}}
        res = api("com.atproto.repo.createRecord", sess["accessJwt"],
                  {"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record})
        posted.add(url)
        print(f"     ✓ paylaşıldı: {res.get('uri','')}")

    state["posted"] = list(posted)[-2000:]
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    print(f"\n✓ state: {len(posted)} paylaşılmış URL")


if __name__ == "__main__":
    main()
