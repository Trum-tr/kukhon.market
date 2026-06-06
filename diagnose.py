"""
Полная диагностика системы Instagram Multi-Agent
Запуск: python diagnose.py
"""
import os, sys, json
from pathlib import Path

BASE = Path(__file__).parent

print("=" * 55)
print("  ДИАГНОСТИКА СИСТЕМЫ")
print("=" * 55)

# ── 1. .ENV ФАЙЛ ──────────────────────────────────────────
print("\n[1] ПРОВЕРКА .ENV")
env_path = BASE / ".env"
if not env_path.exists():
    print("  ОШИБКА: .env файл не найден!")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv(env_path)

keys = {
    "IG_USERNAME":    os.getenv("IG_USERNAME"),
    "IG_PASSWORD":    os.getenv("IG_PASSWORD"),
    "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN"),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
}
for k, v in keys.items():
    if not v:
        print(f"  ОТСУТСТВУЕТ: {k}")
    else:
        masked = v[:6] + "***" + v[-4:] if len(v) > 10 else "***"
        print(f"  OK  {k} = {masked}")

# ── 2. IG_SESSION ─────────────────────────────────────────
print("\n[2] ПРОВЕРКА IG_SESSION.JSON")
session = BASE / "ig_session.json"
if not session.exists():
    print("  ОШИБКА: ig_session.json не найден!")
else:
    try:
        data = json.loads(session.read_text(encoding="utf-8"))
        size = session.stat().st_size
        has_cookies = bool(data.get("cookies") or data.get("authorization_data"))
        has_uuids = bool(data.get("uuids"))
        print(f"  Размер: {size} байт")
        print(f"  UUIDs:   {'OK' if has_uuids else 'ОТСУТСТВУЕТ'}")
        print(f"  Cookies: {'OK' if has_cookies else 'ОТСУТСТВУЕТ (сессия неполная!)'}")
        if not has_cookies:
            print("  ВНИМАНИЕ: Сессия без cookies — логин не будет работать с сервера")
    except Exception as e:
        print(f"  ОШИБКА чтения: {e}")

# ── 3. TELEGRAM ───────────────────────────────────────────
print("\n[3] ПРОВЕРКА TELEGRAM BOT")
try:
    import requests
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    d = r.json()
    if d.get("ok"):
        bot = d["result"]
        print(f"  OK  Бот: @{bot.get('username')} ({bot.get('first_name')})")
    else:
        print(f"  ОШИБКА: {d.get('description')} — TOKEN неверный!")
except Exception as e:
    print(f"  ОШИБКА подключения: {e}")

# ── 4. OPENAI ─────────────────────────────────────────────
print("\n[4] ПРОВЕРКА OPENAI")
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Reply with: OK"}],
        max_tokens=5
    )
    print(f"  OK  GPT ответил: {r.choices[0].message.content.strip()}")
except Exception as e:
    print(f"  ОШИБКА: {e}")

# ── 5. INSTAGRAM SESSION ──────────────────────────────────
print("\n[5] ПРОВЕРКА INSTAGRAM СЕССИИ")
try:
    from instagrapi import Client
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FT

    SESSION_FILE = BASE / "ig_session.json"
    cl = Client()
    cl.delay_range = [1, 2]

    def test_session():
        cl.load_settings(SESSION_FILE)
        feed = cl.get_timeline_feed()
        return True

    if SESSION_FILE.exists():
        with ThreadPoolExecutor(max_workers=1) as ex:
            try:
                ex.submit(test_session).result(timeout=30)
                print(f"  OK  Сессия рабочая — аккаунт активен")
            except FT:
                print(f"  ОШИБКА: Таймаут 30с — Instagram недоступен с этого IP?")
            except Exception as e:
                print(f"  ОШИБКА сессии: {e}")
                print(f"  Сессия устарела или недействительна")
    else:
        print("  ПРОПУСК: ig_session.json не найден")

except ImportError:
    print("  ОШИБКА: instagrapi не установлен")

# ── 6. ФАЙЛЫ СИСТЕМЫ ─────────────────────────────────────
print("\n[6] ПРОВЕРКА ФАЙЛОВ")
files = [
    "orchestrator.py", "dm_agent.py", "content_agent.py",
    "instagram_agent.py", "carousel_generator.py", "video_generator.py",
    ".env", "requirements.txt"
]
for f in files:
    path = BASE / f
    status = f"OK  ({path.stat().st_size} байт)" if path.exists() else "ОТСУТСТВУЕТ!"
    print(f"  {status:30s} {f}")

# ── 7. PYTHON ПАКЕТЫ ─────────────────────────────────────
print("\n[7] ПРОВЕРКА ПАКЕТОВ")
packages = ["instagrapi", "requests", "openai", "psutil", "PIL", "dotenv"]
for pkg in packages:
    try:
        m = __import__(pkg if pkg != "PIL" else "PIL.Image", fromlist=[""])
        ver = getattr(m, "__version__", "?")
        print(f"  OK  {pkg} {ver}")
    except ImportError:
        print(f"  НЕТ: {pkg} — нужно установить!")

print("\n" + "=" * 55)
print("  ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 55)
