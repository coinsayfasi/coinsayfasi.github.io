"""Pin image generation: branded vertical (1000x1500) card, optionally over a
free-license Pexels photo. Returns PNG bytes ready for Pinterest upload.

No external image is ever used except Pexels (commercial-OK, free) — so there is
no copyright risk. If no Pexels key / no result, a clean branded card is drawn.
"""
from __future__ import annotations

import io
import os
import random
import textwrap
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PIN_W, PIN_H = 1000, 1500

# Brand colors per app (matches the landing pages).
BRAND = {
    "routevia": {"bg": (11, 31, 58), "accent": (56, 189, 248), "label": "ROUTEVIA"},
    "onebag":   {"bg": (0, 98, 65),  "accent": (16, 185, 129), "label": "ONEBAG"},
    "rentflow": {"bg": (5, 150, 105), "accent": (99, 91, 255), "label": "RENTFLOW"},
    "default":  {"bg": (17, 24, 39),  "accent": (148, 163, 184), "label": "TABSERVE"},
}

_FONT_CANDIDATES_BOLD = [
    os.path.join(os.path.dirname(__file__), "assets", "font-bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",      # GitHub ubuntu runner
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",          # macOS
    "/Library/Fonts/Arial Bold.ttf",
]
_FONT_CANDIDATES_REG = [
    os.path.join(os.path.dirname(__file__), "assets", "font-regular.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for path in (_FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REG):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fetch_pexels_photo(query: str, api_key: Optional[str]) -> Optional[Image.Image]:
    """Return a portrait Pexels photo for `query`, or None. Free, commercial-OK."""
    if not api_key or not query:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "orientation": "portrait", "per_page": 15, "size": "large"},
            timeout=20,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos)  # aynı sorgu bile gelse görsel çeşitlensin
        src = photo["src"].get("portrait") or photo["src"].get("large")
        img = requests.get(src, timeout=20)
        img.raise_for_status()
        return Image.open(io.BytesIO(img.content)).convert("RGB")
    except Exception as e:  # noqa: BLE001 — never let image fetch crash the run
        print(f"[pexels] '{query}' failed: {e}")
        return None


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+crop to exactly cover w x h (like CSS background-size: cover)."""
    src_ratio, dst_ratio = img.width / img.height, w / h
    if src_ratio > dst_ratio:
        nh = h
        nw = int(h * src_ratio)
    else:
        nw = w
        nh = int(w / src_ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def build_pin_image(title: str, app: str, subtitle: str = "",
                    photo: Optional[Image.Image] = None) -> bytes:
    """Compose a 1000x1500 PNG. If `photo` given, it becomes a darkened backdrop."""
    brand = BRAND.get(app, BRAND["default"])
    canvas = Image.new("RGB", (PIN_W, PIN_H), brand["bg"])

    if photo is not None:
        bg = _cover(photo, PIN_W, PIN_H)
        # Dark gradient overlay for text legibility.
        overlay = Image.new("RGBA", (PIN_W, PIN_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(PIN_H):
            alpha = int(90 + 150 * (y / PIN_H))  # darker toward the bottom
            od.line([(0, y), (PIN_W, y)], fill=(8, 12, 24, min(alpha, 235)))
        canvas = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(canvas)

    # Accent bar + app label (top).
    draw.rectangle([(70, 90), (130, 102)], fill=brand["accent"])
    draw.text((150, 78), brand["label"], font=_font(34, bold=True), fill=brand["accent"])

    # Title — wrapped, bottom-anchored.
    title_font = _font(76, bold=True)
    wrapped = textwrap.wrap(title, width=18)[:5]
    line_h = 92
    total_h = len(wrapped) * line_h
    y = PIN_H - 230 - total_h
    for line in wrapped:
        draw.text((70, y), line, font=title_font, fill=(255, 255, 255))
        y += line_h

    # Subtitle / CTA.
    if subtitle:
        draw.text((70, PIN_H - 200), subtitle, font=_font(38, bold=False),
                  fill=(226, 232, 240))

    # Footer domain.
    draw.text((70, PIN_H - 120), "tabserve.com.tr", font=_font(30, bold=False),
              fill=brand["accent"])

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()
