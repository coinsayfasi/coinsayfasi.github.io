#!/usr/bin/env python3
"""PROTOTYPE: SEO sayfasından dikey YouTube Short üret (lokal, yüklemesiz).

Routevia gezi sayfasından ilk N POI'yi çeker → markalı Ken Burns kartları +
Türkçe seslendirme (macOS `say -v Yelda`, internetsiz) + ffmpeg ile birleştirir.
Çıktı: 1080x1920 mp4. Yükleme YOK — sadece kaliteyi görmek için.

Kullanım: python3 make_short.py <page_index.html> <out.mp4>
"""
from __future__ import annotations

import html
import io
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG_TOP, BG_BOT = (8, 22, 48), (3, 10, 26)        # Routevia lacivert gradient
ACCENT = (56, 189, 248)
TRANS = 0.4                                       # segment crossfade süresi (sn)
HERE = Path(__file__).resolve().parent
SCRATCH = Path(os.environ.get("SHORTS_TMP", "/tmp/shorts_proto"))
SCRATCH.mkdir(parents=True, exist_ok=True)

_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/Library/Fonts/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_REG = ["/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(sz: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for p in (_BOLD if bold else _REG):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * f) for i in range(3)))
    return img


UA = {"User-Agent": "RouteviaShorts/1.0 (travel app; contact teknopattv@gmail.com)"}
# Telif: SADECE bu serbest lisanslar kabul. non-free/fair-use ASLA.
_FREE = ("public domain", "pd-", "cc0", "cc by", "cc-by", "attribution", "no restrictions")
_NONFREE = ("fair use", "non-free", "fairuse", "copyright", "all rights reserved")


def _commons_license(filename: str):
    """Commons'tan görselin lisansını + sanatçısını çek. Serbestse (attr) döndür, değilse None."""
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php",
                         params={"action": "query", "titles": f"File:{filename}",
                                 "prop": "imageinfo", "iiprop": "extmetadata", "format": "json"},
                         headers=UA, timeout=15)
        for p in r.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0].get("extmetadata", {})
            lic = (ii.get("LicenseShortName", {}).get("value", "") or "").lower()
            artist = re.sub(r"<[^>]+>", "", ii.get("Artist", {}).get("value", "") or "").strip()
            if not lic or any(n in lic for n in _NONFREE):
                return None                                  # güvenli değil → reddet
            if any(f in lic for f in _FREE):
                who = (artist or "Wikimedia Commons")[:60]
                return f"{who} / {ii.get('LicenseShortName', {}).get('value', '')} (Wikimedia Commons)"
        return None
    except Exception:  # noqa: BLE001
        return None


def wiki_image(query: str, size: int = 1600):
    """Wikipedia (tr→en) POI fotosu — SADECE lisansı doğrulanmış serbest görsel.
    Döner: (PIL.Image, atıf) ya da (None, None)."""
    for lang in ("tr", "en"):
        try:
            r = requests.get(f"https://{lang}.wikipedia.org/w/api.php",
                             params={"action": "query", "titles": query, "prop": "pageimages",
                                     "pithumbsize": size, "format": "json", "redirects": 1},
                             headers=UA, timeout=15)
            for p in r.json().get("query", {}).get("pages", {}).values():
                fname, src = p.get("pageimage"), p.get("thumbnail", {}).get("source")
                if not (fname and src):
                    continue
                attr = _commons_license(fname)
                if not attr:                                 # lisans serbest değil → atla
                    print(f"[telif] '{query}' görseli serbest DEĞİL → atlandı")
                    continue
                im = requests.get(src, headers=UA, timeout=15)
                img = Image.open(io.BytesIO(im.content)).convert("RGB")
                if min(img.size) < 700:                      # düşük çözünürlük → bulanık olur, atla
                    print(f"[kalite] '{query}' görseli küçük ({img.size}) → atlandı")
                    continue
                return img, attr
        except Exception as e:  # noqa: BLE001
            print(f"[wiki] '{query}' ({lang}) hata: {e}")
    return None, None


def pexels_image(query: str):
    """Pexels portre foto — ticari serbest, atıf gerekmez. Döner: (Image, atıf)|(None,None)."""
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None, None
    try:
        import random
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait", "per_page": 15}, timeout=15)
        photos = r.json().get("photos", [])
        if photos:
            ph = random.choice(photos)
            im = requests.get(ph["src"].get("portrait"), timeout=15)
            return Image.open(io.BytesIO(im.content)).convert("RGB"), f"{ph.get('photographer','')} (Pexels)"
    except Exception as e:  # noqa: BLE001
        print(f"[pexels] '{query}' hata: {e}")
    return None, None


def get_bg(poi: str, place: str):
    """Hybrid + TELİF-GÜVENLİ: Wikipedia (lisans doğrulanmış) → Pexels → (None,None).
    Döner: (Image|None, atıf|None)."""
    for q in (poi, f"{poi} {place}"):
        img, attr = wiki_image(q)
        if img:
            return img, attr
    return pexels_image(f"{place} turkey")


def _cover(img: Image.Image) -> Image.Image:
    r_src, r_dst = img.width / img.height, W / H
    if r_src > r_dst:
        nh, nw = H, int(H * r_src)
    else:
        nw, nh = W, int(W / r_src)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))


def _center_text(d, y, text, fnt, fill, max_w=W - 160):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            t = (line + " " + word).strip()
            if d.textlength(t, font=fnt) <= max_w:
                line = t
            else:
                lines.append(line)
                line = word
        lines.append(line)
    lh = fnt.size + 18
    y -= len(lines) * lh // 2
    for ln in lines:
        w = d.textlength(ln, font=fnt)
        x = (W - w) / 2
        d.text((x + 4, y + 4), ln, font=fnt, fill=(0, 0, 0))   # gölge (okunabilirlik)
        d.text((x, y), ln, font=fnt, fill=fill)
        y += lh
    return y


def card(kind: str, place: str, name: str = "", num: int = 0, total: int = 0, photo=None) -> str:
    if photo is not None:
        base = _cover(photo).convert("RGBA")
        overlay = Image.new("RGBA", (W, H), (5, 12, 28, 140))   # foto üstü karartma
        img = Image.alpha_composite(base, overlay).convert("RGB")
    else:
        img = gradient_bg()
    d = ImageDraw.Draw(img)
    # üst marka
    d.rectangle([(80, 120), (140, 134)], fill=ACCENT)
    d.text((160, 104), "ROUTEVIA", font=font(40), fill=ACCENT)
    if kind == "intro":
        _center_text(d, H // 2 - 120, place, font(150), (255, 255, 255))
        _center_text(d, H // 2 + 120, f"Gezilecek En Güzel {total} Yer", font(70), ACCENT)
    elif kind == "poi":
        # numara rozeti
        d.ellipse([(W // 2 - 70, 360), (W // 2 + 70, 500)], outline=ACCENT, width=6)
        nb = str(num)
        w = d.textlength(nb, font=font(90))
        d.text(((W - w) / 2, 388), nb, font=font(90), fill=ACCENT)
        _center_text(d, H // 2 + 40, name, font(96), (255, 255, 255))
        d.text((80, H - 150), f"{place} • Routevia", font=font(40, False), fill=(170, 190, 220))
    else:  # cta
        _center_text(d, H // 2 - 60, "Tüm rotayı\nRoutevia'da keşfet", font(110), (255, 255, 255))
        _center_text(d, H // 2 + 220, "Ücretsiz indir → App Store & Google Play", font(52), ACCENT)
    p = SCRATCH / f"card_{kind}_{num}.png"
    img.save(p)
    return str(p)


def tts(text: str, idx: int) -> str:
    p = SCRATCH / f"tts_{idx}.aiff"
    subprocess.run(["say", "-v", "Yelda", "-o", str(p), text], check=True)
    return str(p)


def dur(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip() or 2.0)


def segment(card_png: str, audio: str, idx: int):
    d = dur(audio) + 0.7                          # +0.7s sessizlik = crossfade'e pay
    fr = int(d * 30)
    out = SCRATCH / f"seg_{idx}.mp4"
    vf = (f"scale=1188:2112,zoompan=z='min(1+0.0007*on,1.12)':d={fr}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", card_png, "-i", audio,
                    "-t", f"{d:.2f}", "-vf", vf, "-c:v", "libx264", "-crf", "20",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-pix_fmt", "yuv420p",
                    "-shortest", str(out)], check=True, capture_output=True)
    return str(out), d


def assemble(items, out_video: str) -> float:
    """Segmentleri crossfade (xfade) + acrossfade ile birleştir. Döner: toplam süre."""
    n = len(items)
    inputs = []
    for p, _ in items:
        inputs += ["-i", p]
    fc, vp, ap = [], "[0:v]", "[0:a]"
    total = items[0][1]
    for i in range(1, n):
        off = total - TRANS
        fc.append(f"{vp}[{i}:v]xfade=transition=fade:duration={TRANS}:offset={off:.3f}[v{i}]")
        fc.append(f"{ap}[{i}:a]acrossfade=d={TRANS}[a{i}]")
        vp, ap = f"[v{i}]", f"[a{i}]"
        total = total + items[i][1] - TRANS
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
                    "-map", vp, "-map", ap, "-c:v", "libx264", "-crf", "20",
                    "-c:a", "aac", "-ar", "44100", "-pix_fmt", "yuv420p", out_video],
                   check=True, capture_output=True)
    return total


def make_music(total: float, path: str) -> None:
    """Müzik: assets/music.mp3 varsa onu (telif-temiz parça) kullan; yoksa özgün
    yumuşak ambient pad üret (sıfır telif riski). Düşük ses, fade'li."""
    user = HERE / "assets" / "music.mp3"
    if user.exists():
        subprocess.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(user), "-t", f"{total:.2f}",
                        "-af", f"volume=0.16,afade=t=in:d=1,afade=t=out:st={total-1.5:.2f}:d=1.5",
                        "-ac", "2", path], check=True, capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-y",
                        "-f", "lavfi", "-i", f"sine=f=196:d={total:.2f}",
                        "-f", "lavfi", "-i", f"sine=f=261.63:d={total:.2f}",
                        "-f", "lavfi", "-i", f"sine=f=329.63:d={total:.2f}",
                        "-filter_complex",
                        f"[0][1][2]amix=inputs=3:normalize=0,tremolo=f=0.15:d=0.5,"
                        f"aecho=0.8:0.6:900:0.3,lowpass=f=1100,afade=t=in:d=1.2,"
                        f"afade=t=out:st={total-1.8:.2f}:d=1.8,volume=0.12",
                        "-ac", "2", path], check=True, capture_output=True)


def mix_music(voice_video: str, music: str, out: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-i", voice_video, "-i", music, "-filter_complex",
                    "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-ar", "44100", out], check=True, capture_output=True)


def extract_pois(htmlstr: str, n: int = 5) -> list[str]:
    names = []
    for m in re.findall(r"<h3[^>]*>(.*?)</h3>", htmlstr, re.S | re.I):
        t = html.unescape(re.sub(r"<[^>]+>", "", m)).strip()
        t = re.sub(r"[^\wÇĞİÖŞÜçğıöşü .'()-]", "", t).strip()  # emoji/symbol temizle
        t = re.sub(r"\s+", " ", t)
        if 4 <= len(t) <= 32 and t not in names:
            names.append(t)
        if len(names) >= n:
            break
    return names


def build_youtube_meta(place: str, pois: list[str], attrs: list[str]) -> dict:
    """YouTube SEO/ASO metası — Keşfet'e düşmesi için keyword-zengin başlık/açıklama/etiket.
    Limitler: başlık ≤100, etiketler toplam ≤500 krk."""
    n = len(pois)
    title = f"{place} Gezilecek Yerler 🚗 En Güzel {n} Yer | Routevia #shorts"[:100]
    tag_pool = [f"{place} gezilecek yerler", f"{place} gezi", f"{place} gezi rehberi",
                f"{place} tatil", f"{place} nereye gidilir", "gezilecek yerler",
                "gezi rehberi", "tatil rotası", "türkiye gezilecek yerler",
                "seyahat", "tatil", "gezi", "routevia"]
    tags, total = [], 0
    for t in tag_pool:
        if total + len(t) + 1 <= 480:
            tags.append(t); total += len(t) + 1
    poi_lines = "\n".join(f"📍 {p}" for p in pois)
    hashtags = f"#shorts #{place.replace(' ', '')} #gezilecekyerler #gezi #tatil #seyahat #routevia"
    credits = ("\n\nGörseller (CC/serbest lisans):\n" + "\n".join(f"• {a}" for a in dict.fromkeys(attrs))) if attrs else ""
    desc = (
        f"{place} gezilecek yerler — en güzel {n} yer! 🚗 {place} gezi rehberi, "
        f"rotanı Routevia ile planla.\n\n{poi_lines}\n\n"
        f"🗺️ Tüm rotayı haritada gör + ücretsiz planla → Routevia\n"
        f"App Store & Google Play: https://coinsayfasi.github.io/go/routevia/\n\n"
        f"{hashtags}{credits}"
    )[:4900]
    return {"title": title, "description": desc, "tags": tags}


def main() -> None:
    page = Path(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else "short.mp4"
    htmlstr = page.read_text(encoding="utf-8", errors="ignore")
    title = re.search(r"<title>(.*?)</title>", htmlstr, re.S | re.I).group(1)
    place = re.split(r"\s+Gezilecek", html.unescape(title))[0].strip()
    pois = extract_pois(htmlstr, 5)
    print(f"Yer: {place} | POI'ler: {pois}")

    segs, idx, attrs = [], 0, []
    # intro — şehir fotosu
    intro_bg, a = get_bg(place, place)
    if a: attrs.append(a)
    print(f"  intro görsel: {'foto' if intro_bg else 'kart'}")
    segs.append(segment(card("intro", place, total=len(pois), photo=intro_bg),
                        tts(f"{place}'da görmeniz gereken en güzel {len(pois)} yer.", idx), idx)); idx += 1
    for i, name in enumerate(pois, 1):
        bg, a = get_bg(name, place)            # gerçek POI fotosu (lisans doğrulanmış→Pexels)
        if a: attrs.append(a)
        print(f"  {i}. {name}: {'foto' if bg else 'kart'}")
        segs.append(segment(card("poi", place, name=name, num=i, total=len(pois), photo=bg),
                            tts(f"{i}. {name}.", idx), idx)); idx += 1
    # cta — markalı kart (foto yok)
    segs.append(segment(card("cta", place),
                        tts("Tüm rotayı planlamak için Routevia'yı ücretsiz indir.", idx), idx)); idx += 1

    # Crossfade geçişlerle birleştir → müzik üret → miksle
    voice = str(SCRATCH / "voice.mp4")
    total = assemble(segs, voice)
    music = str(SCRATCH / "music.wav")
    make_music(total, music)
    mix_music(voice, music, out)
    # SEO/ASO YouTube metası → yanına .txt (yüklemede kullanılacak)
    meta = build_youtube_meta(place, pois, attrs)
    metap = Path(out).with_suffix(".meta.txt")
    metap.write_text(
        f"TITLE ({len(meta['title'])}/100):\n{meta['title']}\n\n"
        f"DESCRIPTION ({len(meta['description'])} krk):\n{meta['description']}\n\n"
        f"TAGS ({sum(len(t)+1 for t in meta['tags'])}/500 krk):\n{', '.join(meta['tags'])}\n",
        encoding="utf-8")
    print(f"✓ Short hazır: {out}")
    print(f"✓ SEO meta: {metap}")


if __name__ == "__main__":
    main()
