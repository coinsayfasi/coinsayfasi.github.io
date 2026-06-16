#!/usr/bin/env python3
"""Daily Pinterest auto-pinner for the Tabserve landing/SEO pages.

Picks a small, rotating set of not-yet-pinned pages from sitemap.xml, builds a
branded vertical image (optionally over a free Pexels photo), and posts quality
pins with SEO descriptions + hashtags linking back to each page.

Run modes
---------
* Real:    PINTEREST_ACCESS_TOKEN set  -> creates pins, commits updated state.
* Dry-run: token missing               -> prints planned pins + writes preview
                                           PNGs to _automation/pinterest/preview/.

Env: PINTEREST_ACCESS_TOKEN, PEXELS_API_KEY (optional), PINS_PER_RUN (default 3).
Anti-spam by design: few pins/day, unique image+content per page, no duplicates.
"""
from __future__ import annotations

import json
import os
import re
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from pin_image import build_pin_image, fetch_pexels_photo
from pinterest_api import PinterestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SITEMAP = REPO_ROOT / "sitemap.xml"
STATE_FILE = HERE / "state.json"
PREVIEW_DIR = HERE / "preview"

PINS_PER_RUN = int(os.environ.get("PINS_PER_RUN", "3"))
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
PIN_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
# Saat hedefleme: bu çalıştırmada sadece bu app'ler pinlenir (örn "routevia" ya da
# "onebag,rentflow"). Boş = hepsi. Workflow cron'a göre set eder (kitleye uygun saat).
PIN_APPS = {a.strip() for a in os.environ.get("PIN_APPS", "").split(",") if a.strip()}

# ── Theme config: URL prefix -> app, board name, CTA + hashtag strategy ──────
THEMES = [
    {
        "match": "/routevia-app/gezilecek-yerler/",
        "app": "routevia",
        "store": "https://coinsayfasi.github.io/go/routevia/",
        "board": "Türkiye Gezilecek Yerler",
        "board_desc": "Türkiye'nin il il, ilçe ilçe gezilecek yerleri. Rota planını Routevia ile yap.",
        "ctas": [
            "Rota planını Routevia ile yap →",
            "Tüm noktaları haritada gör — Routevia →",
            "Bu rehberi Routevia'da keşfet →",
        ],
        "tags": ["#gezilecekyerler", "#seyahat", "#tatil", "#türkiye", "#routevia"],
        "lang": "tr",
    },
    {
        "match": "/onebag/packing-list/",
        "app": "onebag",
        "store": "https://coinsayfasi.github.io/go/onebag/",
        "board": "Travel Packing Tips",
        "board_desc": "Smart packing lists for every destination. Pack light, never forget — with OneBag.",
        "ctas": [
            "Get the full packing list in OneBag →",
            "Pack smart for this trip — OneBag →",
            "Never forget an item — OneBag →",
        ],
        "tags": ["#packinglist", "#travel", "#traveltips", "#onebag", "#packing"],
        "lang": "en",
    },
    {
        "match": "/rentflow/guides/",
        "app": "rentflow",
        "store": "https://coinsayfasi.github.io/go/rentflow/",
        "board": "Landlord & Rental Tips",
        "board_desc": "Practical guides for landlords — rent, tenants, leases. Manage it all with RentFlow.",
        "ctas": [
            "Manage your rentals with RentFlow →",
            "Read the full guide — RentFlow →",
            "Run your properties smarter — RentFlow →",
        ],
        "tags": ["#landlord", "#realestate", "#propertymanagement", "#rentflow", "#rentaltips"],
        "lang": "en",
    },
]


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"pinned": [], "last_run": None}


def save_state(state: dict) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sitemap_urls() -> list[str]:
    if not SITEMAP.exists():
        raise SystemExit(f"sitemap not found: {SITEMAP}")
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", SITEMAP.read_text(encoding="utf-8"))


def theme_for(url: str) -> dict | None:
    return next((t for t in THEMES if t["match"] in url), None)


def url_to_local(url: str) -> Path:
    path = re.sub(r"^https?://[^/]+/", "", url).rstrip("/")
    return REPO_ROOT / (path + "/index.html" if path else "index.html")


def _meta(html: str, *patterns: str) -> str:
    for p in patterns:
        m = re.search(p, html, re.I | re.S)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def page_meta(local: Path) -> dict:
    html = local.read_text(encoding="utf-8", errors="ignore")
    title = _meta(html,
                  r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']',
                  r"<title>(.*?)</title>")
    desc = _meta(html,
                 r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']',
                 r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']')
    keywords = _meta(html, r'<meta\s+name=["\']keywords["\']\s+content=["\'](.*?)["\']')
    # strip " | Routevia" / " — ... (2026)" style suffixes from <title> fallback
    title = re.split(r"\s+[|]\s+", title)[0].strip()[:100]  # Pinterest başlık limiti 100
    # SEO-zengin gövde için sayfanın ilk anlamlı paragraflarını çek (gerçek içerik).
    intro = ""
    for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S | re.I):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip()
        t = (t.replace("&#x27;", "'").replace("&#39;", "'").replace("&amp;", "&"))
        if len(t) > 50:
            intro = (intro + " " + t).strip()
            if len(intro) > 480:
                break
    return {"title": title, "desc": desc, "keywords": keywords, "intro": intro}


def pexels_query(app: str, title: str) -> str:
    if app == "routevia":
        # place name = text before "Gezilecek"/"—"
        q = re.split(r"\s+(?:Gezilecek|—|-)", title)[0].strip()
        return f"{q} city" if q else "turkey travel"
    if app == "onebag":
        q = re.split(r"\s+(?:Packing|packing|—|-)", title)[0].strip()
        return f"{q} travel" if q else "travel"
    return "apartment real estate"  # rentflow


def build_description(theme: dict, meta: dict) -> str:
    """SEO-zengin Pinterest açıklaması: gerçek sayfa içeriği + değer cümlesi +
    keyword hashtag'leri + marka hashtag'leri + CTA. Pinterest limiti 800 → 790'da
    kesilir. Junk/keyword-stuffing YOK; sadece sayfanın kendi içeriği kullanılır."""
    cta = random.choice(theme["ctas"])
    # Sayfa keyword'lerinden 6'ya kadar hashtag (slug) + marka/tema hashtag'leri.
    kw_tags = []
    for kw in (meta["keywords"].split(",") if meta["keywords"] else []):
        slug = re.sub(r"[^0-9a-zçğıöşü]+", "", kw.strip().lower())
        if 3 <= len(slug) <= 28 and f"#{slug}" not in kw_tags:
            kw_tags.append(f"#{slug}")
        if len(kw_tags) >= 6:
            break
    tags = " ".join(dict.fromkeys(kw_tags + theme["tags"]))  # dedupe, sıra korunur
    # Gövde: sayfa açıklaması + ilk paragraflar (gerçek içerik) + marka değer cümlesi.
    body_parts = [p for p in (meta["desc"], meta.get("intro"), theme["board_desc"]) if p]
    body = " ".join(dict.fromkeys(body_parts)) or meta["title"]
    return f"{body}\n\n{cta}\n\n{tags}"[:800]  # Pinterest açıklama limiti = 800


def pick_candidates(state: dict) -> list[dict]:
    pinned = set(state.get("pinned", []))
    by_app: dict[str, list[dict]] = {}
    for url in sitemap_urls():
        if url in pinned:
            continue
        theme = theme_for(url)
        if not theme:
            continue  # only content pages with a configured theme
        if PIN_APPS and theme["app"] not in PIN_APPS:
            continue  # saat hedefleme: bu çalıştırma bu app'i kapsamıyor
        local = url_to_local(url)
        if not local.exists():
            continue
        by_app.setdefault(theme["app"], []).append({"url": url, "theme": theme, "local": local})

    # Daily-seeded shuffle so the rotation differs each run.
    rng = random.Random(datetime.now(timezone.utc).strftime("%Y%m%d"))
    for items in by_app.values():
        rng.shuffle(items)

    # Round-robin across apps for a balanced feed.
    chosen, apps = [], list(by_app.keys())
    rng.shuffle(apps)
    i = 0
    while len(chosen) < PINS_PER_RUN and any(by_app.values()):
        app = apps[i % len(apps)]
        if by_app.get(app):
            chosen.append(by_app[app].pop())
        i += 1
        if i > 1000:
            break
    return chosen


def main() -> None:
    random.seed()
    state = load_state()
    candidates = pick_candidates(state)
    if not candidates:
        print("Nothing new to pin (all pages already pinned or no candidates).")
        save_state(state)
        return

    dry = not PIN_TOKEN
    client = None if dry else PinterestClient(PIN_TOKEN)
    board_ids: dict[str, str] = {}
    if dry:
        PREVIEW_DIR.mkdir(exist_ok=True)
        print(f"=== DRY-RUN (no PINTEREST_ACCESS_TOKEN) — previews -> {PREVIEW_DIR} ===")

    posted = 0
    for c in candidates:
        theme, meta = c["theme"], page_meta(c["local"])
        if not meta["title"]:
            continue
        desc = build_description(theme, meta)
        photo = fetch_pexels_photo(pexels_query(theme["app"], meta["title"]), PEXELS_KEY)
        img = build_pin_image(meta["title"], theme["app"],
                              subtitle=random.choice(theme["ctas"]), photo=photo)

        store_link = theme["store"]
        print(f"\n• [{theme['app']}] {meta['title']}")
        print(f"  board : {theme['board']}")
        print(f"  link  : {store_link}  (source page: {c['url']})")
        print(f"  desc  : {desc[:120]}...")

        if dry:
            slug = re.sub(r"[^a-z0-9]+", "-", meta["title"].lower())[:50]
            (PREVIEW_DIR / f"{theme['app']}-{slug}.png").write_bytes(img)
        else:
            if theme["board"] not in board_ids:
                board_ids[theme["board"]] = client.ensure_board(theme["board"], theme["board_desc"])
            try:
                pid = client.create_pin(board_ids[theme["board"]], meta["title"], desc,
                                        store_link, img, alt_text=meta["desc"])
                print(f"  ✓ pinned: {pid}")
                state["pinned"].append(c["url"])
                posted += 1
                time.sleep(4)  # be gentle with the API
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ failed: {e}")

    if not dry:
        print(f"\nDone. {posted} pin(s) created.")
    save_state(state)


if __name__ == "__main__":
    main()
