"""
Trends Module v2.0 — тренды для Instagram Growth ниши.
Источники: Google Trends (бесплатно) + статический список актуальных Instagram-тем.
"""

import random
import time


def get_trending_keywords(geo="RU", top_n=10):
    """
    Получает трендовые поисковые запросы по Instagram-тематике из Google Trends.
    """
    # Ключевые слова для мониторинга в нише Instagram-продвижения
    INSTAGRAM_SEED_KEYWORDS = [
        "instagram продвижение",
        "как набрать подписчиков инстаграм",
        "reels алгоритм",
        "охваты инстаграм",
        "контент план инстаграм",
    ]

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="ru-RU", tz=180, timeout=(10, 25))

        all_related = []

        # Берём похожие запросы для seed-слов
        for seed in INSTAGRAM_SEED_KEYWORDS[:3]:
            try:
                pytrends.build_payload([seed], geo=geo, timeframe="now 7-d")
                related = pytrends.related_queries()
                if related and seed in related:
                    top = related[seed].get("top")
                    if top is not None and not top.empty:
                        queries = top["query"].tolist()[:5]
                        all_related.extend(queries)
                time.sleep(2)
            except Exception:
                continue

        # Также берём общие тренды
        try:
            trending = pytrends.trending_searches(pn="russia")
            if trending is not None and not trending.empty:
                all_related.extend(trending[0].tolist()[:5])
        except Exception:
            pass

        # Дедупликация
        seen = set()
        unique = []
        for k in all_related:
            if k not in seen:
                seen.add(k)
                unique.append(k)

        return unique[:top_n] if unique else []

    except Exception as e:
        print(f"⚠️  Google Trends недоступен: {e}")
        return []


def get_instagram_topics():
    """
    Статический пул актуальных тем по Instagram-продвижению.
    Используется как fallback когда Google Trends недоступен.
    Обновляется вручную раз в месяц.
    """
    return [
        # Алгоритм
        "алгоритм Instagram 2026 — что изменилось и как адаптироваться",
        "почему Instagram снижает охваты и как это обойти",
        "как алгоритм решает кому показывать твой контент",

        # Reels
        "структура вирусного Reel: хук тело и CTA",
        "оптимальная длина Reel в 2026 году",
        "почему Reels не набирают просмотры — 5 распространённых ошибок",
        "как снимать Reels без монтажа и получать охваты",

        # Охваты
        "почему охваты упали — честный разбор причин",
        "как поднять органические охваты без рекламы",
        "время публикации постов: влияет ли оно на охваты",

        # Профиль
        "как оформить шапку профиля чтобы она продавала",
        "хайлайты которые увеличивают доверие к аккаунту",
        "как написать биографию которая конвертирует в подписчиков",

        # Контент
        "контент-план на месяц: как не выгорать и всегда иметь идеи",
        "carousel vs Reels: что работает лучше в 2026",
        "как писать подписи которые вовлекают аудиторию",
        "хэштеги в 2026: работают ли они ещё",

        # Монетизация
        "как продавать через Instagram без таргета и рекламы",
        "триггер-слова в директ: как автоматизировать продажи",
        "как превратить подписчиков в клиентов — реальная воронка",

        # Аудитория
        "как привлечь целевую аудиторию а не просто подписчиков",
        "взаимный PR и коллаборации: как найти партнёров",
        "Stories vs Reels — что лучше для роста аккаунта",
    ]


def build_trend_context(geo="RU"):
    """
    Строит контекст трендов для Research агента.
    Возвращает строку с актуальными темами.
    """
    print("🔍 Получаю тренды для Instagram-ниши...")
    keywords = get_trending_keywords(geo=geo)

    if keywords:
        print(f"✅ Google Trends: найдено {len(keywords)} запросов")
        trend_list = "\n".join(f"- {k}" for k in keywords[:8])
        return (
            f"Актуальные поисковые запросы прямо сейчас (Google Trends, RU):\n"
            f"{trend_list}\n\n"
            f"Используй это как контекст при выборе темы для Instagram-контента."
        )
    else:
        # Fallback: берём 3 случайные темы из пула
        topics = get_instagram_topics()
        chosen = random.sample(topics, min(3, len(topics)))
        print(f"ℹ️  Используем темы из статического пула")
        topics_text = "\n".join(f"- {t}" for t in chosen)
        return (
            f"Актуальные темы для Instagram-контента:\n"
            f"{topics_text}\n\n"
            f"Выбери одну из этих тем или похожую — и создай контент под неё."
        )
