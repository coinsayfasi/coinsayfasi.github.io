#!/usr/bin/env python3
"""SEO sayfalarından dikey YouTube Short üretici — 3 app, benzersiz içerik + rotasyon.

Her app kendi teması: Routevia (TR, Wikipedia gerçek POI fotosu), OneBag (EN, Pexels),
RentFlow (EN, Pexels). Telif-güvenli (sadece serbest lisans + atıf), Ken Burns,
crossfade geçiş, özgün ambient müzik, SEO/ASO meta + 3-app cross-promo + meta.json.

Kullanım:
  page <index.html> <out.mp4>   — verilen sayfadan üret
  app  <routevia|onebag|rentflow> <out.mp4>  — o app için SIRADAKİ kullanılmamış
                                                sayfayı seç (state.json dedup) ve üret
Env: PEXELS_API_KEY (ops), TTS_VOICE (override), SHORTS_TMP.
"""
from __future__ import annotations

import html
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
TRANS = 0.4
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SITEMAP = REPO_ROOT / "sitemap.xml"
STATE = HERE / "shorts_state.json"
SCRATCH = Path(os.environ.get("SHORTS_TMP", "/tmp/shorts_proto"))
SCRATCH.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "RouteviaShorts/1.0 (travel app; contact teknopattv@gmail.com)"}
_FREE = ("public domain", "pd-", "cc0", "cc by", "cc-by", "attribution", "no restrictions")
_NONFREE = ("fair use", "non-free", "fairuse", "copyright", "all rights reserved")

GO = "https://coinsayfasi.github.io/go"
APPS_FOOTER = (
    "\n\n📲 Download our free apps:\n\n"
    "🗺️ Routevia — trips & route planning\n"
    "   iOS: https://apps.apple.com/app/id6761003117\n"
    "   Android: https://play.google.com/store/apps/details?id=com.yunusgunes.routevia\n\n"
    "🧳 OneBag — smart packing checklist\n"
    "   iOS: https://apps.apple.com/app/id6761047805\n"
    "   Android: https://play.google.com/store/apps/details?id=com.onebag.travel\n\n"
    "🏠 RentFlow — rent & property manager\n"
    "   iOS: https://apps.apple.com/app/id6767179451\n"
    "   (Android coming soon)"
)

# ── App temaları ─────────────────────────────────────────────────────────────
THEMES = {
    "routevia": {
        "match": "/routevia-app/gezilecek-yerler/",
        "lang": "tr", "say": "Yelda", "edge": "tr-TR-EmelNeural",
        "heading": "h3", "img": "wiki",
        "brand": (8, 22, 48), "brand2": (3, 10, 26), "accent": (56, 189, 248), "label": "ROUTEVIA",
        "store": f"{GO}/routevia/",
        "intro": "{place}'da görmeniz gereken en güzel {n} yer.",
        "item": "{i}. {name}.",
        "cta_say": "{place}'da gezilecek yerlerin tamamı ve rota yorumlarda. Routevia'yı ücretsiz indir.",
        "cta_card": "Tüm liste\nyorumlarda",
        "cta_sub": "Routevia — ücretsiz indir",
        "title": "{place} Gezilecek Yerler 🚗 En Güzel {n} Yer | Routevia #shorts",
        "intro_sub": "Gezilecek En Güzel {n} Yer",
        "tags": ["{place} gezilecek yerler", "{place} gezi rehberi", "{place} tatil",
                 "gezilecek yerler", "gezi rehberi", "tatil rotası", "türkiye gezilecek yerler",
                 "seyahat", "tatil", "routevia"],
        "hashtags": "#shorts #{slug} #gezilecekyerler #gezi #tatil #seyahat #routevia",
        "desc_head": "{place} gezilecek yerler — en güzel {n} yer! 🚗 Rotanı Routevia ile planla.",
    },
    "onebag": {
        "match": "/onebag/packing-list/",
        "lang": "en", "say": "Samantha", "edge": "en-US-AriaNeural",
        "heading": "h2", "img": "pexels",
        "brand": (0, 60, 45), "brand2": (0, 25, 18), "accent": (16, 185, 129), "label": "ONEBAG",
        "store": f"{GO}/onebag/",
        "intro": "What to pack for {place} — the essentials.",
        "item": "{i}. {name}.",
        "cta_say": "The full {place} packing list is in the comments. Download OneBag free.",
        "cta_card": "Full list\nin comments",
        "cta_sub": "OneBag — free download",
        "title": "What to Pack for {place} 🧳 Carry-On Essentials | OneBag #shorts",
        "intro_sub": "Carry-On Packing Essentials",
        "tags": ["what to pack for {place}", "{place} packing list", "{place} travel",
                 "packing list", "carry on packing", "travel essentials", "travel tips",
                 "packing tips", "onebag", "travel checklist"],
        "hashtags": "#shorts #{slug} #packinglist #travel #traveltips #carryon #onebag",
        "desc_head": "What to pack for {place}? The {n} carry-on essentials. Build your list free with OneBag.",
    },
    "rentflow": {
        "match": "/rentflow/guides/",
        "lang": "en", "say": "Samantha", "edge": "en-US-AriaNeural",
        "heading": "h2", "img": "pexels",
        "brand": (5, 46, 40), "brand2": (2, 20, 18), "accent": (99, 102, 241), "label": "RENTFLOW",
        "store": f"{GO}/rentflow/",
        "intro": "{place} — {n} key steps for landlords.",
        "item": "{i}. {name}.",
        "cta_say": "The full landlord checklist is in the comments. Download RentFlow free.",
        "cta_card": "Full checklist\nin comments",
        "cta_sub": "RentFlow — free download",
        "title": "{place} 🏠 {n} Tips for Landlords | RentFlow #shorts",
        "intro_sub": "{n} Tips for Landlords",
        "tags": ["{place}", "landlord tips", "property management", "rental tips",
                 "how to be a landlord", "real estate", "rental property", "landlord advice",
                 "rentflow", "property manager"],
        "hashtags": "#shorts #landlord #realestate #propertymanagement #rentaltips #rentflow",
        "desc_head": "{place}: {n} essential tips for landlords. Manage everything with RentFlow.",
    },
}

_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_REG = ["/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(sz, bold=True):
    for p in (_BOLD if bold else _REG):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


# ── Görsel: telif-güvenli Wikipedia + Pexels ─────────────────────────────────
def _clean_artist(raw):
    """Atfı temiz, İngilizce ve profesyonel tut: HTML/çok-dilli 'own work' kalıplarını at,
    prose/uzun/yabancı görünüyorsa düş → 'Wikimedia Commons' kullanılır (Almanca sızıntısı engellenir)."""
    a = re.sub(r"<[^>]+>", " ", raw or "")
    a = re.sub(r"&[a-z]+;", " ", a)
    a = re.sub(r"https?://\S+", "", a)
    a = re.sub(r"\s+", " ", a).strip(" ,.-–—|")
    # çok dilli "own work / self" kalıpları
    a = re.sub(r"(?i)\b(eigenes werk|own work|self[- ]?photographed|own photograph|travail personnel|trabajo propio|self made|photo personnelle)\b", "", a)
    a = re.sub(r"\s+", " ", a).strip(" ,.-–—|()")
    # hâlâ cümle gibi (uzun / çok kelime / Almanca prose izleri) → düş
    if not a or len(a) > 40 or a.count(" ") > 4:
        return None
    if re.search(r"(?i)\b(und|der|die|das|von|für|mit|aufnahme|datei|foto|bild|el|la|los|de|del|une|le|du|des|et|tourisme|ville|stadt)\b", a):
        return None
    return a

def _commons_license(filename):
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php",
                         params={"action": "query", "titles": f"File:{filename}",
                                 "prop": "imageinfo", "iiprop": "extmetadata",
                                 "uselang": "en", "format": "json"},
                         headers=UA, timeout=15)
        for p in r.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0].get("extmetadata", {})
            lic_name = ii.get("LicenseShortName", {}).get("value", "") or ""
            lic = lic_name.lower()
            artist = _clean_artist(ii.get("Artist", {}).get("value", ""))
            if not lic or any(n in lic for n in _NONFREE):
                return None
            if any(f in lic for f in _FREE):
                return f"{artist or 'Wikimedia Commons'} / {lic_name} (Wikimedia Commons)"
        return None
    except Exception:
        return None


def wiki_image(query, size=1600):
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
                if not attr:
                    continue
                im = requests.get(src, headers=UA, timeout=15)
                img = Image.open(io.BytesIO(im.content)).convert("RGB")
                if min(img.size) < 700:
                    continue
                return img, attr
        except Exception as e:
            print(f"[wiki] '{query}' ({lang}): {e}")
    return None, None


def pexels_image(query):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None, None
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait", "per_page": 15}, timeout=15)
        photos = r.json().get("photos", [])
        if photos:
            ph = random.choice(photos)
            im = requests.get(ph["src"].get("portrait"), timeout=15)
            return Image.open(io.BytesIO(im.content)).convert("RGB"), f"{ph.get('photographer','')} (Pexels)"
    except Exception as e:
        print(f"[pexels] '{query}': {e}")
    return None, None


def get_bg(theme, point, place):
    if theme["img"] == "wiki":
        for q in (point, f"{point} {place}"):
            img, attr = wiki_image(q)
            if img:
                return img, attr
        return pexels_image(f"{place} turkey")
    # pexels temalı (onebag/rentflow): noktaya/şehre göre çeşitli
    q = point if theme["match"].startswith("/rentflow") else f"{place} {point}"
    img, attr = pexels_image(q)
    return (img, attr) if img else pexels_image(place)


# ── Kart çizimi ──────────────────────────────────────────────────────────────
def gradient_bg(theme):
    top, bot = theme["brand"], theme["brand2"]
    img = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3)))
    return img


def _cover(img):
    rs, rd = img.width / img.height, W / H
    if rs > rd:
        nh, nw = H, int(H * rs)
    else:
        nw, nh = W, int(W / rs)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))


def _center(d, y, text, fnt, fill, max_w=W - 160):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            t = (line + " " + word).strip()
            if d.textlength(t, font=fnt) <= max_w:
                line = t
            else:
                lines.append(line); line = word
        lines.append(line)
    lh = fnt.size + 18
    y -= len(lines) * lh // 2
    for ln in lines:
        x = (W - d.textlength(ln, font=fnt)) / 2
        d.text((x + 4, y + 4), ln, font=fnt, fill=(0, 0, 0))
        d.text((x, y), ln, font=fnt, fill=fill)
        y += lh
    return y


def card(theme, kind, place, name="", num=0, total=0, photo=None):
    acc = theme["accent"]
    if photo is not None:
        img = Image.alpha_composite(_cover(photo).convert("RGBA"),
                                    Image.new("RGBA", (W, H), (5, 12, 28, 140))).convert("RGB")
    else:
        img = gradient_bg(theme)
    d = ImageDraw.Draw(img)
    d.rectangle([(80, 120), (140, 134)], fill=acc)
    d.text((160, 104), theme["label"], font=font(40), fill=acc)
    if kind == "intro":
        L = len(place)
        fsz = 150 if L <= 10 else 112 if L <= 18 else 80 if L <= 30 else 62
        _center(d, H // 2 - 120, place, font(fsz), (255, 255, 255))
        _center(d, H // 2 + 140, theme["intro_sub"].format(n=total), font(64), acc)
    elif kind == "poi":
        d.ellipse([(W // 2 - 70, 360), (W // 2 + 70, 500)], outline=acc, width=6)
        nb = str(num)
        d.text(((W - d.textlength(nb, font=font(90))) / 2, 388), nb, font=font(90), fill=acc)
        _center(d, H // 2 + 40, name, font(92), (255, 255, 255))
        d.text((80, H - 150), f"{place} • {theme['label'].title()}", font=font(40, False), fill=(190, 205, 225))
    else:
        _center(d, H // 2 - 60, theme["cta_card"], font(110), (255, 255, 255))
        _center(d, H // 2 + 220, theme["cta_sub"], font(50), acc)
    p = SCRATCH / f"card_{kind}_{num}.png"
    img.save(p)
    return str(p)


# ── Ses / video ──────────────────────────────────────────────────────────────
def tts(theme, text, idx):
    if shutil.which("say"):
        p = SCRATCH / f"tts_{idx}.aiff"
        subprocess.run(["say", "-v", theme["say"], "-o", str(p), text], check=True)
        return str(p)
    p = SCRATCH / f"tts_{idx}.mp3"
    voice = os.environ.get("TTS_VOICE") or theme["edge"]
    subprocess.run(["edge-tts", "--voice", voice, "--text", text, "--write-media", str(p)], check=True)
    return str(p)


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip() or 2.0)


def segment(card_png, audio, idx):
    # Konuşmaya baş (0.5s) + son (0.8s) sessizlik payı → crossfade konuşmayı YEMESİN.
    d = dur(audio) + 1.3
    fr = int(d * 30)
    out = SCRATCH / f"seg_{idx}.mp4"
    vf = (f"scale=1188:2112,zoompan=z='min(1+0.0007*on,1.12)':d={fr}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", card_png, "-i", audio, "-t", f"{d:.2f}",
                    "-vf", vf, "-af", "adelay=500|500,apad", "-c:v", "libx264", "-crf", "20",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-pix_fmt", "yuv420p", str(out)],
                   check=True, capture_output=True)
    return str(out), d


def assemble(items, out_video):
    inputs = []
    for p, _ in items:
        inputs += ["-i", p]
    fc, vp, ap = [], "[0:v]", "[0:a]"
    total = items[0][1]
    for i in range(1, len(items)):
        fc.append(f"{vp}[{i}:v]xfade=transition=fade:duration={TRANS}:offset={total - TRANS:.3f}[v{i}]")
        fc.append(f"{ap}[{i}:a]acrossfade=d={TRANS}[a{i}]")
        vp, ap = f"[v{i}]", f"[a{i}]"
        total = total + items[i][1] - TRANS
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", vp, "-map", ap,
                    "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100",
                    "-pix_fmt", "yuv420p", out_video], check=True, capture_output=True)
    return total


def make_music(total, path):
    user = HERE / "assets" / "music.mp3"
    if user.exists():
        subprocess.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(user), "-t", f"{total:.2f}",
                        "-af", f"volume=0.16,afade=t=in:d=1,afade=t=out:st={total-1.5:.2f}:d=1.5",
                        "-ac", "2", path], check=True, capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=f=196:d={total:.2f}",
                        "-f", "lavfi", "-i", f"sine=f=261.63:d={total:.2f}",
                        "-f", "lavfi", "-i", f"sine=f=329.63:d={total:.2f}", "-filter_complex",
                        f"[0][1][2]amix=inputs=3:normalize=0,tremolo=f=0.15:d=0.5,aecho=0.8:0.6:900:0.3,"
                        f"lowpass=f=1100,afade=t=in:d=1.2,afade=t=out:st={total-1.8:.2f}:d=1.8,volume=0.12",
                        "-ac", "2", path], check=True, capture_output=True)


def mix_music(voice_video, music, out):
    subprocess.run(["ffmpeg", "-y", "-i", voice_video, "-i", music, "-filter_complex",
                    "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v",
                    "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-ar", "44100", out],
                   check=True, capture_output=True)


# ── İçerik çıkarma + meta ─────────────────────────────────────────────────────
_SKIP = ("faq", "build this", "manage it", "download", "indir", "sık sorulan", "sorular")


def extract_points(htmlstr, tag, n=5):
    pts = []
    for m in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", htmlstr, re.S | re.I):
        t = html.unescape(re.sub(r"<[^>]+>", "", m)).strip()
        t = re.sub(r"[^\wÇĞİÖŞÜçğıöşü .'&()/-]", "", t).strip()
        t = re.sub(r"\s+", " ", t)
        if 4 <= len(t) <= 34 and not any(s in t.lower() for s in _SKIP) and t not in pts:
            pts.append(t)
        if len(pts) >= n:
            break
    return pts


def place_of(theme, htmlstr):
    title = html.unescape(re.search(r"<title>(.*?)</title>", htmlstr, re.S | re.I).group(1))
    if theme["match"].startswith("/routevia"):
        return re.split(r"\s+Gezilecek", title)[0].strip()
    if theme["match"].startswith("/onebag"):
        m = re.search(r"(?:What to Pack for|Pack for)\s+(.+?)\s*(?:[—\-(|]|$)", title, re.I)
        return (m.group(1).strip() if m else re.split(r"\s*[|—-]", title)[0].strip())
    return re.split(r"\s*[|—]", title)[0].strip()           # rentflow: başlık


def build_meta(theme, place, points, attrs):
    n = len(points)
    slug = re.sub(r"\s+", "", place)
    title = theme["title"].format(place=place, n=n)[:100]
    pool = [t.format(place=place) for t in theme["tags"]]
    tags, tot = [], 0
    for t in pool:
        if tot + len(t) + 1 <= 480:
            tags.append(t); tot += len(t) + 1
    plist = "\n".join(f"📍 {p}" for p in points)
    hashtags = theme["hashtags"].format(slug=slug)
    credits = ("\n\nImages (free license):\n" + "\n".join(f"• {a}" for a in dict.fromkeys(attrs))) if attrs else ""
    desc = (f"{theme['desc_head'].format(place=place, n=n)}\n\n{plist}{APPS_FOOTER}\n\n{hashtags}{credits}")[:4900]
    return {"title": title, "description": desc, "tags": tags, "categoryId": "19"}


# ── Rotasyon (benzersiz içerik, tekrar yok) ──────────────────────────────────
def sitemap_urls():
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", SITEMAP.read_text(encoding="utf-8"))


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"used": []}


def url_to_local(url):
    path = re.sub(r"^https?://[^/]+/", "", url).rstrip("/")
    return REPO_ROOT / (path + "/index.html" if path else "index.html")


def pick_page(app):
    theme = THEMES[app]
    used = set(load_state()["used"])
    cands = [u for u in sitemap_urls()
             if theme["match"] in u and u not in used and url_to_local(u).exists()]
    if not cands:
        raise SystemExit(f"{app}: pinlenecek yeni sayfa yok (hepsi kullanıldı).")
    rng = random.Random(os.environ.get("SHORTS_SEED") or None)
    return rng.choice(cands)


def mark_used(url):
    st = load_state()
    if url not in st["used"]:
        st["used"].append(url)
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Ana akış ─────────────────────────────────────────────────────────────────
def build(theme, page_path, out, source_url=None):
    htmlstr = Path(page_path).read_text(encoding="utf-8", errors="ignore")
    place = place_of(theme, htmlstr)
    points = extract_points(htmlstr, theme["heading"], 7)   # daha uzun video (içerik elverdiğince)
    print(f"[{theme['label']}] {place} | {points}")
    if len(points) < 3:
        raise SystemExit("Yetersiz içerik (3'ten az nokta).")

    segs, idx, attrs = [], 0, []
    ibg, a = get_bg(theme, place, place)
    if a: attrs.append(a)
    segs.append(segment(card(theme, "intro", place, total=len(points), photo=ibg),
                        tts(theme, theme["intro"].format(place=place, n=len(points)), idx), idx)); idx += 1
    for i, name in enumerate(points, 1):
        bg, a = get_bg(theme, name, place)
        if a: attrs.append(a)
        print(f"  {i}. {name}: {'foto' if bg else 'kart'}")
        segs.append(segment(card(theme, "poi", place, name=name, num=i, total=len(points), photo=bg),
                            tts(theme, theme["item"].format(i=i, name=name), idx), idx)); idx += 1
    segs.append(segment(card(theme, "cta", place),
                        tts(theme, theme["cta_say"].format(place=place), idx), idx)); idx += 1

    voice = str(SCRATCH / "voice.mp4")
    total = assemble(segs, voice)
    user_music = HERE / "assets" / "music.mp3"
    if user_music.exists():                       # SADECE telif-temiz gerçek müzik varsa
        music = str(SCRATCH / "music.wav")
        make_music(total, music)
        mix_music(voice, music, out)
    else:                                         # müzik yok → temiz seslendirme (sentetik bip YOK)
        shutil.copy(voice, out)

    meta = build_meta(theme, place, points, attrs)
    Path(out).with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    Path(out).with_suffix(".meta.txt").write_text(
        f"TITLE ({len(meta['title'])}/100):\n{meta['title']}\n\n"
        f"DESCRIPTION ({len(meta['description'])}):\n{meta['description']}\n\n"
        f"TAGS:\n{', '.join(meta['tags'])}\n", encoding="utf-8")
    print(f"✓ Short: {out}\n✓ meta: {Path(out).with_suffix('.meta.json')}")


def theme_for_path(page_path):
    rel = "/" + str(Path(page_path).resolve().relative_to(REPO_ROOT))
    return next((t for t in THEMES.values() if t["match"] in rel), None)


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Kullanım: make_short.py [page <index.html> | app <routevia|onebag|rentflow>] <out.mp4>")
    mode, arg, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "app":
        theme = THEMES[arg]
        url = pick_page(arg)
        page = url_to_local(url)
        build(theme, page, out, source_url=url)
        mark_used(url)
    else:
        page = Path(arg)
        theme = theme_for_path(page)
        if not theme:
            raise SystemExit(f"Sayfa hiçbir temaya uymuyor: {arg}")
        build(theme, page, out)


if __name__ == "__main__":
    main()
