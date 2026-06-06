"""
Carousel Generator v2.0
========================
Генерирует PNG-слайды карусели для Instagram.
Формат: 1080×1350 (4:5) — оптимальный для охватов в ленте.
Стиль: тёмный фон (#0d0d0d), белый текст, красный акцент (#e74c3c).
Структура: 10 слайдов (обложка + превью + 5 советов + резюме + CTA + бонус).

Запуск: python3 carousel_generator.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    os.system(f"{sys.executable} -m pip install Pillow -q")
    from PIL import Image, ImageDraw, ImageFont

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────

W, H = 1080, 1350   # 4:5 — оптимальный формат для Instagram 2026

BG    = (13,  13,  13)   # #0d0d0d
WHITE = (255, 255, 255)
RED   = (231,  76,  60)  # #e74c3c
GRAY  = (102, 102, 102)  # #666666
DARK  = (26,  26,  26)   # #1a1a1a

FONTS_DIR  = Path(__file__).parent / "fonts"
OUTPUT_DIR = Path(__file__).parent / "instagram_posts"
CONTENT_F  = Path(__file__).parent / "generated_content.json"
ACCOUNT_TAG = "@kukhon.market"

SYSTEM_FONTS = {
    "black": [
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        # Mac
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        # Локальная папка
        str(FONTS_DIR / "bold.ttf"),
    ],
    "bold": [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        str(FONTS_DIR / "bold.ttf"),
    ],
    "regular": [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        str(FONTS_DIR / "regular.ttf"),
    ],
    "light": [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibril.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        str(FONTS_DIR / "light.ttf"),
    ],
}

# ─── ИНИЦИАЛИЗАЦИЯ ────────────────────────────────────────────────────────────

def setup():
    FONTS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

def get_font(style="regular", size=40):
    paths = SYSTEM_FONTS.get(style, SYSTEM_FONTS["regular"])
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    if style == "black":
        return get_font("bold", size)
    return ImageFont.load_default()

# ─── УТИЛИТЫ ──────────────────────────────────────────────────────────────────

def wrap_text(draw, text, fnt, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=fnt) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def draw_lines(draw, lines, fnt, x, y, color, spacing=12):
    bbox = draw.textbbox((0, 0), "Ag", font=fnt)
    lh = bbox[3] - bbox[1] + spacing
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=color)
        y += lh
    return y

def draw_centered_lines(draw, lines, fnt, y, color, spacing=12):
    """Выводит строки текста по горизонтальному центру слайда."""
    bbox = draw.textbbox((0, 0), "Ag", font=fnt)
    lh = bbox[3] - bbox[1] + spacing
    for line in lines:
        tw = draw.textlength(line, font=fnt)
        x = (W - tw) // 2
        draw.text((x, y), line, font=fnt, fill=color)
        y += lh
    return y

def new_slide():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def accent_bar(draw):
    draw.rectangle([(0, 0), (10, H)], fill=RED)

def tag_bottom(draw):
    fnt = get_font("light", 26)
    tw = draw.textlength(ACCOUNT_TAG, font=fnt)
    draw.text((W - tw - 44, H - 52), ACCOUNT_TAG, font=fnt, fill=GRAY)

def red_line(draw, y):
    draw.rectangle([(44, y), (180, y + 6)], fill=RED)

# ─── СЛАЙДЫ ───────────────────────────────────────────────────────────────────

def make_cover(title: str, subtitle: str = "", pain: str = "") -> Image.Image:
    """Слайд 1 — обложка с сильным хуком."""
    img, draw = new_slide()
    accent_bar(draw)

    # Верхняя красная полоса
    draw.rectangle([(44, 80), (240, 94)], fill=RED)

    # Главный заголовок — большой, провокационный
    fnt_title = get_font("black", 88)
    lines = wrap_text(draw, title, fnt_title, W - 110)
    y = 140
    y = draw_lines(draw, lines, fnt_title, 48, y, WHITE, spacing=8)

    # Подзаголовок / угол подачи
    if subtitle:
        y += 24
        fnt_sub = get_font("regular", 38)
        sub_lines = wrap_text(draw, subtitle, fnt_sub, W - 110)
        y = draw_lines(draw, sub_lines, fnt_sub, 48, y, GRAY, spacing=6)

    # Боль аудитории в красной плашке
    if pain:
        y += 40
        fnt_pain = get_font("bold", 34)
        pain_lines = wrap_text(draw, pain, fnt_pain, W - 130)
        pain_h = len(pain_lines) * 46 + 24
        draw.rectangle([(44, y), (W - 44, y + pain_h)], fill=RED)
        draw_lines(draw, pain_lines, fnt_pain, 64, y + 12, WHITE, spacing=10)
        y += pain_h + 16

    # Свайп-подсказка внизу
    fnt_swipe = get_font("light", 30)
    swipe_text = "Свайпай →  читай до конца"
    sw = draw.textlength(swipe_text, font=fnt_swipe)
    draw.text(((W - sw) // 2, H - 120), swipe_text, font=fnt_swipe, fill=GRAY)

    # Нижний акцент
    draw.rectangle([(44, H - 90), (W - 44, H - 84)], fill=RED)
    tag_bottom(draw)
    return img


def make_preview(tips: list) -> Image.Image:
    """Слайд 2 — превью: что узнаешь из карусели."""
    img, draw = new_slide()
    accent_bar(draw)

    fnt_h = get_font("black", 52)
    draw.text((48, 80), "Что внутри:", font=fnt_h, fill=WHITE)
    red_line(draw, 148)

    fnt_item = get_font("regular", 38)
    y = 180
    for tip in tips[:5]:
        title = tip.get("title", "")
        lines = wrap_text(draw, f"→  {title}", fnt_item, W - 110)
        y = draw_lines(draw, lines, fnt_item, 48, y, WHITE, spacing=6)
        y += 18

    tag_bottom(draw)
    return img


def make_tip(num: int, title: str, body: str, example: str = "") -> Image.Image:
    """Слайды 3–7 — советы по центру + пример."""
    img, draw = new_slide()
    accent_bar(draw)

    # Декоративный номер (фон)
    fnt_bg = get_font("black", 260)
    num_str = f"0{num}"
    tw_bg = draw.textlength(num_str, font=fnt_bg)
    draw.text((W - tw_bg - 10, -40), num_str, font=fnt_bg, fill=DARK)

    # Плашка «СОВЕТ N» — по центру
    fnt_label = get_font("bold", 30)
    label = f"СОВЕТ {num}"
    lw = draw.textlength(label, font=fnt_label)
    box_x = (W - lw - 32) // 2
    draw.rectangle([(box_x, 80), (box_x + lw + 32, 122)], fill=RED)
    draw.text((box_x + 16, 84), label, font=fnt_label, fill=WHITE)

    # Заголовок — по центру
    fnt_h = get_font("black", 68)
    title_lines = wrap_text(draw, title, fnt_h, W - 120)
    y = 150
    y = draw_centered_lines(draw, title_lines, fnt_h, y, WHITE, spacing=6)

    # Разделитель по центру
    y += 24
    draw.rectangle([((W - 120) // 2, y), ((W + 120) // 2, y + 6)], fill=RED)
    y += 32

    # Тело совета — по центру
    fnt_body = get_font("regular", 38)
    body_lines = wrap_text(draw, body, fnt_body, W - 120)
    y = draw_centered_lines(draw, body_lines, fnt_body, y, WHITE, spacing=14)

    # Пример — серый блок внизу
    if example:
        y += 36
        fnt_ex_label = get_font("bold", 28)
        fnt_ex = get_font("regular", 32)
        ex_lines = wrap_text(draw, example, fnt_ex, W - 160)
        ex_h = len(ex_lines) * 44 + 64
        # Серый блок с красным левым бордером
        draw.rectangle([(44, y), (W - 44, y + ex_h)], fill=DARK)
        draw.rectangle([(44, y), (50, y + ex_h)], fill=RED)
        # Подпись "Например:"
        draw.text((68, y + 14), "Например:", font=fnt_ex_label, fill=RED)
        # Текст примера по центру
        draw_centered_lines(draw, ex_lines, fnt_ex, y + 46, GRAY, spacing=8)

    tag_bottom(draw)
    return img


def make_summary(tips: list) -> Image.Image:
    """Слайд 8 — резюме всех советов."""
    img, draw = new_slide()
    accent_bar(draw)

    fnt_h = get_font("black", 52)
    draw.text((48, 80), "Запомни главное:", font=fnt_h, fill=WHITE)
    red_line(draw, 148)

    fnt_item = get_font("bold", 34)
    fnt_body = get_font("regular", 30)
    y = 185
    for tip in tips[:5]:
        num = tip.get("num", "")
        title = tip.get("title", "")
        # Номер + заголовок
        label = f"{num}. {title}"
        lines = wrap_text(draw, label, fnt_item, W - 110)
        y = draw_lines(draw, lines, fnt_item, 48, y, RED, spacing=4)
        y += 12

    tag_bottom(draw)
    return img


def make_bonus(trigger: str) -> Image.Image:
    """Слайд 9 — бонус/тизер для директа."""
    img, draw = new_slide()

    # Красный заголовок-плашка сверху
    draw.rectangle([(0, 0), (W, 110)], fill=RED)
    fnt_bonus = get_font("black", 52)
    bonus_w = draw.textlength("БОНУС", font=fnt_bonus)
    draw.text(((W - bonus_w) // 2, 28), "БОНУС", font=fnt_bonus, fill=WHITE)

    accent_bar(draw)

    fnt_main = get_font("black", 58)
    lines = wrap_text(draw, "Хочешь разбор своего аккаунта бесплатно?", fnt_main, W - 110)
    y = 160
    y = draw_lines(draw, lines, fnt_main, 48, y, WHITE, spacing=8)

    y += 30
    fnt_desc = get_font("regular", 38)
    desc = "Напиши мне в директ — сделаю аудит и скажу что мешает расти."
    desc_lines = wrap_text(draw, desc, fnt_desc, W - 110)
    y = draw_lines(draw, desc_lines, fnt_desc, 48, y, GRAY, spacing=10)

    # Триггер
    y += 50
    fnt_trigger = get_font("black", 80)
    tw = draw.textlength(trigger, font=fnt_trigger)
    tx = (W - tw) // 2
    pad = 22
    bbox = draw.textbbox((0, 0), trigger, font=fnt_trigger)
    th = bbox[3] - bbox[1]
    draw.rectangle([(tx - pad, y - pad // 2), (tx + tw + pad, y + th + pad // 2)], fill=RED)
    draw.text((tx, y), trigger, font=fnt_trigger, fill=WHITE)

    tag_bottom(draw)
    return img


def make_cta(trigger: str, cta_text: str) -> Image.Image:
    """Слайд 10 — финальный CTA."""
    img, draw = new_slide()

    draw.rectangle([(0, 0), (W, 14)], fill=RED)
    draw.rectangle([(0, H - 14), (W, H)], fill=RED)
    accent_bar(draw)

    fnt_main = get_font("black", 66)
    cta_lines = wrap_text(draw, cta_text, fnt_main, W - 120)
    total_h = len(cta_lines) * 84
    y = H // 2 - total_h - 80
    y = draw_lines(draw, cta_lines, fnt_main, 48, y, WHITE, spacing=12)

    y += 50
    fnt_trigger = get_font("black", 100)
    tw = draw.textlength(trigger, font=fnt_trigger)
    tx = (W - tw) // 2
    pad = 26
    bbox = draw.textbbox((0, 0), trigger, font=fnt_trigger)
    th = bbox[3] - bbox[1]
    draw.rectangle([(tx - pad, y - pad // 2), (tx + tw + pad, y + th + pad // 2)], fill=RED)
    draw.text((tx, y), trigger, font=fnt_trigger, fill=WHITE)

    y += th + pad + 32
    fnt_hint = get_font("light", 30)
    hint = "← напиши это слово в директ"
    hw = draw.textlength(hint, font=fnt_hint)
    draw.text(((W - hw) // 2, y), hint, font=fnt_hint, fill=GRAY)

    tag_bottom(draw)
    return img


# ─── ГЕНЕРАЦИЯ КАРУСЕЛИ ───────────────────────────────────────────────────────

def generate_carousel(item: dict, out_dir: Path) -> list[Path]:
    topic   = item["topic"]
    content = item["content"]
    fmt     = item.get("format", "carousel")

    slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = out_dir / slug
    folder.mkdir(parents=True, exist_ok=True)

    files = []

    if fmt == "carousel":
        tips = content.get("tips", [])
        trigger = topic.get("trigger_word", "ГАЙД")

        slides_data = [
            ("01_cover",   make_cover(
                content.get("slide1_title", topic["topic"]),
                content.get("slide1_subtitle", ""),
                topic.get("pain", "")
            )),
            ("02_preview", make_preview(tips)),
        ]
        for tip in tips[:5]:
            slides_data.append((
                f"0{tip['num'] + 2}_tip{tip['num']}",
                make_tip(tip["num"], tip["title"], tip["body"], tip.get("example", ""))
            ))
        slides_data.append(("08_summary", make_summary(tips)))
        slides_data.append(("09_bonus",   make_bonus(trigger)))
        slides_data.append(("10_cta",     make_cta(
            trigger,
            content.get("cta_slide", "Напиши в директ")
        )))

        for name, slide in slides_data:
            path = folder / f"slide_{name}.png"
            slide.save(path, "PNG", quality=95)
            files.append(path)
            print(f"  ✅ {path.name}")

    elif fmt == "reels":
        trigger = topic.get("trigger_word", "ГАЙД")
        hook    = content.get("hook", topic["topic"])

        slides_data = [
            ("01_hook", make_cover(hook, "Смотри до конца →")),
        ]
        for idx, key in enumerate(["tip1", "tip2", "tip3"], start=1):
            body = content.get(key, "")
            if body:
                slides_data.append((
                    f"0{idx + 1}_tip{idx}",
                    make_tip(idx, f"Совет {idx}", body)
                ))
        cta_text = content.get("cta", f"Напиши {trigger} в директ")
        slides_data.append(("05_cta", make_cta(trigger, cta_text)))

        for name, slide in slides_data:
            path = folder / f"slide_{name}.png"
            slide.save(path, "PNG", quality=95)
            files.append(path)
            print(f"  🎬 {path.name}")

    return files


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("🎨 Carousel Generator v2.1  [1080×1350 / carousel: 10 слайдов, reels: 5 слайдов]")
    print("━" * 44)

    setup()

    if not CONTENT_F.exists():
        print("❌ generated_content.json не найден.")
        print("   Запусти: python3 content_agent.py")
        return

    items = json.loads(CONTENT_F.read_text(encoding="utf-8"))
    if not items:
        print("❌ Файл контента пуст.")
        return

    to_process = items[-3:]
    print(f"📦 Обрабатываю последние {len(to_process)} поста\n")

    all_files = []
    for i, item in enumerate(to_process, 1):
        name = item["topic"]["topic"][:55]
        fmt  = item.get("format", "carousel").upper()
        print(f"── [{i}/{len(to_process)}] {fmt}: {name}")
        try:
            files = generate_carousel(item, OUTPUT_DIR)
            all_files.extend(files)
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
        print()

    print("━" * 44)
    print(f"✅ Готово! Создано слайдов: {len(all_files)}")
    print(f"📁 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
