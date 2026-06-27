# Google Indexing API — Kurulum (tek seferlik, ~10 dakika)

Bu otomasyon her gün **200 URL**'yi Google Indexing API'ye bildirir (manuel "İndeksleme İste"
günde ~10 ile sınırlıyken). Script + cron hazır; senin yapman gereken **tek seferlik 4 adım**:

## 1) Google Cloud'da proje + Indexing API
1. https://console.cloud.google.com → yeni proje (veya mevcut) seç.
2. **APIs & Services → Library** → "**Indexing API**" ara → **Enable**.

## 2) Service Account oluştur
1. **APIs & Services → Credentials → Create Credentials → Service account**.
2. İsim: `indexing-bot` → Create → rol vermeden Done.
3. Oluşan service account'a tıkla → **Keys → Add Key → Create new key → JSON** → indir.
   - JSON içinde bir `client_email` var (örn. `indexing-bot@PROJE.iam.gserviceaccount.com`) — bunu 3. adımda kullanacaksın.

## 3) Service Account'ı Search Console'a SAHİP (Owner) olarak ekle
> En kritik adım — bu olmadan API 403 döner.
1. https://search.google.com/search-console → `coinsayfasi.github.io` mülkü.
2. **Ayarlar → Kullanıcılar ve izinler → Kullanıcı ekle**.
3. Yukarıdaki `client_email` adresini yapıştır → izin: **Sahip (Owner)** → Ekle.

## 4) JSON key'i GitHub Secret yap
1. GitHub → `coinsayfasi/coinsayfasi.github.io` reposu → **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: **`GOOGLE_INDEXING_SA`**
3. Value: indirdiğin **JSON dosyasının tüm içeriği** (kopyala-yapıştır) → Add secret.

## Bitti ✅
- Her gün **08:30 TR**'de otomatik çalışır, 200 URL gönderir (en yeni çok dilli sayfalar önce).
- Hemen başlatmak için: repo → **Actions → "Google Indexing" → Run workflow**.
- İlerleme `state.json`'da tutulur; kota dolunca ertesi gün kalan gönderilir.
- ~1457 URL ÷ 200 ≈ **8 günde** tüm site bir kez Google'a bildirilmiş olur. Yeni sayfalar otomatik kuyruğa girer.

## Notlar
- Indexing API günlük varsayılan kota = 200/gün. Gerekirse Google Cloud'dan kota artışı istenebilir.
- Resmî olarak Indexing API "JobPosting/BroadcastEvent" içindir; genel sayfalarda da taramayı
  hızlandırdığı yaygın gözlemlenir ama Google garanti vermez. **Sitemap + iç linkler asıl yol**,
  bu onu hızlandıran ek bir sinyaldir.
- Bing/Yandex zaten IndexNow ile anlık besleniyor (ayrı, çalışıyor).
