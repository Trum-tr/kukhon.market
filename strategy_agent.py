"""
Strategy Agent v1.0 — Аналитик и стратег контента
===================================================
Анализирует производительность постов в Instagram,
выявляет что работает лучше всего, обновляет стратегию
для Content Agent на следующий цикл.

Входы:
  - Instagram API: метрики последних 20 постов (лайки, комменты, охваты)
  - lead_registry.json: какие триггеры сконвертировали в лидов
  - strategy.json: текущая стратегия (для сравнения)

Выходы:
  - strategy.json: обновлённая стратегия контента
  - Telegram-отчёт с инсайтами и рекомендациями

Запуск: python strategy_agent.py
Автозапуск: оркестратор — еженедельно (каждые 7 дней)
"""

import os, json, time
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FT
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import requests

BASE = Path(__file__).parent

IG_USER    = os.getenv("IG_USERNAME")
IG_PASS    = os.getenv("IG_PASSWORD")
TG_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TG_CHAT    = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

STRATEGY_FILE = BASE / "strategy.json"
LEADS_FILE    = BASE / "lead_registry.json"
SESSION_FILE  = BASE / "ig_session.json"

# ── Утилиты ───────────────────────────────────────────────────────────────────

def tg(text: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass

def load_json(path, default):
    if Path(path).exists():
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def save_json(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )

# ── 1. Метрики Instagram ──────────────────────────────────────────────────────

def pull_post_metrics(amount=20) -> list[dict]:
    """
    Получает метрики последних N постов:
    лайки, комменты, дата, подпись, формат (карусель / видео / фото).
    """
    try:
        from instagrapi import Client
        cl = Client()
        cl.delay_range = [2, 4]

        def _load():
            if SESSION_FILE.exists():
                cl.load_settings(SESSION_FILE)
                cl.get_timeline_feed()

        with ThreadPoolExecutor(max_workers=1) as ex:
            ex.submit(_load).result(timeout=45)

        user   = cl.user_info_by_username(IG_USER)
        medias = cl.user_medias(user.pk, amount=amount)

        posts = []
        followers = max(user.follower_count, 1)
        for m in medias:
            likes    = m.like_count    or 0
            comments = m.comment_count or 0
            caption  = (m.caption_text or "")[:300]

            # Пробуем получить сохранения (только Creator/Business аккаунты)
            saves = 0
            try:
                insights = cl.insights_media(m.pk)
                saves    = insights.get("saved", 0) or 0
            except Exception:
                pass

            # Формат поста
            fmt = "carousel" if m.media_type == 8 else (
                  "video"    if m.media_type == 2 else "photo")

            # Часть дня публикации
            hour = m.taken_at.hour if hasattr(m, "taken_at") and m.taken_at else 9
            dow  = m.taken_at.strftime("%A") if hasattr(m, "taken_at") and m.taken_at else "?"

            # ER (engagement rate)
            er = round((likes + comments * 2 + saves * 3) / followers * 100, 3)

            posts.append({
                "id":       str(m.pk),
                "date":     m.taken_at.isoformat() if m.taken_at else "",
                "hour":     hour,
                "dow":      dow,
                "format":   fmt,
                "likes":    likes,
                "comments": comments,
                "saves":    saves,
                "er":       er,
                "caption":  caption,
            })

        print(f"  Получено {len(posts)} постов")
        return sorted(posts, key=lambda p: p["er"], reverse=True)

    except FT:
        print("  ОШИБКА: таймаут Instagram API")
        return []
    except Exception as e:
        print(f"  ОШИБКА Instagram: {e}")
        return []

# ── 2. Анализ лидов ───────────────────────────────────────────────────────────

def analyze_leads() -> dict:
    """Считает сколько лидов дал каждый триггер."""
    data = load_json(LEADS_FILE, [])
    triggers = {}
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for lead in data:
        if not isinstance(lead, dict):
            continue
        t    = lead.get("trigger", "?")
        date = lead.get("date", "")
        triggers[t] = triggers.get(t, {"total": 0, "week": 0})
        triggers[t]["total"] += 1
        if date >= week_ago:
            triggers[t]["week"] += 1

    return triggers

# ── 3. GPT-анализ и стратегия ─────────────────────────────────────────────────

def gpt_strategy(posts: list, leads: dict, current: dict) -> dict:
    """
    GPT-4o анализирует метрики и возвращает обновлённую стратегию.
    """
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    # Топ-5 и антитоп-5 постов
    top5  = posts[:5]
    bot5  = posts[-5:] if len(posts) >= 5 else []

    # Статистика по форматам
    fmt_stats = {}
    for p in posts:
        f = p["format"]
        if f not in fmt_stats:
            fmt_stats[f] = {"count": 0, "er_sum": 0}
        fmt_stats[f]["count"]  += 1
        fmt_stats[f]["er_sum"] += p["er"]
    fmt_avg = {f: round(v["er_sum"] / v["count"], 3)
               for f, v in fmt_stats.items() if v["count"] > 0}

    # Статистика по часам публикации
    hour_stats = {}
    for p in posts:
        h = p["hour"]
        if h not in hour_stats:
            hour_stats[h] = {"count": 0, "er_sum": 0}
        hour_stats[h]["count"]  += 1
        hour_stats[h]["er_sum"] += p["er"]
    best_hours = sorted(
        hour_stats.items(),
        key=lambda x: x[1]["er_sum"] / max(x[1]["count"], 1),
        reverse=True
    )[:3]
    best_hours_str = ", ".join(f"{h}:00" for h, _ in best_hours)

    top5_caps  = "\n".join(f"ER {p['er']}% | {p['format']} | {p['caption'][:120]}" for p in top5)
    bot5_caps  = "\n".join(f"ER {p['er']}% | {p['format']} | {p['caption'][:120]}" for p in bot5)
    leads_str  = "\n".join(f"  {t}: {v['total']} лидов ({v['week']} за неделю)"
                           for t, v in sorted(leads.items(), key=lambda x: -x[1]["total"]))

    prompt = f"""Ты стратег Instagram-аккаунта @inst.insider.ru (ниша: раскрутка Instagram).
Аккаунт публикует обучающий контент и продаёт через DM-воронку.

МЕТРИКИ ПОСЛЕДНИХ ПОСТОВ:

Топ-5 по ER:
{top5_caps or '— нет данных —'}

Антитоп-5 по ER:
{bot5_caps or '— нет данных —'}

Средний ER по форматам:
{json.dumps(fmt_avg, ensure_ascii=False)}

Лучшее время публикации по ER:
{best_hours_str or '— нет данных —'}

ЛИДЫ ПО ТРИГГЕРАМ:
{leads_str or '— нет лидов —'}

ТЕКУЩАЯ СТРАТЕГИЯ:
{json.dumps(current, ensure_ascii=False, indent=2)[:600]}

ЗАДАЧА:
Проанализируй данные и верни ОБНОВЛЁННУЮ стратегию строго в JSON без markdown:
{{
  "preferred_formats": ["carousel", "video", "photo"],
  "best_publish_hour": 9,
  "hot_topics": [
    "тема 1 — почему работает",
    "тема 2 — почему работает"
  ],
  "avoid_topics": [
    "тема которая не зашла — почему"
  ],
  "winning_triggers": ["ГАЙД", "ОХВАТЫ"],
  "tone": "casual",
  "hooks_style": "описание стиля хуков которые работают лучше всего",
  "cta_recommendation": "как улучшить призывы к действию",
  "key_insight": "главный вывод из анализа — одним предложением",
  "next_week_focus": "на чём сосредоточиться следующие 7 дней",
  "updated_at": "{datetime.now().isoformat()}"
}}

Правила:
- preferred_formats — от лучшего к худшему по ER
- hot_topics — конкретные темы, не абстракции
- winning_triggers — только те что реально дают лидов
- Если данных мало — основывайся на нише и здравом смысле"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            temperature=0.4
        )
        raw = r.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"  GPT ошибка: {e}")
        return current

# ── 4. Telegram-отчёт ─────────────────────────────────────────────────────────

def send_report(posts: list, leads: dict, strategy: dict):
    if not posts:
        tg("⚠️ <b>Strategy Agent</b>: нет данных о постах для анализа")
        return

    top = posts[0] if posts else {}
    avg_er = round(sum(p["er"] for p in posts) / len(posts), 3) if posts else 0

    leads_top = sorted(leads.items(), key=lambda x: -x[1]["total"])[:3]
    leads_str = "\n".join(f"  {t}: {v['total']} лидов" for t, v in leads_top) or "  —"

    tg(
        f"<b>📊 Strategy Agent — еженедельный анализ</b>\n"
        f"{datetime.now().strftime('%d.%m.%Y')}\n\n"

        f"<b>Анализ {len(posts)} постов:</b>\n"
        f"Средний ER: <b>{avg_er}%</b>\n"
        f"Лучший пост: ER {top.get('er',0)}% ({top.get('format','?')}) — "
        f"{top.get('caption','')[:80]}...\n\n"

        f"<b>Топ триггеры → лиды:</b>\n{leads_str}\n\n"

        f"<b>Обновлённая стратегия:</b>\n"
        f"🎯 Фокус: {strategy.get('next_week_focus','—')}\n"
        f"💡 Инсайт: {strategy.get('key_insight','—')}\n"
        f"📌 Форматы: {' > '.join(strategy.get('preferred_formats',['carousel']))}\n"
        f"⏰ Лучшее время: {strategy.get('best_publish_hour',9)}:00\n"
        f"🔥 Горячие темы:\n" +
        "\n".join(f"  • {t}" for t in strategy.get("hot_topics", [])[:3]) + "\n\n"

        f"<b>CTA-совет:</b> {strategy.get('cta_recommendation','—')[:200]}"
    )

# ── Главная функция ───────────────────────────────────────────────────────────

def run():
    print("=" * 50)
    print("  STRATEGY AGENT v1.0")
    print("=" * 50)

    # Текущая стратегия (если есть)
    current = load_json(STRATEGY_FILE, {
        "preferred_formats": ["carousel", "video", "photo"],
        "best_publish_hour": 9,
        "hot_topics": [
            "Алгоритм Instagram 2026",
            "Reels: что работает",
            "Почему падают охваты"
        ],
        "avoid_topics": [],
        "winning_triggers": ["ГАЙД", "ОХВАТЫ", "REELS"],
        "tone": "casual",
        "hooks_style": "провокационный вопрос или шокирующий факт",
        "cta_recommendation": "Пиши слово ГАЙД в директ",
        "key_insight": "Начальная стратегия",
        "next_week_focus": "Карусели про охваты и алгоритм",
        "updated_at": datetime.now().isoformat(),
    })

    # Шаг 1: Метрики постов
    print("\n[1] Получение метрик Instagram...")
    posts = pull_post_metrics(amount=20)

    # Шаг 2: Анализ лидов
    print("\n[2] Анализ лидов...")
    leads = analyze_leads()
    print(f"  Триггеров: {len(leads)}, всего лидов: {sum(v['total'] for v in leads.values())}")

    # Шаг 3: GPT-стратегия
    print("\n[3] GPT-анализ и генерация стратегии...")
    if OPENAI_KEY:
        strategy = gpt_strategy(posts, leads, current)
        print(f"  Стратегия обновлена: {strategy.get('key_insight','')}")
    else:
        print("  OPENAI_API_KEY не задан — пропуск GPT")
        strategy = current
        strategy["updated_at"] = datetime.now().isoformat()

    # Шаг 4: Сохранение
    save_json(STRATEGY_FILE, strategy)
    print(f"\n  Стратегия сохранена → strategy.json")

    # Шаг 5: Telegram-отчёт
    print("\n[4] Отправка отчёта в Telegram...")
    send_report(posts, leads, strategy)

    print("\n" + "=" * 50)
    print("  STRATEGY AGENT — ЗАВЕРШЁН")
    print("=" * 50)
    return strategy

if __name__ == "__main__":
    run()
