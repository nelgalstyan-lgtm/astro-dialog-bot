# -*- coding: utf-8 -*-
"""
Карточка профиля.

Приоритет источников:
1. Готовая карточка психотипа из assets/cards/ (<type_id>.png либо
   <type_id>_female.png / <type_id>_male.png).
2. Если готовой карточки нет — генерация "на лету" из общего референса знака.
"""
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from config import REFERENCES_DIR, FONTS_DIR, CARDS_DIR
from content import ZODIAC

CARD_SIZE = (1080, 1350)

FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"
FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"

GOLD = (201, 169, 110)
CREAM = (245, 240, 230)
DARK_OVERLAY = (10, 8, 12)


def find_static_card(type_id: str, gender: Optional[str] = None) -> Optional[Path]:
    candidates = []
    if gender:
        candidates.append(CARDS_DIR / f"{type_id}_{gender}.png")
    candidates.append(CARDS_DIR / f"{type_id}.png")
    for path in candidates:
        if path.exists():
            return path
    return None


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _load_reference(zodiac_key: str) -> Image.Image:
    path = REFERENCES_DIR / f"{zodiac_key}.png"
    return Image.open(path).convert("RGB")


def _crop_half(img: Image.Image, gender: str) -> Image.Image:
    w, h = img.size
    target_ratio = CARD_SIZE[0] / CARD_SIZE[1]

    half_w = w / 2
    if gender == "female":
        box = (0, 0, int(half_w * 1.15), h)
    else:
        box = (int(half_w * 0.85), 0, w, h)

    half = img.crop(box)
    hw, hh = half.size
    current_ratio = hw / hh

    if current_ratio > target_ratio:
        new_w = int(hh * target_ratio)
        if gender == "female":
            left = 0
        else:
            left = hw - new_w
        half = half.crop((left, 0, left + new_w, hh))
    else:
        new_h = int(hw / target_ratio)
        top = max(0, (hh - new_h) // 3)
        half = half.crop((0, top, hw, top + new_h))

    return half.resize(CARD_SIZE, Image.LANCZOS)


def _apply_bottom_gradient(img: Image.Image, height_ratio: float = 0.62) -> Image.Image:
    w, h = img.size
    gradient_h = int(h * height_ratio)
    gradient = Image.new("L", (1, gradient_h), color=0)
    for y in range(gradient_h):
        alpha = int(255 * (y / gradient_h) ** 1.6)
        gradient.putpixel((0, y), alpha)
    gradient = gradient.resize((w, gradient_h))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    black = Image.new("RGBA", (w, gradient_h), DARK_OVERLAY + (0,))
    black.putalpha(gradient)
    overlay.paste(black, (0, h - gradient_h), black)

    top_h = int(h * 0.22)
    top_grad = Image.new("L", (1, top_h), color=0)
    for y in range(top_h):
        alpha = int(150 * (1 - y / top_h))
        top_grad.putpixel((0, y), alpha)
    top_grad = top_grad.resize((w, top_h))
    top_black = Image.new("RGBA", (w, top_h), DARK_OVERLAY + (0,))
    top_black.putalpha(top_grad)
    overlay.paste(top_black, (0, 0), top_black)

    base = img.convert("RGBA")
    return Image.alpha_composite(base, overlay)


def _draw_text_centered(draw, text, y, font, fill, img_w, tracking=0):
    if tracking:
        widths = [draw.textlength(ch, font=font) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
        x = (img_w - total) / 2
        for ch, cw in zip(text, widths):
            draw.text((x, y), ch, font=font, fill=fill)
            x += cw + tracking
    else:
        w = draw.textlength(text, font=font)
        x = (img_w - w) / 2
        draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_fallback_card(zodiac_key: str, gender: str, type_data: dict) -> BytesIO:
    sign = ZODIAC[zodiac_key]
    ref = _load_reference(zodiac_key)
    cropped = _crop_half(ref, gender)
    card = _apply_bottom_gradient(cropped)

    draw = ImageDraw.Draw(card)
    w, h = card.size

    brand_font = _font(FONT_BOLD, 30)
    _draw_text_centered(draw, "ASTRO DIALOG", 56, brand_font, GOLD, w, tracking=6)

    sign_font = _font(FONT_BOLD, 64)
    sign_text = f"{sign['emoji']}  {sign['name'].upper()}"
    _draw_text_centered(draw, sign_text, 108, sign_font, CREAM, w)

    label_font = _font(FONT_REGULAR, 30)
    archetype_font = _font(FONT_BOLD, 66)
    body_font = _font(FONT_REGULAR, 34)

    y = h - 560
    _draw_text_centered(draw, "ТИП ЛИЧНОСТИ", y, label_font, GOLD, w, tracking=4)
    y += 46
    _draw_text_centered(draw, type_data["title"], y, archetype_font, CREAM, w)
    y += 96

    line_w = 90
    draw.line([(w / 2 - line_w / 2, y), (w / 2 + line_w / 2, y)], fill=GOLD, width=3)
    y += 34

    def add_block(label, text):
        nonlocal y
        _draw_text_centered(draw, label, y, label_font, GOLD, w, tracking=3)
        y += 44
        for line in _wrap_text(draw, text, body_font, w - 160):
            _draw_text_centered(draw, line, y, body_font, CREAM, w)
            y += 42
        y += 24

    add_block("ГЛАВНАЯ СИЛА", type_data["main_force"])
    add_block("ПРАВИЛО ЖИЗНИ", type_data["life_rule"])

    buf = BytesIO()
    card.convert("RGB").save(buf, format="PNG", quality=95)
    buf.seek(0)
    buf.name = f"{zodiac_key}_{type_data['id']}_{gender}.png"
    return buf


def get_profile_card(zodiac_key: str, type_data: dict, gender: str) -> BytesIO:
    static_path = find_static_card(type_data["id"], gender)
    if static_path is not None:
        buf = BytesIO(static_path.read_bytes())
        buf.seek(0)
        buf.name = static_path.name
        return buf
    return generate_fallback_card(zodiac_key, gender, type_data)
