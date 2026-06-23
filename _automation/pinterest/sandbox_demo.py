#!/usr/bin/env python3
"""Pinterest STANDARD-access demo driver — run this LIVE while screen recording.

Pinterest reddetti çünkü ilk video bir "slideshow" idi. Standard onayı için
KESİNTİSİZ GERÇEK ekran kaydı şart; kayıtta şunlar GÖRÜNMELİ:
  1) OAuth: auth URL → Pinterest login → "Give access" → redirect_uri'de `code=`
  2) Token exchange API çağrısı (Authorization: Basic base64(app_id:secret))
  3) API kullanımı: bir Pin OLUŞTUR ve oluşan Pin'i geri oku/göster

Trial erişimi production'da pin atamaz (403 code 29) → demo SANDBOX'ta yapılır
(api-sandbox.pinterest.com). Eloise'in mailindeki yönlendirme de bu.

ÇEKİM (iki adım, ikisi de kayıtta):

  1) AUTH URL'yi al, tarayıcıda aç, izin ver:
       python3 sandbox_demo.py url
     → coinsayfasi.github.io/?code=XXXX&state=tabserve adresine düşersin.
       Adres çubuğundaki `code=` değerini kopyala (sayfa boş, önemli değil).

  2) Kodu kullanıp CANLI token al + sandbox pin oluştur + geri oku:
       PINTEREST_APP_SECRET=xxxxx python3 sandbox_demo.py run <KOPYALADIĞIN_KOD>
     → bu komut ekrana büyük büyük basar: token alındı → board → pin id →
       GET ile pin geri okundu. Hepsi tek akışta, kayıt için ideal.

Notlar:
  * APP_SECRET Pinterest developer console → uygulaman → "App secret key".
  * Sandbox/production host'ları PINTEREST_TOKEN_HOST / PINTEREST_API_HOST ile
    ezilebilir (varsayılan: sandbox).
  * api(-sandbox).pinterest.com WiFi filtresine takılırsa filtresiz/mobil ağda çek.
"""
from __future__ import annotations

import base64
import os
import sys
import urllib.parse
import warnings

warnings.filterwarnings("ignore")  # kayıt için temiz çıktı (urllib3/LibreSSL uyarısı vs.)

import requests

from pin_image import build_pin_image

# "Tabserve Apps" Pinterest uygulaması (bkz memory pinterest_automation).
APP_ID = os.environ.get("PINTEREST_APP_ID", "1581587").strip()
REDIRECT_URI = os.environ.get("PINTEREST_REDIRECT_URI", "https://coinsayfasi.github.io/").strip()
SCOPES = "boards:read,boards:write,pins:read,pins:write"

# Demo SANDBOX'ta yapılır (trial production'da pin atamaz). İstenirse production'a
# çevrilebilir ama Standard onayı gelmeden production pin = 403.
TOKEN_HOST = os.environ.get("PINTEREST_TOKEN_HOST", "https://api-sandbox.pinterest.com").rstrip("/")
API_HOST = os.environ.get("PINTEREST_API_HOST", "https://api-sandbox.pinterest.com").rstrip("/")
API = f"{API_HOST}/v5"

DEMO_BOARD = "Tabserve Travel & Rental Tips"
DEMO_LINK = "https://coinsayfasi.github.io/go/onebag/"


def _hr(title: str) -> None:
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)


def auth_url() -> str:
    q = urllib.parse.urlencode({
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": "tabserve",
    })
    return f"https://www.pinterest.com/oauth/?{q}"


def _secret() -> str:
    s = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    if not s:
        sys.exit("HATA: PINTEREST_APP_SECRET gerekli "
                 "(Pinterest developer console → uygulaman → App secret key).")
    return s


def exchange(code: str) -> str:
    _hr("ADIM 2 — Authorization code → Access token (token exchange API çağrısı)")
    basic = base64.b64encode(f"{APP_ID}:{_secret()}".encode()).decode()
    print(f"POST {TOKEN_HOST}/v5/oauth/token")
    print(f"Authorization: Basic {basic[:24]}…  (base64 of app_id:app_secret)")
    print(f"grant_type=authorization_code  code={code[:10]}…  redirect_uri={REDIRECT_URI}")
    r = requests.post(
        f"{TOKEN_HOST}/v5/oauth/token",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code,
              "redirect_uri": REDIRECT_URI},
        timeout=30,
    )
    if r.status_code >= 400:
        sys.exit(f"HATA {r.status_code}: {r.text[:400]}")
    tok = r.json()
    at = tok.get("access_token", "")
    print(f"\n✓ Access token alındı: {at[:18]}…  scope={tok.get('scope','')}")
    return at


def ensure_board(s: requests.Session, name: str) -> str:
    r = s.get(f"{API}/boards", params={"page_size": 100}, timeout=20)
    r.raise_for_status()
    for b in r.json().get("items", []):
        if b.get("name", "").strip().lower() == name.lower():
            print(f"✓ Board mevcut: {name}  (id {b['id']})")
            return b["id"]
    r = s.post(f"{API}/boards",
               json={"name": name, "description": "Demo board", "privacy": "PUBLIC"},
               timeout=20)
    r.raise_for_status()
    bid = r.json()["id"]
    print(f"✓ Board oluşturuldu: {name}  (id {bid})")
    return bid


def run(code: str) -> None:
    token = exchange(code)
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})

    _hr("ADIM 3 — API kullanımı: Pin OLUŞTUR")
    print(f"API host: {API}")
    board_id = ensure_board(s, DEMO_BOARD)

    img = build_pin_image(
        title="Travel lighter, stress less",
        app="onebag",
        subtitle="One bag. Every trip.",
    )
    payload = {
        "board_id": board_id,
        "title": "OneBag — pack carry-on only",
        "description": "Carry-on packing tips with OneBag. #travel #onebag #packinglight",
        "link": DEMO_LINK,
        "alt_text": "OneBag packing tips pin",
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/png",
            "data": base64.b64encode(img).decode("ascii"),
        },
    }
    print(f"POST {API}/pins   (board_id={board_id}, image_base64 {len(img)//1024} KB)")
    r = s.post(f"{API}/pins", json=payload, timeout=60)
    if r.status_code >= 400:
        sys.exit(f"HATA create_pin {r.status_code}: {r.text[:400]}")
    pin_id = r.json().get("id")
    print(f"\n✓ PIN OLUŞTURULDU — id: {pin_id}")

    _hr("ADIM 4 — Oluşan Pin'i geri oku (GET /pins/{id}) — kanıt")
    r = s.get(f"{API}/pins/{pin_id}", timeout=20)
    r.raise_for_status()
    p = r.json()
    print(f"GET {API}/pins/{pin_id}")
    print(f"  id:          {p.get('id')}")
    print(f"  title:       {p.get('title')}")
    print(f"  board_id:    {p.get('board_id')}")
    print(f"  link:        {p.get('link')}")
    print(f"  created_at:  {p.get('created_at')}")
    print("\n✓✓ DEMO TAMAM — OAuth + token exchange + pin create + read-back kayıtta.")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "url"
    if mode == "url":
        _hr("ADIM 1 — OAuth: bu URL'yi tarayıcıda aç ve 'Give access' bas")
        print("\n   " + auth_url() + "\n")
        print("Sonra redirect'teki `code=` değerini al ve şunu çalıştır:")
        print("   PINTEREST_APP_SECRET=xxxxx python3 sandbox_demo.py run <KOD>")
        return
    if mode == "run":
        if len(sys.argv) < 3:
            sys.exit("Kullanım: PINTEREST_APP_SECRET=xxx python3 sandbox_demo.py run <KOD>")
        run(sys.argv[2].strip())
        return
    sys.exit("Kullanım: python3 sandbox_demo.py [url | run <KOD>]")


if __name__ == "__main__":
    main()
