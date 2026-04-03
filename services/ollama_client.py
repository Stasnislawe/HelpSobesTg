import aiohttp
import json
import logging
import re
from typing import List
from models.schemas import Question, VerificationResult
from config import OLLAMA_URL, OLLAMA_MODEL


logger = logging.getLogger(__name__)


def clean_json_response(response_text: str) -> str:
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*', '', response_text)
    return response_text.strip()


async def generate_quiz_questions(topic: str, count: int) -> List[Question]:
    """Генерирует вопросы с ответами (скрытыми от пользователя)"""
    prompt = f"""Сгенерируй {count} вопросов для собеседования на тему "{topic}".
Для каждого вопроса предоставь JSON объект с полями:
- question: текст вопроса на русском языке
- correct_answer: правильный развёрнутый ответ на русском
- theory: краткая теория (необязательно, но можно оставить пустой строкой)

Верни только валидный JSON массив.
Пример:
[
  {{
    "question": "Что такое декоратор в Python?",
    "correct_answer": "Декоратор — это функция, которая принимает другую функцию и расширяет её поведение.",
    "theory": ""
  }}
]"""
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
                logger.error(f"Ошибка парсинга: {e}\nОтвет: {cleaned}")
                raise Exception("Ошибка обработки ответа от LLM")


async def generate_questions_with_answers(topic: str, count: int) -> List[dict]:
    prompt = f"""Сгенерируй {count} вопросов по теме "{topic}" вместе с правильными ответами.
Формат: JSON массив объектов с полями "question" и "answer".
Вопросы сложные, ответы развёрнутые на русском.
Пример: [{{"question": "Что такое GIL в Python?", "answer": "Global Interpreter Lock – мьютекс..."}}]"""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            data = await resp.json()
            response_text = data.get("response", "")
            cleaned = clean_json_response(response_text)
            try:
                return json.loads(cleaned)
            except:
                return []


async def generate_theory(topic: str) -> str:
    prompt = f"""Расскажи подробно о теме "{topic}" в формате краткого конспекта для собеседования.
Выдели основные моменты, определения, примеры. Длина 5-7 абзацев. На русском."""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            data = await resp.json()
            return data.get("response", "Не удалось сгенерировать теорию.")


async def verify_answer(question: Question, user_answer: str) -> VerificationResult:
    prompt = f"""Вопрос: {question.question}
Правильный ответ: {question.correct_answer}
Ответ пользователя: {user_answer}

Определи, правильный ли ответ (или частично). Верни JSON:
{{"correct": true/false, "explanation": "краткий отзыв на русском"}}"""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                raise Exception("LLM недоступна")
            data = await resp.json()
            response_text = data.get("response", "")
            cleaned = clean_json_response(response_text)
            try:
                result = json.loads(cleaned)
                return VerificationResult(**result)
            except:
                return VerificationResult(correct=False, explanation="Ошибка проверки ответа.")


async def parse_intent_via_llm(user_text: str) -> dict:
    """Возвращает словарь с полями: intent, topic, count, with_answers, intensive_topic"""
    prompt = f"""Проанализируй запрос пользователя и определи его намерение.
Запрос: "{user_text}"

Верни JSON в точности с полями:
- intent: одно из "quiz", "qa", "theory", "intensive"
- topic: строка с темой (например, "python", "django") или пустая строка, если не указана
- count: целое число (количество вопросов, если указано, иначе null)
- with_answers: булево (true если пользователь хочет вопросы с ответами, иначе false)
- intensive_topic: строка (тема для интенсива, если intent="intensive", иначе null)

Примеры:
"5 вопросов по python" -> {{"intent": "quiz", "topic": "python", "count": 5, "with_answers": false, "intensive_topic": null}}
"расскажи про джанго" -> {{"intent": "theory", "topic": "django", "count": null, "with_answers": false, "intensive_topic": null}}
"3 вопроса по js с ответами" -> {{"intent": "qa", "topic": "js", "count": 3, "with_answers": true, "intensive_topic": null}}
"повтори мои ошибки по python" -> {{"intent": "intensive", "topic": null, "count": null, "with_answers": false, "intensive_topic": "python"}}
"/intensive" -> {{"intent": "intensive", "topic": null, "count": null, "with_answers": false, "intensive_topic": null}}

Верни только JSON, без пояснений."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                logger.error(f"Ollama error in intent parsing: {resp.status}")
                return None
            data = await resp.json()
            response_text = data.get("response", "")
            cleaned = clean_json_response(response_text)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse intent JSON: {e}\nResponse: {cleaned}")
                return None