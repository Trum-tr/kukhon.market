"""
Research Agent v1.0 — Исследователь трендов
=============================================
Мониторит тренды в нише Instagram-маркетинга:
  1. Google Trends (pytrends) — что ищут прямо сейчас
  2. Топ-посты по хэштегам (instagrapi) — что заходит в Instagram
  3. GPT-4o синтезирует находки → готовые идеи для контента

Выходы:
  - research_results.json — сырые данные исследования
  - content_backlog.json  — очередь тем для Content Agent

Запуск: python research_agent.py
Автозапуск: оркестратор каждые 3 дня
"""

import os, json, time, re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FT
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import requests

BASE = Path(__file__).parent

IG_USER    = os.getenv("IG_USERNAME")
TG_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TG_CHAT    = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

RESEARCH_FILE = BASE / "research_results.json"
BACKLOG_FILE  = BASE / "content_backlog.json"
SESSION_FILE  = BASE / "ig_session.json"
STRATEGY_FILE = BASE / "strategy.json"

# Хэштеги для мониторинга (Instagram-маркетинг ниша)
MONITOR_HASHTAGS = [
    "instagrammarketing",
    "smm",
    "продвижениеинстаграм",
    "блогер",
    "контентмаркетинг",
    "reels",
    "охватыинстаграм",
    "инстаграммаркетинг",
]

# Ключевые слова для Google Trends (русскоязычная аудитория)
TREND_KEYWORDS = [
    "instagram алгоритм",
    "как набрать подписчиков",
    "reels продвижение",
    "охваты instagram",
    "smm 2026",
]

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

# ── 1. Google Trends ──────────────────────────────────────────────────────────

def research_google_trends() -> dict:
    """Получает данные трендов из Google Trends через pytrends."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "pip", "install", "pytrends", "-q"])
        from pytrends.request import TrendReq

    results = {"rising": [], "top": [], "related": []}
    try:
        pt = TrendReq(hl="ru-RU", tz=180, timeout=(10, 30))

        # Растущие запросы по главному ключевому слову
        pt.build_payload(["instagram продвижение"], cat=0, timeframe="now 7-d", geo="RU")

        # Похожие темы
        related = pt.related_topics()
        for kw, data in related.items():
            if data and "rising" in data and data["rising"] is not None:
                for _, row in data["rising"].head(5).iterrows():
                    results["rising"].append(row.get("topic_title", ""))

        # Похожие запросы
        queries = pt.related_queries()
        for kw, data in queries.items():
            if data and "rising" in data and data["rising"] is not None:
                for _, row in data["rising"].head(5).iterrows():
                    results["related"].append(row.get("query", ""))

        # Сравнение ключевых слов за 7 дней
        pt.build_payload(TREND_KEYWORDS[:5], timeframe="now 7-d", geo="RU")
        interest = pt.interest_over_time()
        if not interest.empty:
            avg = interest.mean().to_dict()
            results["top"] = sorted(avg.items(), key=lambda x: -x[1])

        print(f"  Google Trends: rising={len(results['rising'])}, queries={len(results['related'])}")
    except Exception as e:
        print(f"  Google Trends ошибка: {e}")

    return results

# ── 2. Instagram хэштеги ──────────────────────────────────────────────────────

def research_hashtags(max_per_tag: int = 5) -> list[dict]:
    """
    Получает топ-посты по ключевым хэштегам через Instagram.
    Возвращает список постов с caption, лайками, комментами.
    """
    posts = []
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

        for tag in MONITOR_HASHTAGS[:5]:  # ограничиваем чтобы не заблочили
            try:
                medias = cl.hashtag_medias_top(tag, amount=max_per_tag)
                for m in medias:
                    caption = (m.caption_text or "")[:400]
                    if len(caption) < 30:
                        continue
                    posts.append({
                        "hashtag": tag,
                        "likes":    m.like_count or 0,
                        "comments": m.comment_count or 0,
                        "caption":  caption,
                        "format":   "carousel" if m.media_type == 8 else (
                                    "video" if m.media_type == 2 else "photo"),
                    })
                time.sleep(3)  # пауза между хэштегами
                print(f"  #{tag}: {len(medias)} постов")
            except Exception as e:
                print(f"  #{tag} ошибка: {e}")

    except FT:
        print("  Instagram: таймаут при загрузке сессии")
    except Exception as e:
        print(f"  Instagram ошибка: {e}")

    return posts

# ── 3. GPT-синтез → контент-идеи ─────────────────────────────────────────────

def gpt_synthesize(trends: dict, posts: list, strategy: dict) -> list[dict]:
    """
    GPT-4o анализирует тренды и топ-посты,
    возвращает список готовых идей для Content Backlog.
    """
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    # Готовим данные
    rising_str  = ", ".join(filter(None, trends.get("rising", [])))[:300]
    related_str = ", ".join(filter(None, trends.get("related", [])))[:300]
    top_str     = "\n".join(f"  {kw}: {round(v,1)}" for kw, v in trends.get("top", [])[:5])

    # Топ-5 постов по вовлечённости
    top_posts = sorted(posts, key=lambda p: p["likes"] + p["comments"] * 2, reverse=True)[:5]
    posts_str = "\n".join(
        f"  [{p['format']}] {p['likes']}❤ {p['comments']}💬 | {p['caption'][:120]}"
        for p in top_posts
    )

    strategy_focus = strategy.get("next_week_focus", "")
    hot_topics     = "\n".join(strategy.get("hot_topics", [])[:3])
    pref_format    = strategy.get("preferred_formats", ["carousel"])[0]
    triggers       = ", ".join(strategy.get("winning_triggers", ["ГАЙД", "ОХВАТЫ"]))

    prompt = f"""Ты Research Agent Instagram-аккаунта @kukhon.market.
Ниша: обучающий контент по раскрутке Instagram для блогеров и экспертов.
Монетизация: DM-воронка → платные консультации и гайды.

ДАННЫЕ GOOGLE TRENDS (последние 7 дней, Россия):
Растущие темы: {rising_str or '— нет данных —'}
Популярные запросы: {related_str or '— нет данных —'}
Рейтинг ключевых слов:
{top_str or '— нет данных —'}

ТОП-ПОСТЫ ПО ХЭШТЕГАМ КОНКУРЕНТОВ:
{posts_str or '— нет данных —'}

ТЕКУЩАЯ СТРАТЕГИЯ:
Фокус недели: {strategy_focus}
Горячие темы (высокий ER): {hot_topics}
Предпочтительный формат: {pref_format}
Конвертирующие триггеры: {triggers}

ЗАДАЧА:
Найди 6 КОНКРЕТНЫХ тем для публикаций на следующие 7 дней.
Приоритет — темы которые сейчас в тренде И подходят под нашу нишу.

Верни строго JSON массив без markdown:
[
  {{
    "topic": "Конкретная тема поста (не абстрактная)",
    "angle": "Неожиданный или провокационный угол подачи",
    "pain": "Боль аудитории которую решает этот контент",
    "format": "carousel или reels",
    "trigger_word": "одно слово (ГАЙД / ОХВАТЫ / REELS / РАЗБОР / ПЛАН)",
    "priority": 8,
    "reason": "почему эта тема актуальна прямо сейчас"
  }}
]

Правила:
- Темы должны быть конкретными: не 'алгоритм Instagram' а '3 изменения алгоритма которые убивают охваты в 2026'
- priority от 1 до 10 (10 = максимально актуально прямо сейчас)
- Учитывай что уже хорошо работало (горячие темы стратегии)
- Ориентируйся на тренды из Google и то что набирает лайки у конкурентов"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.7
        )
        raw = r.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ideas = json.loads(raw)
        print(f"  GPT сгенерировал {len(ideas)} идей")
        return ideas
    except Exception as e:
        print(f"  GPT ошибка: {e}")
        return []

# ── 4. Обновление Content Backlog ─────────────────────────────────────────────

def update_backlog(ideas: list) -> int:
    """
    Добавляет новые идеи в content_backlog.json.
    Не дублирует темы которые уже есть.
    Возвращает количество добавленных.
    """
    backlog = load_json(BACKLOG_FILE, [])

    # Существующие темы для проверки дублей
    existing_topics = {item.get("topic", "").lower() for item in backlog}

    added = 0
    for idea in ideas:
        topic = idea.get("topic", "")
        if not topic or topic.lower() in existing_topics:
            continue
        backlog.append({
            "id":         f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{added}",
            "created_at": datetime.now().isoformat(),
            "source":     "research_agent",
            "topic":      topic,
            "angle":      idea.get("angle", ""),
            "pain":       idea.get("pain", ""),
            "format":     idea.get("format", "carousel"),
            "trigger_word": idea.get("trigger_word", "ГАЙД"),
            "priority":   idea.get("priority", 5),
            "reason":     idea.get("reason", ""),
            "status":     "pending",
            "used_at":    None,
        })
        existing_topics.add(topic.lower())
        added += 1

    # Сортируем по приоритету
    backlog.sort(key=lambda x: (x.get("status") == "used", -x.get("priority", 0)))

    save_json(BACKLOG_FILE, backlog)
    print(f"  Backlog: добавлено {added} идей, всего {len(backlog)}")
    return added

# ── 5. Telegram-отчёт ─────────────────────────────────────────────────────────

def send_report(trends: dict, posts: list, ideas: list, added: int):
    if not ideas:
        tg("⚠️ <b>Research Agent</b>: не удалось сгенерировать идеи")
        return

    # Топ-3 идеи по приоритету
    top3 = sorted(ideas, key=lambda x: -x.get("priority", 0))[:3]
    ideas_str = "\n".join(
        f"  {i+1}. [{x.get('format','?').upper()}] <b>{x['topic']}</b>\n"
        f"     → {x.get('reason','')[:80]}"
        for i, x in enumerate(top3)
    )

    rising = ", ".join(filter(None, trends.get("rising", [])))[:150] or "—"
    hashtag_count = len(posts)

    tg(
        f"<b>🔍 Research Agent — отчёт</b>\n"
        f"{datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Источники:</b>\n"
        f"📈 Google Trends: растущие темы — {rising}\n"
        f"📱 Instagram хэштеги: проанализировано {hashtag_count} постов\n\n"
        f"<b>Топ-3 идеи в Content Backlog:</b>\n"
        f"{ideas_str}\n\n"
        f"✅ Добавлено в очередь: <b>{added}</b> новых тем\n"
        f"<i>Content Agent возьмёт их при следующей публикации</i>"
    )

# ── Главная функция ───────────────────────────────────────────────────────────

def run():
    print("=" * 52)
    print("  RESEARCH AGENT v1.0")
    print("=" * 52)

    strategy = load_json(STRATEGY_FILE, {})

    # Шаг 1: Google Trends
    print("\n[1] Google Trends...")
    trends = research_google_trends()

    # Шаг 2: Instagram хэштеги
    print("\n[2] Instagram хэштеги...")
    posts = research_hashtags(max_per_tag=5)
    print(f"  Всего постов: {len(posts)}")

    # Шаг 3: GPT-синтез
    print("\n[3] GPT-синтез идей...")
    ideas = []
    if OPENAI_KEY:
        ideas = gpt_synthesize(trends, posts, strategy)
    else:
        print("  OPENAI_API_KEY не задан — пропуск")

    # Шаг 4: Сохраняем raw-результаты
    research = {
        "date":       datetime.now().isoformat(),
        "trends":     trends,
        "posts_count": len(posts),
        "top_posts":  sorted(posts, key=lambda p: p["likes"], reverse=True)[:10],
        "ideas":      ideas,
    }
    save_json(RESEARCH_FILE, research)

    # Шаг 5: Content Backlog
    print("\n[4] Обновляю Content Backlog...")
    added = update_backlog(ideas)

    # Шаг 6: Telegram
    print("\n[5] Отправка отчёта...")
    send_report(trends, posts, ideas, added)

    print("\n" + "=" * 52)
    print(f"  RESEARCH AGENT — завершён. Добавлено: {added} идей")
    print("=" * 52)
    return ideas

if __name__ == "__main__":
    run()
