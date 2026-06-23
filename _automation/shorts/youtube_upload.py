#!/usr/bin/env python3
"""YouTube'a Short yükle (refresh-token → access token → resumable upload).

Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Test modu:  YT_TEST=1 python3 youtube_upload.py        → sadece kanalı yazdırır (yükleme yok)
Yükleme:    python3 youtube_upload.py <video.mp4>       → yanındaki <video>.meta.json'u kullanır
            (yoksa dosya adından başlık). Privacy: YT_PRIVACY (default private).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

CID = os.environ.get("YT_CLIENT_ID", "").strip()
CSEC = os.environ.get("YT_CLIENT_SECRET", "").strip()
RTOK = os.environ.get("YT_REFRESH_TOKEN", "").strip()


def access_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token",
                      data={"client_id": CID, "client_secret": CSEC,
                            "refresh_token": RTOK, "grant_type": "refresh_token"}, timeout=30)
    if r.status_code >= 400:
        raise SystemExit(f"token yenileme HATA {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]


def channel_title(tok: str) -> str:
    r = requests.get("https://www.googleapis.com/youtube/v3/channels",
                     params={"part": "snippet", "mine": "true"},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0]["snippet"]["title"] if items else "(kanal bulunamadı)"


def upload(tok: str, video: str, meta: dict) -> dict:
    privacy = os.environ.get("YT_PRIVACY", "private")  # audit'e kadar zaten private
    body = {
        "snippet": {"title": meta["title"][:100], "description": meta["description"][:4900],
                    "tags": meta.get("tags", []), "categoryId": meta.get("categoryId", "19")},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/*"},
                      data=json.dumps(body), timeout=30)
    if r.status_code >= 400:
        raise SystemExit(f"resumable init HATA {r.status_code}: {r.text[:400]}")
    up_url = r.headers["Location"]
    data = Path(video).read_bytes()
    r2 = requests.put(up_url, headers={"Authorization": f"Bearer {tok}",
                                       "Content-Type": "video/*", "Content-Length": str(len(data))},
                      data=data, timeout=600)
    if r2.status_code >= 400:
        raise SystemExit(f"upload HATA {r2.status_code}: {r2.text[:400]}")
    return r2.json()


def main() -> None:
    if not (CID and CSEC and RTOK):
        raise SystemExit("HATA: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN gerekli.")
    tok = access_token()
    if os.environ.get("YT_TEST") == "1":
        print(f"✓ Bağlantı OK. Kanal: {channel_title(tok)}")
        return
    if len(sys.argv) < 2:
        raise SystemExit("Kullanım: python3 youtube_upload.py <video.mp4>")
    video = sys.argv[1]
    metaf = Path(video).with_suffix(".meta.json")
    if metaf.exists():
        meta = json.loads(metaf.read_text(encoding="utf-8"))
    else:
        meta = {"title": Path(video).stem, "description": "", "tags": []}
    res = upload(tok, video, meta)
    vid = res.get("id", "")
    print(f"✓ Yüklendi: https://youtube.com/watch?v={vid}  (privacy: {res.get('status', {}).get('privacyStatus')})")


if __name__ == "__main__":
    main()
