# Pinterest Standard Access — Demo Video Runbook

**Neden:** İlk başvuru reddedildi. Sebep (Eloise / API Ops):
1. Slideshow göndermişiz, **kesintisiz tam video** değil.
2. **OAuth akışı** videoda görünmüyor.
3. **API kullanımı** videoda görünmüyor.

Bu sefer **gerçek, kesintisiz bir ekran kaydı** çekeceğiz. Trial production'da pin
atamadığı için (403 code 29) demo'yu **Sandbox**'ta yapıyoruz — Eloise de bunu
söyledi. Video **5 dakikadan kısa** olmalı (hedef ~2-3 dk).

---

## Hazırlık (çekimden önce)

1. **App secret'ı al:** Pinterest developer console → App `1581587` → "App secret key".
2. Tarayıcıda **Pinterest hesabına giriş yapmış ol** (consent ekranı hızlı gelsin).
3. Terminali ve tarayıcıyı yan yana, büyük fontla aç (kayıtta okunsun).
4. Klasöre gir:
   ```
   cd ~/Desktop/02_Projeler/coinsayfasi.github.io/_automation/pinterest
   ```

## Çekim (ekran kaydını BAŞLAT — macOS: Cmd+Shift+5 → Record)

> Kaydı **tek seferde, kesintisiz** çek. Kes/yapıştır YOK.

**1) OAuth — auth URL'yi üret ve göster**
```
python3 sandbox_demo.py url
```
Çıkan `https://www.pinterest.com/oauth/?...` URL'sini **kopyala, tarayıcıda aç**.

**2) OAuth — izin ver (kayıtta net görünmeli)**
- Pinterest **login / "Authorize app"** ekranı görünür.
- Kırmızı **"Give access"** butonuna bas.
- Tarayıcı `https://coinsayfasi.github.io/?code=XXXX&state=tabserve` adresine düşer.
- **Adres çubuğundaki `code=` değerini** birkaç saniye göster (zoom iyi olur), sonra kopyala.

**3) Token exchange + Pin oluştur + geri oku — TEK komut, canlı**
```
PINTEREST_APP_SECRET=BURAYA_SECRET python3 sandbox_demo.py run KOPYALADIGIN_KOD
```
Terminal sırayla şunu basar (hepsi kayıtta):
- ADIM 2: `POST /v5/oauth/token` → ✓ Access token alındı
- ADIM 3: board ensure → `POST /v5/pins` → ✓ PIN OLUŞTURULDU id: ...
- ADIM 4: `GET /v5/pins/{id}` → pin alanları (title, board_id, link, created_at)

**4) Kaydı DURDUR.** (Toplam ~2-3 dk.) `.mov`'u `.mp4`'e çevirmek istersen:
```
ffmpeg -i kayit.mov -vcodec libx264 -crf 23 pinterest_standard_demo.mp4
```

---

## Başvuruyu yeniden gönder

1. Pinterest console → App `1581587` → **Upgrade to Standard access**.
2. Yeni videoyu yükle (`pinterest_standard_demo.mp4`).
3. Açıklama alanına kısaca: *"Full uncut screen recording showing the complete OAuth
   flow (consent + redirect with authorization code), the token exchange API call, and
   live API usage (creating a Pin and reading it back), performed in the Sandbox
   environment per your guidance."*
4. Eloise'in mesaj thread'ine de cevap at (taslak: `REPLY_TO_ELOISE.txt`).

---

## Sorun çıkarsa

- **`code=` görünmüyor / sayfa hata:** redirect_uri kayıtlı `https://coinsayfasi.github.io/`
  ile birebir aynı olmalı (sonundaki `/` dahil). URL bar'da kod yine de var.
- **Bağlantı/timeout (`api-sandbox.pinterest.com`):** WiFi içerik filtresine takılıyor
  olabilir → filtresiz ağ / telefon hotspot'unda çek.
- **`401/403` token exchange'de:** App secret yanlış ya da kod süresi geçmiş
  (kod tek kullanımlık + kısa ömürlü) — auth URL'yi tekrar açıp taze kod al.
- **Pin başka hesapta görünmüyor:** normal, sandbox pin'leri yalnızca sana görünür;
  GET ile geri okumak Pinterest için yeterli kanıt.
