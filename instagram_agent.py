"""
Instagram Agent v3.0 — Instagrapi
===================================
Публикует карусель ИЛИ Reel в Instagram через Instagrapi.

Режимы:
  python3 instagram_agent.py           → карусель (PNG-слайды)
  python3 instagram_agent.py --reel    → Reel (MP4 с музыкой)
  python3 instagram_agent.py --auto    → автовыбор: Reel если есть reel.mp4, иначе карусель

Workflow:
  1. Берёт контент из instagram_posts/последняя_папка/
  2. Публикует с подписью из generated_content.json
  3. Уведомляет в Telegram
"""

import os, json, sys, argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import subprocess
for pkg in ["instagrapi", "requests", "pillow"]:
    try:
        __import__("PIL" if pkg == "pillow" else pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg,
                        "-q"])

from instagrapi import Client
import requests

# ── Конфиг ────────────────────────────────────────────────────────────────────
IG_USERNAME  = os.getenv("IG_USERNAME", "inst.insider.ru")
IG_PASSWORD  = os.getenv("IG_PASSWORD")
TG_TOKEN     = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

SESSION_FILE = Path(__file__).parent / "ig_session.json"
POSTS_DIR    = Path(__file__).parent / "instagram_posts"
CONTENT_F    = Path(__file__).parent / "generated_content.json"

# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(text):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"  Telegram: {e}")

# ── Instagram Client ───────────────────────────────────────────────────────────
def build_client():
    cl = Client()
    cl.delay_range = [2, 5]
    if SESSION_FILE.exists():
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USERNAME, IG_PASSWORD)
            cl.get_timeline_feed()
            print("  Сессия восстановлена")
            return cl
        except Exception:
            SESSION_FILE.unlink(missing_ok=True)
    cl.login(IG_USERNAME, IG_PASSWORD)
    cl.dump_settings(SESSION_FILE)
    print("  Новая сессия сохранена")
    return cl

# ── Подпись ───────────────────────────────────────────────────────────────────
def build_caption(is_reel=False):
    if not CONTENT_F.exists():
        return "Подпишись, чтобы не пропустить 🔥\n\n#инстаграм #smm #продвижение"
    items = json.loads(CONTENT_F.read_text(encoding="utf-8"))
    if not items:
        return ""
    item     = items[-1]
    content  = item.get("content", {})
    topic    = item.get("topic", {})
    trigger  = topic.get("trigger_word", "ГАЙД")
    caption  = content.get("caption", "")
    hashtags = content.get("hashtags", "#инстаграм #smm #продвижение")

    if not caption:
        if is_reel:
            caption = f"Смотри до конца — внутри золото 🔥 Напиши {trigger} в директ"
        else:
            caption = f"Напиши {trigger} в директ — пришлю материал бесплатно 🔥"

    cta = f"✉️ Напиши <b>{trigger}</b> в директ — пришлю бесплатно"
    if is_reel:
        cta = f"💬 Напиши {trigger} в директ — пришлю материал"

    return f"{caption}\n\n{cta}\n\n{hashtags}"

# ── Поиск последней папки ─────────────────────────────────────────────────────
def get_latest_folder(need_reel=False, need_slides=False):
    folders = sorted(POSTS_DIR.glob("*/"), reverse=True)
    for f in folders:
        if need_reel and list(f.glob("reel.mp4")):
            return f
        if need_slides and list(f.glob("slide_*.png")):
            return f
        if not need_reel and not need_slides:
            if list(f.glob("slide_*.png")) or list(f.glob("reel.mp4")):
                return f
    raise FileNotFoundError("Нет готового контента в instagram_posts/")

# ── Публикация карусели ───────────────────────────────────────────────────────
def publish_carousel(cl, folder):
    slides = sorted(folder.glob("slide_*.png"))
    if not slides:
        raise FileNotFoundError("PNG-слайды не найдены")
    print(f"  Слайдов: {len(slides)}")
    caption = build_caption(is_reel=False)
    print(f"  Режим: карусель")
    if len(slides) == 1:
        media = cl.photo_upload(slides[0], caption=caption)
    else:
        media = cl.album_upload(slides, caption=caption)
    return media, "карусель", len(slides)

# ── Публикация Reel ───────────────────────────────────────────────────────────
def publish_reel(cl, folder):
    reel = folder / "reel.mp4"
    if not reel.exists():
        raise FileNotFoundError(f"reel.mp4 не найден в {folder.name}")
    size_mb = reel.stat().st_size / 1_000_000
    print(f"  Файл: reel.mp4 ({size_mb:.1f} MB)")
    caption = build_caption(is_reel=True)
    print(f"  Режим: Reel")

    # Обложка — первый слайд
    thumbnail = folder / "slide_01_cover.png"
    if not thumbnail.exists():
        covers = list(folder.glob("slide_*.png")) + list(folder.glob("reels_cover.png"))
        thumbnail = covers[0] if covers else None

    if thumbnail:
        media = cl.clip_upload(reel, caption=caption, thumbnail=thumbnail)
    else:
        media = cl.clip_upload(reel, caption=caption)
    return media, "Reel", 1

# ── Главная функция ───────────────────────────────────────────────────────────
def publish(mode="carousel"):
    if not IG_PASSWORD:
        print("❌ IG_PASSWORD не задан в .env")
        return

    print(f"📱 Instagram Agent v3.0  [{mode.upper()}]")
    print("─" * 40)

    if mode == "auto":
        # Ищем папку с reel.mp4, если нет — публикуем карусель
        try:
            folder = get_latest_folder(need_reel=True)
            mode = "reel"
        except FileNotFoundError:
            folder = get_latest_folder(need_slides=True)
            mode = "carousel"
    elif mode == "reel":
        folder = get_latest_folder(need_reel=True)
    else:
        folder = get_latest_folder(need_slides=True)

    print(f"  Папка: {folder.name}")

    cl = build_client()

    if mode == "reel":
        media, label, count = publish_reel(cl, folder)
    else:
        media, label, count = publish_carousel(cl, folder)

    post_url = f"https://www.instagram.com/p/{media.code}/"
    print(f"  ✅ Опубликовано ({label}): {post_url}")

    emoji = "🎬" if mode == "reel" else "🖼️"
    send_telegram(
        f"{emoji} <b>Новый {label} опубликован!</b>\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"Контент: {count} {'видео' if mode == 'reel' else 'слайдов'}\n"
        f"{post_url}"
    )
    return post_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reel",     action="store_true", help="Публиковать как Reel")
    parser.add_argument("--carousel", action="store_true", help="Публиковать как карусель")
    parser.add_argument("--auto",     action="store_true", help="Автовыбор (Reel > карусель)")
    args = parser.parse_args()

    if args.reel:
        mode = "reel"
    elif args.auto:
        mode = "auto"
    else:
        mode = "carousel"

    publish(mode)
