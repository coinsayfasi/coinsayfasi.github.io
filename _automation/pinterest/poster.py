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

import html as _html
import json
import os
import re
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from pin_image import build_pin_image, fetch_pexels_photo
from pinterest_api import PinterestClient, refresh_access_token

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SITEMAP = REPO_ROOT / "sitemap.xml"
STATE_FILE = HERE / "state.json"
PREVIEW_DIR = HERE / "preview"

PINS_PER_RUN = int(os.environ.get("PINS_PER_RUN", "3"))
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()


def resolve_token() -> str:
    """Bir access token döndür. Tercih: refresh-token modu (hiç sönmez); yoksa
    statik PINTEREST_ACCESS_TOKEN; ikisi de yoksa boş (= dry-run)."""
    rt = os.environ.get("PINTEREST_REFRESH_TOKEN", "").strip()
    app_id = os.environ.get("PINTEREST_APP_ID", "").strip()
    app_secret = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    if rt and app_id and app_secret:
        try:
            return refresh_access_token(app_id, app_secret, rt)
        except Exception as e:  # noqa: BLE001
            print(f"⚠ refresh token başarısız ({e}); statik token'a düşülüyor.")
    return os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()


PIN_TOKEN = resolve_token()
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
        "titles": [
            "{e} Gezilecek Yerler — Gezi Rehberi",
            "{e} Gezilecek Yerler — En Güzel Rotalar",
            "{eloc} Nereye Gidilir? Gezi Rehberi",
            "{e} Gezi Rotası — Görülecek Yerler",
        ],
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
        "titles": [
            "What to Pack for {e} — Carry-On Packing List",
            "{e} Packing List — Carry-On Essentials",
            "What to Pack for {e}: Carry-On Only Guide",
            "{e} Travel Packing List — Pack Light",
            "{e} Travel Checklist — Carry-On Packing Tips",
        ],
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
    {
        # 88 bagaj rehberi + 121 "A vs B" karşılaştırma (compare alt yolu da buraya düşer)
        "match": "/onebag/baggage/",
        "app": "onebag",
        "store": "https://coinsayfasi.github.io/go/onebag/",
        "board": "Airline Baggage Allowance",
        "board_desc": "Carry-on & checked baggage size and weight limits by airline. Track your bag with OneBag.",
        "ctas": [
            "Check your airline's limit — OneBag →",
            "Track carry-on weight — OneBag →",
            "Avoid baggage fees — OneBag →",
        ],
        "tags": ["#carryon", "#baggage", "#flighttips", "#travel", "#onebag"],
        "lang": "en",
        "titles": [
            "{e} Baggage Allowance — Carry-On & Checked Limits",
            "{e} Carry-On Size & Weight Limit",
            "{e} Hand Luggage Rules — Avoid Baggage Fees",
            "{e} Cabin Bag Allowance Guide",
        ],
    },
    {
        "match": "/rentflow/rent-increase-laws/",
        "app": "rentflow",
        "store": "https://coinsayfasi.github.io/go/rentflow/",
        "board": "Landlord & Rental Tips",
        "board_desc": "Rent increase laws & caps by country for landlords. Stay compliant with RentFlow.",
        "ctas": [
            "Track rent increases — RentFlow →",
            "Stay compliant — RentFlow →",
            "Manage rentals smarter — RentFlow →",
        ],
        "tags": ["#landlord", "#rentincrease", "#realestate", "#rentaltips", "#rentflow"],
        "lang": "en",
    },
    {
        "match": "/rentflow/calculators/",
        "app": "rentflow",
        "store": "https://coinsayfasi.github.io/go/rentflow/",
        "board": "Landlord & Rental Tips",
        "board_desc": "Free calculators for landlords — yield, cash flow, rent increase. Run the numbers in RentFlow.",
        "ctas": [
            "Calculate real yield — RentFlow →",
            "Track cash flow — RentFlow →",
            "Run your numbers — RentFlow →",
        ],
        "tags": ["#realestateinvesting", "#landlord", "#rentalproperty", "#cashflow", "#rentflow"],
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
        t = _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip())
        if len(t) > 50:
            intro = (intro + " " + t).strip()
            if len(intro) > 640:
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
    # rentflow — başlığa göre alakalı + çeşitli görsel (hep aynı foto olmasın)
    tl = title.lower()
    if any(k in tl for k in ("calculat", "yield", "cash flow", "cap rate", "roi")):
        return random.choice(["real estate finance", "house money calculator", "property investment"])
    if "tax" in tl:
        return random.choice(["tax paperwork desk", "accounting documents"])
    if any(k in tl for k in ("tenant", "screen", "lease")):
        return random.choice(["apartment living room", "modern apartment interior", "renting home"])
    if any(k in tl for k in ("law", "increase", "rent control")):
        return random.choice(["apartment building exterior", "city apartments"])
    return random.choice(["rental property", "modern apartment", "house keys real estate",
                          "real estate investing", "for rent sign", "landlord property"])


def _tr_loc(name: str) -> str:
    """Türkçe bulunma hâli eki (ünlü+ünsüz uyumlu): Adana→Adana'da, İzmir→İzmir'de,
    Sinop→Sinop'ta. Proper-noun apostrof + da/de/ta/te."""
    low = name.replace("İ", "i").replace("I", "ı").lower()
    back, front = "aıou", "eiöü"
    last_vowel = next((c for c in reversed(low) if c in back or c in front), "")
    if not last_vowel:
        return f"{name}'de"
    d = "t" if low[-1] in "fstkçşhp" else "d"
    v = "a" if last_vowel in back else "e"
    return f"{name}'{d}{v}"


def _routevia_province(url: str) -> str:
    """Routevia ilçe URL'sinden (.../gezilecek-yerler/<il>/<ilçe>/) il'in DOĞRU
    (Türkçe) adını il index sayfasının başlığından çek. İl sayfasıysa/bulamazsa ''."""
    parts = re.sub(r"^https?://[^/]+/", "", url).strip("/").split("/")
    if "gezilecek-yerler" not in parts:
        return ""
    i = parts.index("gezilecek-yerler")
    sub = parts[i + 1:]
    if len(sub) < 2:           # tek segment = il sayfası (ilçe değil)
        return ""
    prov_local = REPO_ROOT.joinpath(*parts[:i + 1], sub[0], "index.html")
    if prov_local.exists():
        m = re.search(r"<title>(.*?)</title>", prov_local.read_text(encoding="utf-8", errors="ignore"), re.I | re.S)
        if m:
            return re.split(r"\s+Gezilecek\b", _html.unescape(m.group(1)), flags=re.I)[0].strip()
    return ""


def _extract_entity(theme: dict, title: str, url: str = "") -> str:
    """Sayfa başlığından niş varlığı çıkar (ülke/havayolu/şehir). Bulamazsa ''."""
    m = theme["match"]
    if "packing-list" in m:
        mm = re.search(r"(?:What to Pack for|Pack for)\s+(.+?)\s*(?:[—\-(]|$)", title, re.I)
        return mm.group(1).strip() if mm else ""
    if "baggage" in m:
        return re.split(r"\s+Baggage\b", title, flags=re.I)[0].strip()
    if "gezilecek-yerler" in m:
        base = re.split(r"\s+Gezilecek\b", title, flags=re.I)[0].strip()
        # Generic ilçe ("Merkez") tek başına anlamsız → il adını başına koy.
        if base.lower() in ("merkez", "merkez i̇lçesi", "merkez ilçesi"):
            prov = _routevia_province(url)
            if prov:
                return f"{prov} {base}"
        return base
    return ""


def build_title(theme: dict, meta: dict, url: str = "") -> str:
    """Dönüşümlü, SEO-zengin pin başlığı: niş varlık (ülke/havayolu/şehir) +
    dönen yüksek-hacim head keyword şablonu. Şablon yoksa / varlık çıkmazsa sayfa
    başlığına düşer. Sayfanın kendi (sayı-zengin) başlığı da rotasyona dahildir."""
    title = _html.unescape(meta["title"]).strip()
    templates = theme.get("titles")
    if not templates:
        return title[:100]
    entity = _extract_entity(theme, title, url)
    if not entity or len(entity) > 40:
        return title[:100]
    # Sayfanın orijinal başlığı da seçeneklerden biri (çeşitlilik + sayı-zengin varyant).
    choice = random.choice(list(templates) + ["{__orig__}"])
    out = title if choice == "{__orig__}" else choice.format(e=entity, eloc=_tr_loc(entity))
    return out[:100]  # Pinterest başlık limiti 100


def build_description(theme: dict, meta: dict, title: str | None = None) -> str:
    """SEO-maks Pinterest açıklaması. Hem Pinterest aramasında hem Google'da (pin
    sayfası indeksli) sıralatmak için: ANA keyword'ü (başlık) başa al → doğal,
    keyword-zengin okunaklı gövde (gerçek sayfa içeriği) → makul hashtag seti.
    ~790'a doldurulur (limit 800). Keyword-stuffing YOK (Pinterest'te spam sinyali);
    sadece sayfanın kendi içeriği + ilgili hashtag'ler."""
    cta = random.choice(theme["ctas"])
    # Hashtag: sayfa keyword'lerinden 8'e kadar (slug) + tema hashtag'leri, dedupe.
    kw_tags = []
    for kw in (meta["keywords"].split(",") if meta["keywords"] else []):
        slug = re.sub(r"[^0-9a-zçğıöşü]+", "", kw.strip().lower())
        if 3 <= len(slug) <= 28 and f"#{slug}" not in kw_tags:
            kw_tags.append(f"#{slug}")
        if len(kw_tags) >= 6:
            break
    tags = " ".join(dict.fromkeys(kw_tags + theme["tags"]))  # dedupe, sıra korunur
    # Gövde: BAŞLIK (ana keyword, öne) + sayfa açıklaması + gerçek paragraflar + değer.
    title = _html.unescape(title or meta["title"]).strip()
    rest_parts, seen = [], {title.lower()}
    for p in (meta["desc"], meta.get("intro"), theme["board_desc"]):
        p = _html.unescape(p or "").strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            rest_parts.append(p)
    rest = " ".join(rest_parts)
    body = f"{title}. {rest}".strip() if rest else title
    # CTA + hashtag'ler HER ZAMAN korunur (keşif değeri); gövde sığacak şekilde kısalır.
    suffix = f"\n\n{cta}\n\n{tags}"
    max_body = 490 - len(suffix)
    return (body[:max_body].rstrip() + suffix)  # hedef ≤500 karakter (etiket dahil)


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
        pin_title = build_title(theme, meta, c["url"])  # dönüşümlü SEO başlık
        desc = build_description(theme, meta, pin_title)
        photo = fetch_pexels_photo(pexels_query(theme["app"], meta["title"]), PEXELS_KEY)
        img = build_pin_image(pin_title, theme["app"],
                              subtitle=random.choice(theme["ctas"]), photo=photo)

        store_link = theme["store"]
        print(f"\n• [{theme['app']}] {pin_title}")
        print(f"  board : {theme['board']}")
        print(f"  link  : {store_link}  (source page: {c['url']})")
        print(f"  desc  : {desc[:120]}...")

        if dry:
            slug = re.sub(r"[^a-z0-9]+", "-", pin_title.lower())[:50]
            (PREVIEW_DIR / f"{theme['app']}-{slug}.png").write_bytes(img)
        else:
            if theme["board"] not in board_ids:
                board_ids[theme["board"]] = client.ensure_board(theme["board"], theme["board_desc"])
            try:
                pid = client.create_pin(board_ids[theme["board"]], pin_title, desc,
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
