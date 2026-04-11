import json
import logging
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
    return await generate_topics_pool(start_topic, num_topics)


async def generate_topic_theory(topic: str) -> str:
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
    user_mistakes: List[dict] = None
) -> List[Question]:
    context = ""
    if previous_questions:
        context += f"\nНе задавай вопросы, которые уже были:\n{', '.join([q['question'] for q in previous_questions])}"
    if user_mistakes:
        context += f"\nУдели особое внимание вопросам, на которые пользователь отвечал неверно: {', '.join([m['question_text'] for m in user_mistakes[:3]])}"
    prompt = f"""Сгенерируй {count} вопросов для собеседования по теме "{topic}"{context}.
Вопросы должны быть разной сложности. Для каждого вопроса предоставь JSON объект с полями:
- question: текст вопроса на русском языке
- correct_answer: правильный развёрнутый ответ на русском
- theory: краткая теория (необязательно)

Верни только валидный JSON массив."""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                raise Exception("LLM недоступна")
            data = await resp.json()
            response_text = data.get("response", "")
            cleaned = clean_json_response(response_text)
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    return [Question(**item) for item in parsed]
                else:
                    raise ValueError("Не массив")
            except Exception as e:
                logger.error(f"Ошибка генерации вопросов: {e}")
                return []