# TikTok Production Review — Başvuru Materyali (Direct Post / video.publish)
_Full-auto public paylaşım için. Sandbox'ta çalıştır → demo çek → Submit for review._

## Önce portal: video.publish scope ekle + re-auth
1. **Production** app → Scopes → **`video.publish`** ekle (Content Posting API → "Direct Post" aç).
2. Aynısını **Sandbox**'a da ekle (Direct Post enable).
3. **Re-authorize** (her iki scope ile) — yeni link (kuruluma kodu ver):
   `https://www.tiktok.com/v2/auth/authorize/?client_key=sbawzn3yz90e10imm6&scope=video.upload,video.publish&response_type=code&redirect_uri=https%3A%2F%2Fcoinsayfasi.github.io%2Ftiktok-callback%2F&state=tabserve`

## "Explain how each product and scope works" (kutuya yapıştır, ~1000 krk)
```
Tabserve is a publisher of small mobile apps (OneBag - travel packing lists, Routevia - trip planning, RentFlow - rental management). We use TikTok to share short promotional videos about our own apps on our own official account (@tabserve).

Login Kit (user.info.basic): Used once to authenticate our own TikTok account and obtain an access token so our backend can post to it. We only authorize our own account.

Content Posting API (video.publish - Direct Post): Our automated backend generates a short vertical video for one of our apps each day and posts it directly to our own @tabserve account with a relevant caption and hashtags. The video file is sent via FILE_UPLOAD (push_by_file). We post 1-3 videos per day, only to our own account, only our own original content about our own apps. No third-party or user content is involved. Privacy is PUBLIC_TO_EVERYONE.

The integration is server-side (GitHub Actions cron). The demo video shows: authorizing our account, the backend uploading a video, and the post appearing on the TikTok profile.
```

## Demo video (30-60 sn ekran kaydı) — script
TikTok, entegrasyonun uçtan uca çalıştığını görmek istiyor. **Sandbox'ta** çek:
1. **Developer Portal'ı göster** (Tabserve app, Content Posting API + video.publish scope görünsün).
2. **Authorize akışı:** authorize linkine tıkla → TikTok izin ekranı → onayla → callback'te kod.
3. **Backend post:** terminalde `tiktok_upload.py ... direct` çalıştır → "✓ Direct Post → publish_id" çıktısı.
4. **Sonuç:** TikTok @tabserve profilinde videonun göründüğünü göster (sandbox'ta SELF_ONLY olur, normal).
5. Web sitesi domaini (coinsayfasi.github.io) demo'da görünsün (portal'da kayıtlı domainle aynı).

> Kayıt: QuickTime ekran kaydı (Mac) → mp4 → review formuna yükle. Max 50MB.

## Onay sonrası (full-auto'ya geçiş)
1. Workflow'da `tiktok_upload.py ... inbox` → **`direct`** yap.
2. `TIKTOK_PRIVACY` zaten `PUBLIC_TO_EVERYONE` ayarlı.
3. Production refresh token'ı (video.publish'li) secret'a koy: `TIKTOK_SB_REFRESH_TOKEN` güncelle ya da production creds'e geç.
→ Artık cron tamamen otomatik, SEO caption'lı, public paylaşır. Senin işin 0.

## Cron sıklığı (sağlıklı maksimum)
- Şu an: 3/gün (app başına 1) — TikTok için ideal.
- İstenirse app başına 2. slot eklenir (~6/gün) ama daha fazlası erişimi düşürür. "Max" = spam = baskılanma.
