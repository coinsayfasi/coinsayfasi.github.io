#!/usr/bin/env python3
"""Belirtilen pinleri sil + (opsiyonel) state.json'ı sıfırla.

Eski/test pinlerini (yanlış format, tekrar görsel) temizlemek için. Pinterest v5
pin görselini düzenlemeye izin vermez → silip cron'a taze attırmak tek temiz yol.

Env: CLEANUP_PIN_IDS (virgüllü pin id), RESET_STATE (1/0, default 1),
     + poster.py ile aynı token env'leri (REFRESH_TOKEN/APP_ID/APP_SECRET ya da
     ACCESS_TOKEN). Sadece GitHub Actions'ta (secret'lar orada) çalıştırılır.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pinterest_api import PinterestClient, refresh_access_token

STATE = Path(__file__).resolve().parent / "state.json"


def _token() -> str:
    rt = os.environ.get("PINTEREST_REFRESH_TOKEN", "").strip()
    aid = os.environ.get("PINTEREST_APP_ID", "").strip()
    sec = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    if rt and aid and sec:
        return refresh_access_token(aid, sec, rt)
    return os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()


def main() -> None:
    ids = [x.strip() for x in os.environ.get("CLEANUP_PIN_IDS", "").split(",") if x.strip()]
    token = _token()
    if not token:
        raise SystemExit("HATA: token yok (secret'lar eksik).")
    client = PinterestClient(token)
    for pid in ids:
        try:
            client.delete_pin(pid)
            print(f"✓ silindi: {pid}")
        except Exception as e:  # noqa: BLE001
            print(f"✗ {pid}: {e}")
    if os.environ.get("RESET_STATE", "1") == "1":
        STATE.write_text(json.dumps({"pinned": [], "last_run": None},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
        print("state.json sıfırlandı → cron sayfaları taze, yeni formatla yeniden atar.")
    print(f"Done. {len(ids)} pin işlendi.")


if __name__ == "__main__":
    main()
