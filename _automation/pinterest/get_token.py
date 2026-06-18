#!/usr/bin/env python3
"""One-time Pinterest OAuth helper — get the write tokens for the auto-pinner.

Pinterest trial onayı GELİNCE çalıştır. İki adım:

  1) AUTH URL al ve tarayıcıda aç, izin ver:
       python3 get_token.py url
     → Pinterest seni https://coinsayfasi.github.io/?code=XXXX&state=... adresine
       yönlendirir. Adres çubuğundaki `code=` değerini KOPYALA (sayfa boş görünür,
       önemli değil — kod URL'de).

  2) Kodu token'a çevir (APP_SECRET lazım — Pinterest developer console'dan):
       PINTEREST_APP_SECRET=xxxxx python3 get_token.py token <KOPYALADIĞIN_KOD>
     → access_token + refresh_token basar ve eklenecek `gh secret` komutlarını verir.

Sadece stdlib kullanır (kurulum yok). app_id/redirect varsayılanları aşağıda;
gerekirse PINTEREST_APP_ID / PINTEREST_REDIRECT_URI env ile ez.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.parse
import urllib.request

# "Tabserve Apps" Pinterest uygulaması (bkz memory pinterest_automation).
APP_ID = os.environ.get("PINTEREST_APP_ID", "1581587").strip()
REDIRECT_URI = os.environ.get("PINTEREST_REDIRECT_URI", "https://coinsayfasi.github.io/").strip()
# Pin atmak + board oluşturmak için gereken minimum izinler.
SCOPES = "boards:read,boards:write,pins:read,pins:write"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"


def auth_url() -> str:
    q = urllib.parse.urlencode({
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": "tabserve",
    })
    return f"https://www.pinterest.com/oauth/?{q}"


def exchange(code: str) -> dict:
    secret = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    if not secret:
        sys.exit("HATA: PINTEREST_APP_SECRET env değişkeni gerekli "
                 "(Pinterest developer console → uygulaman → App secret).")
    basic = base64.b64encode(f"{APP_ID}:{secret}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"HATA {e.code}: {e.read().decode()[:400]}")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Bağlantı hatası: {e}\n(api.pinterest.com WiFi filtresine takılıyorsa "
                 "filtresiz/mobil ağda dene.)")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "url"
    if mode == "url":
        print("\n1) Şu adresi tarayıcıda aç, Pinterest'te izin ver:\n")
        print("   " + auth_url())
        print("\n2) Yönlendirildiğin adresteki `code=...` değerini kopyala, sonra:\n")
        print("   PINTEREST_APP_SECRET=xxxxx python3 get_token.py token <KOD>\n")
        return
    if mode == "token":
        if len(sys.argv) < 3:
            sys.exit("Kullanım: PINTEREST_APP_SECRET=xxx python3 get_token.py token <KOD>")
        tok = exchange(sys.argv[2].strip())
        at, rt = tok.get("access_token", ""), tok.get("refresh_token", "")
        print("\n✓ Token alındı.\n")
        print(f"access_token  (~{tok.get('expires_in','?')}s):  {at[:18]}…")
        print(f"refresh_token (~{tok.get('refresh_token_expires_in','?')}s): {rt[:18]}…")
        print(f"scope: {tok.get('scope','')}\n")
        print("GitHub secret'larını ekle (refresh-token modu = token hiç sönmez):\n")
        print(f"  gh secret set PINTEREST_REFRESH_TOKEN -b '{rt}'")
        print(f"  gh secret set PINTEREST_APP_ID        -b '{APP_ID}'")
        print(f"  gh secret set PINTEREST_APP_SECRET    -b '$PINTEREST_APP_SECRET'\n")
        print("Sonra workflow'daki cron 2 satırını yorumdan çıkar → günde 3 pin başlar.")
        return
    sys.exit("Kullanım: python3 get_token.py [url | token <KOD>]")


if __name__ == "__main__":
    main()
