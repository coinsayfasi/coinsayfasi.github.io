# YouTube API Audit — başvuru paketi (public yükleme kilidini açar)

Yeni Google Cloud projesi denetlenene kadar API ile yüklenen videolar **private/unlisted**
kalır (public olamaz). Denetimden geçince **public** (Keşfet/Shorts akışı) açılır.

## 📝 Başvuru formu
👉 https://support.google.com/youtube/contact/yt_api_form
(Giriş: projenin sahibi **merve.eroglu@gmail.com** ile — Cloud projesi onda.)

## Forma yazılacak bilgiler (hazır cevaplar)

**Google Cloud Project Number:** 652543258166
**Project ID:** tabserve-shorts
**OAuth Client ID:** 652543258166-a2oktm9omh4v7b2i36ub6fjm28ghurqp.apps.googleusercontent.com
**API:** YouTube Data API v3
**Scope:** https://www.googleapis.com/auth/youtube.upload

**How do you use the YouTube API? (kullanım açıklaması):**
> We use the YouTube Data API v3 to upload short vertical videos (YouTube Shorts) to our
> own channel. The videos are auto-generated travel/utility guides promoting our own free
> mobile apps (Routevia, OneBag, RentFlow). We authenticate the single channel owner via
> OAuth 2.0 (offline access, refresh token) and call videos.insert. We do not access or
> store any other users' data; only our own channel is used.

**Which API methods?** videos.insert (resumable upload).

**Who are the users?** Only the channel owner (single account, our own brand channel).
We do not onboard third-party users.

**Do you store credentials securely?** Yes — refresh token stored as an encrypted GitHub
Actions secret; never exposed in code or logs.

**Content source / rights:** Video text is generated from our own website content
(coinsayfasi.github.io). Background images are either Pexels (free commercial license) or
Wikimedia Commons images whose license is verified programmatically as free (PD/CC) with
attribution shown in the video description. No copyrighted/third-party media is used.

**Compliance:** We comply with the YouTube API Services Terms of Service and Developer
Policies. No misleading metadata, no spam, unique content per video, modest daily volume.

## Süreç
- Form gönderilir → Google inceler (birkaç gün–hafta) → onaylanınca proje "audited" olur.
- Onay gelince: workflow'da privacy'yi **public** yaparız (`YT_PRIVACY=public`), eski
  unlisted videolar da public'e çevrilebilir.

## Not
Denetime kadar cron **unlisted** yüklemeye devam eder (link'le izlenebilir, warm-up).
Onay sonrası tek satır değişiklikle public'e geçilir.
