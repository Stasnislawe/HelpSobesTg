import json
import logging
from typing import List
from services.ollama_client import clean_json_response
from config import OLLAMA_URL, OLLAMA_MODEL
import aiohttp


logger = logging.getLogger(__name__)


async def generate_topics_pool(start_topic: str, num_topics: int = 4) -> List[str] | None:
    """
    Генерирует логически связанный список тем для обучения.
    Возвращает список строк или None при ошибке.
    """
    prompt = f"""Создай учебный план из {num_topics} тем, начиная с "{start_topic}".
Темы должны логически перетекать друг в друга, образуя последовательность для fullstack/backend разработчика.
Пример: Django -> PostgreSQL -> оптимизация запросов -> Docker -> Redis -> Celery -> React.

Верни только JSON-массив строк, например:
["Django", "PostgreSQL", "Оптимизация запросов в PostgreSQL", "Docker", "Redis", "Celery", "React"]

Не добавляй пояснений, только JSON массив."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_URL, json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Ollama error generating topics: {resp.status}")
                    return None
                data = await resp.json()
                response_text = data.get("response", "")
                cleaned = clean_json_response(response_text)
                topics = json.loads(cleaned)
                if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
                    return topics[:num_topics]
                else:
                    logger.error(f"Invalid topics format: {cleaned}")
                    return None
    except Exception as e:
        logger.exception("Failed to generate topics pool")
        return None


async def regenerate_topics_pool(start_topic: str, num_topics: int = 4, previous_topics: List[str] = None) -> List[str] | None:
    """Повторная генерация пула, если пользователь не одобрил."""
    # Можно добавить в промпт указание «измени список, предложи другой вариант»
    # Пока просто вызываем ту же генерацию
    return await generate_topics_pool(start_topic, num_topics)