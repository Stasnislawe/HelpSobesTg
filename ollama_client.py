import aiohttp
import json
import logging
from typing import List
from models import Question, VerificationResult


logger = logging.getLogger(__name__)


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gpt-oss:20b-cloud"  # замените на вашу модель


async def generate_questions(topic: str, count: int) -> List[Question]:
    prompt = f"""Generate {count} interview questions about {topic}. 
For each question, provide:
- question: the question text
- correct_answer: a detailed explanation of the correct answer
- theory: optional theoretical background

Return only valid JSON array with these fields. Example:
[
  {{
    "question": "What is a decorator in Python?",
    "correct_answer": "A decorator is a function that takes another function and extends its behavior without explicitly modifying it.",
    "theory": "Decorators are syntactic sugar for higher-order functions..."
  }}
]"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                logger.error(f"Ollama error: {resp.status}")
                raise Exception("LLM недоступна")
            data = await resp.json()
            response_text = data.get("response", "")
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, list):
                    return [Question(**item) for item in parsed]
                else:
                    raise ValueError("Response is not a list")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse LLM response: {e}\nResponse: {response_text}")
                raise Exception("Ошибка обработки ответа от LLM")


async def verify_answer(question: Question, user_answer: str) -> VerificationResult:
    prompt = f"""Question: {question.question}
Correct answer: {question.correct_answer}
User answer: {user_answer}

Determine if the user's answer is correct or partially correct. Return JSON:
{{"correct": true/false, "explanation": "brief feedback"}}"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                logger.error(f"Ollama error: {resp.status}")
                raise Exception("LLM недоступна")
            data = await resp.json()
            response_text = data.get("response", "")
            try:
                result = json.loads(response_text)
                return VerificationResult(**result)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse verification: {e}\nResponse: {response_text}")
                return VerificationResult(
                    correct=False,
                    explanation="Не удалось проверить ответ. Пожалуйста, попробуйте ещё раз."
                )