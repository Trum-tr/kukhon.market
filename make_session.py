# make_session.py — создаёт ig_session.json для переноса на сервер
# Запускать на Mac, подключённом к мобильному интернету (iPhone hotspot)

import os, subprocess, sys, json, time
from pathlib import Path

# ── Установка зависимостей ──────────────────────────────────────────────────
for pkg in ["instagrapi", "python-dotenv"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        print(f"Устанавливаю {pkg}...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q", "--break-system-packages"])

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, TwoFactorRequired, ChallengeRequired,
    BadPassword, UserNotFound, SelectContactPointRecoveryForm,
    RecaptchaChallengeForm
)
try:
    from instagrapi.exceptions import GeoBlockRequired
except ImportError:
    GeoBlockRequired = None

# ── Конфиг ──────────────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).parent / ".env"
SESSION_PATH = Path(__file__).parent / "ig_session.json"

load_dotenv(ENV_PATH)
USERNAME = os.getenv("IG_USERNAME", "kukhon.market")
PASSWORD = os.getenv("IG_PASSWORD", "")

if not PASSWORD:
    print("❌ IG_PASSWORD не найден в .env")
    sys.exit(1)

print("=" * 55)
print("  Instagram Session Maker")
print("=" * 55)
print(f"  Аккаунт : @{USERNAME}")
print(f"  Сессия  : {SESSION_PATH}")
print("=" * 55)
print()
print("⚠️  ВАЖНО: Mac должен быть подключён к iPhone Hotspot")
print("   (не к офисному/серверному Wi-Fi)")
print()
input("  Нажми Enter чтобы начать логин...")
print()

# ── Клиент ──────────────────────────────────────────────────────────────────
cl = Client()
cl.delay_range = [2, 5]


def challenge_code_handler(username, choice):
    """Вызывается когда Instagram требует код подтверждения."""
    method = "SMS" if choice == 1 else "Email"
    print(f"\n📲 Instagram требует подтверждение ({method})")
    code = input(f"  Введи код из {method}: ").strip()
    return code


def login_with_retry():
    # Если старая сессия есть — пробуем её переиспользовать
    if SESSION_PATH.exists():
        print("📂 Найдена старая сессия, пробую переиспользовать...")
        try:
            cl.load_settings(SESSION_PATH)
            cl.login(USERNAME, PASSWORD)
            print("✅ Старая сессия валидна!")
            return True
        except Exception:
            print("  Старая сессия устарела, делаю новый логин...")
            SESSION_PATH.unlink(missing_ok=True)

    print(f"🔑 Логин как @{USERNAME}...")

    try:
        cl.login(USERNAME, PASSWORD)
        return True

    except BadPassword:
        print("❌ Неверный пароль. Проверь IG_PASSWORD в .env")
        return False

    except UserNotFound:
        print(f"❌ Аккаунт @{USERNAME} не найден. Проверь IG_USERNAME в .env")
        return False

    except TwoFactorRequired:
        print("\n🔐 Instagram требует двухфакторную аутентификацию")
        code = input("  Введи код из приложения-аутентификатора (или SMS): ").strip()
        try:
            cl.login(USERNAME, PASSWORD, verification_code=code)
            return True
        except Exception as e:
            print(f"❌ Ошибка 2FA: {e}")
            return False

    except ChallengeRequired:
        print("\n⚠️  Instagram требует подтверждение аккаунта (Challenge)")
        print("  Выбери способ:")
        print("  1 — SMS на телефон")
        print("  2 — Email")
        choice = input("  Твой выбор (1 или 2): ").strip()
        try:
            cl.challenge_resolve(cl.last_json)
        except Exception:
            pass

        try:
            # Запрашиваем отправку кода
            method = 1 if choice == "1" else 0
            cl.challenge_send_code(method)
            code = input(f"  Введи код из {'SMS' if method == 1 else 'Email'}: ").strip()
            cl.challenge_resolve(cl.last_json, security_code=code)
            return True
        except Exception as e:
            print(f"❌ Ошибка Challenge: {e}")
            print()
            print("  Попробуй:")
            print("  1. Открой Instagram на iPhone и подтверди вход")
            print("  2. Затем запусти этот скрипт ещё раз")
            return False

    except SelectContactPointRecoveryForm as e:
        print(f"\n⚠️  Instagram требует восстановление аккаунта: {e}")
        print("  Зайди в Instagram на iPhone и верифицируй аккаунт вручную")
        return False

    except RecaptchaChallengeForm:
        print("\n❌ Instagram требует решить CAPTCHA")
        print("  Зайди в браузере на instagram.com, войди вручную, потом повтори скрипт")
        return False

    except Exception as e:
        if GeoBlockRequired and isinstance(e, GeoBlockRequired):
            print("\n❌ IP заблокирован Instagram (GeoBlock)")
            print("  Убедись, что Mac подключён к iPhone Hotspot, а не к VPS/серверу")
            return False
        err = str(e).lower()
        if "ip" in err or "blacklist" in err or "blocked" in err:
            print(f"\n❌ IP заблокирован: {e}")
            print("  Переключись на iPhone Hotspot и повтори")
        else:
            print(f"\n❌ Неизвестная ошибка: {e}")
        return False


# ── Запуск ──────────────────────────────────────────────────────────────────
success = login_with_retry()

if success:
    cl.dump_settings(SESSION_PATH)
    print()
    print("=" * 55)
    print("  ✅ СЕССИЯ СОЗДАНА УСПЕШНО")
    print("=" * 55)
    print(f"  Аккаунт : @{USERNAME}")
    print(f"  Файл    : {SESSION_PATH}")
    print()
    print("  Следующий шаг — скопировать файл на сервер:")
    print()
    print("  На Mac (в Терминале):")
    print(f'  scp "{SESSION_PATH}" Administrator@<IP_СЕРВЕРА>:C:\\InstAgent\\ig_session.json')
    print()
    print("  Или через GitHub (если scp недоступен) — спроси агента")
    print("=" * 55)
else:
    print()
    print("=" * 55)
    print("  ❌ Логин не удался")
    print("  Прочитай инструкцию INSTAGRAM_LOGIN.md")
    print("=" * 55)
    sys.exit(1)
