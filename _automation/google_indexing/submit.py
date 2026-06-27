#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Indexing API — sitemap'teki URL'leri günde N tane Google'a bildirir.

Akış: sitemap.xml → öncelik sırala (çok dilli/yeni içerik önce) → state'te olmayan
ilk N URL'yi al → service account ile auth → urlNotifications:publish (URL_UPDATED)
→ başarılıları state'e yaz. Kota (200/gün) dolunca temiz çıkar; cron ertesi gün kalanı.

Env:
  GOOGLE_INDEXING_SA   service account JSON'un TAMAMI (GitHub Secret). Yoksa DRY-RUN.
  DAILY_LIMIT          günlük URL sayısı (default 200 — Indexing API varsayılan kotası)
  REPING               1 ise hepsi gönderilince en eski gönderilenleri tazeler (default 0)
"""
import os, json, sys, datetime, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))   # coinsayfasi.github.io kökü
SITEMAP = os.path.join(ROOT, "sitemap.xml")
STATE = os.path.join(HERE, "state.json")
BASE = "https://coinsayfasi.github.io"
ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPE = "https://www.googleapis.com/auth/indexing"
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "200"))
REPING = os.environ.get("REPING", "0") == "1"
TODAY = datetime.date.today().isoformat()


def load_sitemap_urls():
    tree = ET.parse(SITEMAP)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [el.text.strip() for el in tree.findall(".//sm:url/sm:loc", ns)]


def priority(url):
    """Küçük = önce. Çok dilli yeni içerik (de/es/fr) EN'den önce; sığ yollar (hub) önce."""
    p = url[len(BASE):].strip("/")
    depth = p.count("/")
    is_ml = p.startswith(("de/", "es/", "fr/"))
    # 0: çok dilli hub (sığ), 1: çok dilli içerik, 2: diğer (EN/landing zaten bilinir)
    bucket = 0 if (is_ml and depth <= 2) else (1 if is_ml else 2)
    return (bucket, depth, url)


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding="utf-8"))
        except Exception:
            pass
    return {"submitted": {}, "history": []}


def save_state(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def pick_queue(urls, submitted):
    pending = [u for u in urls if u not in submitted]
    pending.sort(key=priority)
    if pending:
        return pending[:DAILY_LIMIT], "yeni"
    if REPING:  # hepsi gönderilmiş → en eski gönderilenleri tazele
        oldest = sorted(submitted, key=lambda u: submitted[u])
        return oldest[:DAILY_LIMIT], "tazeleme"
    return [], "bitti"


def main():
    urls = load_sitemap_urls()
    st = load_state()
    submitted = st.setdefault("submitted", {})
    queue, mode = pick_queue(urls, submitted)
    print(f"sitemap: {len(urls)} URL · gönderilmiş: {len(submitted)} · sıradaki ({mode}): {len(queue)} (limit {DAILY_LIMIT})")

    sa_raw = os.environ.get("GOOGLE_INDEXING_SA", "").strip()
    if not sa_raw:
        print("\n⚠️  GOOGLE_INDEXING_SA yok → DRY-RUN. Gönderilecek ilk 10 URL:")
        for u in queue[:10]:
            print("   ·", u)
        print(f"\n(Gerçek gönderim için service account JSON'unu GOOGLE_INDEXING_SA secret'ına ekle. Bkz SETUP.md)")
        return 0
    if not queue:
        print("✅ Tüm URL'ler zaten gönderilmiş, yapılacak iş yok.")
        return 0

    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    info = json.loads(sa_raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    session = AuthorizedSession(creds)

    ok = quota = err = 0
    for u in queue:
        try:
            r = session.post(ENDPOINT, json={"url": u, "type": "URL_UPDATED"}, timeout=30)
        except Exception as e:
            err += 1; print(f"  ✗ {u} → istek hatası {type(e).__name__}"); continue
        if r.status_code == 200:
            ok += 1; submitted[u] = TODAY
        elif r.status_code == 429:
            quota += 1
            print(f"  ⏸ kota doldu (429) → {ok} gönderildi, kalan yarın. ({u})")
            break
        elif r.status_code == 403:
            print(f"  ✗ 403 — service account GSC'de Sahip (Owner) değil mi? Gönderim durdu.\n     Yanıt: {r.text[:200]}")
            break
        else:
            err += 1
            if err <= 5:
                print(f"  ✗ {u} → {r.status_code} {r.text[:120]}")

    st["history"].append({"date": TODAY, "mode": mode, "ok": ok, "quota_hit": bool(quota), "errors": err})
    st["history"] = st["history"][-60:]
    save_state(st)
    print(f"\n✅ {ok} URL Google'a bildirildi · hata: {err} · toplam gönderilmiş: {len(submitted)}/{len(urls)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
