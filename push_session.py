# push_session.py — отправляет ig_session.json на GitHub после логина
# Запускать на Mac сразу после make_session.py

import os, sys, json, base64, subprocess
from pathlib import Path

for pkg in ["requests", "python-dotenv"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"])

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
SESSION_PATH = Path(__file__).parent / "ig_session.json"

load_dotenv(ENV_PATH)

TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO  = os.getenv("GITHUB_REPO", "")

if not TOKEN or not REPO:
    print("❌ GITHUB_TOKEN или GITHUB_REPO не найдены в .env")
    sys.exit(1)

if not SESSION_PATH.exists():
    print("❌ ig_session.json не найден. Сначала запусти make_session.py")
    sys.exit(1)

API = f"https://api.github.com/repos/{REPO}/contents/ig_session.json"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

content = base64.b64encode(SESSION_PATH.read_bytes()).decode()

# Проверяем, есть ли файл уже в репо (нужен SHA для обновления)
sha = None
r = requests.get(API, headers=HEADERS)
if r.status_code == 200:
    sha = r.json().get("sha")

payload = {
    "message": "update ig_session.json",
    "content": content,
}
if sha:
    payload["sha"] = sha

print(f"📤 Отправляю ig_session.json в {REPO}...")
r = requests.put(API, headers=HEADERS, json=payload)

if r.status_code in (200, 201):
    print("✅ Готово! Файл загружен на GitHub.")
    print()
    print("Теперь на Windows-сервере выполни:")
    print("  cd C:\\InstAgent")
    print("  python update.py")
    print()
    print("Через ~1 мин Telegram пришлёт: ✅ DM-агент: сессия восстановлена")
else:
    print(f"❌ Ошибка GitHub {r.status_code}: {r.text[:300]}")
    sys.exit(1)
