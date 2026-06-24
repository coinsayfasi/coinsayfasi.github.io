#!/usr/bin/env python3
"""TikTok Content Posting API — video'yu yetkili hesabın INBOX/taslaklarına yükler (push_by_file).
Audit'siz çalışır (video.upload scope). Kullanıcı TikTok uygulamasında caption ekleyip paylaşır.

Env:
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN
Kullanım:
  python tiktok_upload.py <video.mp4>
Çıktı: publish_id (taslak hesabın TikTok inbox'ına düşer).
"""
import os
import sys
import requests

OAUTH = "https://open.tiktokapis.com/v2/oauth/token/"
INBOX_INIT = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"


def refresh_access_token(ck, cs, rt):
    r = requests.post(OAUTH, headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data={"client_key": ck, "client_secret": cs,
                            "grant_type": "refresh_token", "refresh_token": rt}, timeout=30)
    j = r.json()
    if "access_token" not in j:
        raise SystemExit(f"[tiktok] token yenileme hatası: {j}")
    return j["access_token"], j.get("refresh_token", rt)


def upload_to_inbox(access_token, video_path):
    size = os.path.getsize(video_path)
    init = requests.post(
        INBOX_INIT,
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                              "chunk_size": size, "total_chunk_count": 1}}, timeout=30)
    j = init.json()
    err = j.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise SystemExit(f"[tiktok] inbox init hatası: {err}")
    data = j["data"]
    upload_url, publish_id = data["upload_url"], data["publish_id"]
    with open(video_path, "rb") as f:
        blob = f.read()
    put = requests.put(upload_url, headers={
        "Content-Range": f"bytes 0-{size - 1}/{size}",
        "Content-Type": "video/mp4",
        "Content-Length": str(size),
    }, data=blob, timeout=120)
    if put.status_code not in (200, 201, 204):
        raise SystemExit(f"[tiktok] video yükleme hatası: HTTP {put.status_code} {put.text[:300]}")
    print(f"✓ TikTok inbox'a yüklendi → publish_id={publish_id}")
    print("  → TikTok uygulamasında bildirim/taslak gelir; caption ekleyip paylaş.")
    return publish_id


def main():
    video = sys.argv[1]
    ck = os.environ["TIKTOK_CLIENT_KEY"]
    cs = os.environ["TIKTOK_CLIENT_SECRET"]
    rt = os.environ["TIKTOK_REFRESH_TOKEN"]
    access, new_rt = refresh_access_token(ck, cs, rt)
    if new_rt != rt:
        # CI'da yeni refresh token'ı GITHUB_OUTPUT'a yaz (workflow secret günceller)
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"new_refresh_token={new_rt}\n")
        print("  (refresh token döndü — workflow güncelleyecek)")
    upload_to_inbox(access, video)


if __name__ == "__main__":
    main()
