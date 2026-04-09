import json
import logging
import asyncio
from typing import List
from services.ollama_client import clean_json_response
from models.schemas import Question
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


async def generate_topic_theory(topic: str) -> str:
    """Генерирует теорию по теме для обучения (подробно, понятно)"""
    prompt = f"""Расскажи подробно о теме "{topic}" в формате урока для подготовки к собеседованию.
Выдели основные моменты, определения, примеры использования, частые вопросы на собеседованиях.
Длина: 5-7 абзацев. Пиши на русском, понятно и структурированно."""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            data = await resp.json()
            return data.get("response", f"Не удалось сгенерировать теорию по теме {topic}.")


async def generate_topic_questions(
        topic: str,
        count: int,
        previous_questions: List[dict] = None,
        user_mistakes: List[dict] = None,
        max_retries: int = 2
) -> List[Question]:
    """Генерирует вопросы с повторными попытками при ошибке JSON"""
    context = ""
    if previous_questions:
        context += f"\nНе задавай вопросы, которые уже были:\n{', '.join([q['question'] for q in previous_questions])}"
    if user_mistakes:
        context += f"\nУдели особое внимание вопросам, на которые пользователь отвечал неверно: {', '.join([m['question_text'] for m in user_mistakes[:3]])}"

    prompt = f"""Сгенерируй {count} вопросов для собеседования строго по теме "{topic}". Вопросы не должны выходить за пределы этой темы. Не задавай вопросы, требующие знаний смежных тем, если они не были явно указаны.
Вопросы должны быть разной сложности. Для каждого вопроса предоставь JSON объект с полями:
- question: текст вопроса на русском языке
- correct_answer: правильный развёрнутый ответ на русском
- theory: краткая теория (необязательно)

Верни только валидный JSON массив. Пример:
[{{"question": "Что такое GIL?", "correct_answer": "GIL — это мьютекс...", "theory": ""}}]"""

    for attempt in range(max_retries):
        try:
            payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
            async with aiohttp.ClientSession() as session:
                async with session.post(OLLAMA_URL, json=payload) as resp:
                    if resp.status != 200:
                        raise Exception("LLM недоступна")
                    data = await resp.json()
                    response_text = data.get("response", "")
                    cleaned = clean_json_response(response_text)
                    # Дополнительная очистка: удаляем всё до первого '[' и после последнего ']'
                    start = cleaned.find('[')
                    end = cleaned.rfind(']') + 1
                    if start != -1 and end != 0:
                        cleaned = cleaned[start:end]
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, list):
                        return [Question(**item) for item in parsed]
                    else:
                        raise ValueError("Не массив")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Попытка {attempt + 1} не удалась: {e}")
            if attempt == max_retries - 1:
                return []
            await asyncio.sleep(1)
    return []