#!/usr/bin/env python3
"""TikTok Content Posting API — video'yu yetkili hesaba yükler.

İki mod:
  inbox  (varsayılan, video.upload scope, AUDIT YOK): taslağa atar, kullanıcı caption+ses ekleyip paylaşır.
  direct (video.publish scope, AUDIT GEREKİR): SEO caption ile otomatik paylaşır (onay sonrası PUBLIC).

Env:
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN
  TIKTOK_PRIVACY (direct mod): SELF_ONLY (audit öncesi) | PUBLIC_TO_EVERYONE (audit sonrası). Vars: SELF_ONLY
Kullanım:
  python tiktok_upload.py <video.mp4> [app] [inbox|direct]
"""
import os
import sys
import requests

OAUTH = "https://open.tiktokapis.com/v2/oauth/token/"
INBOX_INIT = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
DIRECT_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"

# SEO caption + hashtag (Direct Post otomatik basar; bio link tıklanır)
CAPTIONS = {
    "onebag": ("Pack carry-on only & never forget a thing ✈️\U0001f392 Your smart packing list — free. "
               "\U0001f4f2 Download → link in bio "
               "#packinglist #travelhacks #carryon #traveltips #onebag #packwithme #traveltok #minimalist"),
    "routevia": ("Türkiye'yi gez, rotanı saniyede planla \U0001f9ed\U0001f1f9\U0001f1f7 Kişiye özel günlük gezi planı — ücretsiz. "
                 "\U0001f4f2 İndir → bio'daki link "
                 "#gezilecekyerler #türkiye #tatil #gezi #seyahat #routevia #kapadokya #traveltok"),
    "rentflow": ("Manage your rentals without spreadsheets \U0001f3e0\U0001f4ca Track rent, tenants & leases — free. "
                 "\U0001f4f2 Download → link in bio "
                 "#landlord #realestate #rentalproperty #propertymanagement #rentflow #realestateinvesting #passiveincome"),
}


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


def _put_video(upload_url, video_path, size):
    with open(video_path, "rb") as f:
        blob = f.read()
    put = requests.put(upload_url, headers={
        "Content-Range": f"bytes 0-{size - 1}/{size}",
        "Content-Type": "video/mp4", "Content-Length": str(size),
    }, data=blob, timeout=120)
    if put.status_code not in (200, 201, 204):
        raise SystemExit(f"[tiktok] video yükleme hatası: HTTP {put.status_code} {put.text[:300]}")


def direct_post(access_token, video_path, caption):
    """Direct Post (video.publish, AUDIT GEREKİR). Caption otomatik basılır.
    Audit öncesi privacy SELF_ONLY olmalı; onay sonrası PUBLIC_TO_EVERYONE."""
    privacy = os.environ.get("TIKTOK_PRIVACY", "SELF_ONLY")
    size = os.path.getsize(video_path)
    init = requests.post(
        DIRECT_INIT,
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        json={"post_info": {"title": caption[:2200], "privacy_level": privacy,
                            "disable_comment": False, "disable_duet": False, "disable_stitch": False},
              "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                              "chunk_size": size, "total_chunk_count": 1}}, timeout=30)
    j = init.json()
    err = j.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise SystemExit(f"[tiktok] direct post init hatası: {err}")
    data = j["data"]
    _put_video(data["upload_url"], video_path, size)
    print(f"✓ TikTok Direct Post → publish_id={data['publish_id']} (privacy={privacy})")
    return data["publish_id"]


def main():
    video = sys.argv[1]
    app = sys.argv[2] if len(sys.argv) > 2 else ""
    mode = sys.argv[3] if len(sys.argv) > 3 else "inbox"
    ck = os.environ["TIKTOK_CLIENT_KEY"]
    cs = os.environ["TIKTOK_CLIENT_SECRET"]
    rt = os.environ["TIKTOK_REFRESH_TOKEN"]
    access, new_rt = refresh_access_token(ck, cs, rt)
    if new_rt != rt:
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"new_refresh_token={new_rt}\n")
        print("  (refresh token döndü)")
    if mode == "direct":
        direct_post(access, video, CAPTIONS.get(app, CAPTIONS["onebag"]))
    else:
        upload_to_inbox(access, video)


if __name__ == "__main__":
    main()
