#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gezi.tabserve.com.tr'nin GEZİLECEK-YERLER sayfalarını Pinterest'te
"Türkiye Gezilecek Yerler" board'una pinler — hedef link = gezi sayfasının
KENDİSİ (gerçek backlink). Sadece konu-uyumlu (gezilecek-yerler) URL'ler pinlenir,
alakasız içeriğe bulaşmaz. Döngüsel: günde birkaç sayfa, 21 gün tekrar-koruması.

poster.py'nin altyapısını reuse eder (PinterestClient, build_pin_image, Pexels).
Env: PINTEREST_REFRESH_TOKEN+APP_ID+APP_SECRET (veya PINTEREST_ACCESS_TOKEN),
     PEXELS_API_KEY (ops.), GEZI_PINS_PER_RUN (vars. 1). Token yoksa DRY-RUN."""
from __future__ import annotations
import html as _html
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pinterest_api import PinterestClient
from pin_image import build_pin_image, fetch_pexels_photo
from poster import resolve_token

HERE = Path(__file__).resolve().parent
STATE = HERE / "gezi_pins_state.json"
PREVIEW_DIR = HERE / "preview"
SITEMAP = "https://gezi.tabserve.com.tr/sitemap.xml"
BOARD = "Türkiye Gezilecek Yerler"
BOARD_DESC = "Türkiye'nin il il, ilçe ilçe gezilecek yerleri, rotalar ve gezi rehberleri."
TAGS = "#gezilecekyerler #seyahat #tatil #türkiye #gezi"
CTAS = ["Rotanı planla 🗺️", "Kaydet, sonra gez ✈️", "Gezi rehberini oku 📍"]
PER_RUN = int(os.environ.get("GEZI_PINS_PER_RUN", "1"))
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
esc = _html.unescape


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "gezi-pin/1.0"})
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def meta(h: str, *pats: str) -> str:
    for p in pats:
        m = re.search(p, h, re.I | re.S)
        if m:
            return esc(re.sub(r"\s+", " ", m.group(1)).strip())
    return ""


def candidate_urls() -> list[str]:
    """Sitemap'ten SADECE gezilecek-yerler konulu URL'ler (konu uyumu)."""
    try:
        xml = fetch(SITEMAP)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ sitemap alınamadı: {e}")
        return []
    urls = re.findall(r"<loc>\s*(.*?)\s*</loc>", xml)
    return [u for u in urls if "gezilecek-yerler" in u]


def _province(url: str, title: str) -> str:
    """Başlıktan/URL'den il/bölge adını çıkar (Pexels sorgusu + başlık için)."""
    m = re.search(r"/([a-z0-9-]*gezilecek-yerler)", url)
    slug = m.group(1).replace("-gezilecek-yerler", "") if m else ""
    name = slug.replace("-", " ").strip()
    return name or (title.split(" Gezilecek")[0] if title else "Türkiye")


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"pinned": {}}


def main() -> None:
    urls = candidate_urls()
    if not urls:
        print("gezi-pin: aday gezilecek-yerler sayfası yok")
        return

    st = load_state()
    pinned = st.get("pinned", {})
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=21)).isoformat()
    pending = [u for u in urls if pinned.get(u, "") < cutoff]
    if not pending:  # hepsi taze → en eskiden devam (döngü)
        pending = sorted(urls, key=lambda u: pinned.get(u, ""))
    picks = pending[:PER_RUN]

    token = resolve_token()
    dry = not token
    client = None
    board_id = None
    if dry:
        PREVIEW_DIR.mkdir(exist_ok=True)
        print(f"=== DRY-RUN (token yok) — önizlemeler -> {PREVIEW_DIR} ===")
    else:
        client = PinterestClient(token)
        board_id = client.ensure_board(BOARD, BOARD_DESC)

    posted = 0
    for url in picks:
        try:
            h = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"  {url} alınamadı: {e}")
            continue
        title = meta(h, r'og:title["\']\s+content=["\'](.*?)["\']',
                     r"<title>(.*?)</title>").split(" | ")[0]
        desc_src = meta(h, r'og:description["\']\s+content=["\'](.*?)["\']',
                        r'name=["\']description["\']\s+content=["\'](.*?)["\']')
        if not title:
            continue
        prov = _province(url, title)
        cta = CTAS[posted % len(CTAS)]
        body = f"{title}. {desc_src}".strip()
        desc = f"{body[:400]}\n\n{cta}\n\n{TAGS}"[:495]
        photo = fetch_pexels_photo(f"{prov} turkey travel landscape", PEXELS_KEY) if PEXELS_KEY else None
        # Görsel altyazısı emojisiz (PIL fontu emoji basamıyor → tofu); emoji
        # sadece Pinterest açıklamasında kalır (orada düzgün render olur).
        img_subtitle = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", "", cta).strip()
        img = build_pin_image(title, "routevia", subtitle=img_subtitle, photo=photo,
                              footer="gezi.tabserve.com.tr")

        print(f"\n• {title}\n  board: {BOARD}\n  link : {url}")
        if dry:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:50]
            (PREVIEW_DIR / f"gezi-{slug}.png").write_bytes(img)
            print("  (DRY-RUN: önizleme yazıldı)")
        else:
            try:
                pid = client.create_pin(board_id, title, desc, url, img, alt_text=desc_src)
                print(f"  ✓ pinned: {pid}")
                posted += 1
                time.sleep(4)
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ failed: {e}")
                continue
        pinned[url] = now.isoformat()

    st["pinned"] = pinned
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {posted} gezi pin(s).")


if __name__ == "__main__":
    main()
