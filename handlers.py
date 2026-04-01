import logging
import re
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ollama_client import generate_questions, verify_answer
from memory_storage import MemoryStorage
from models import QuizSession

router = Router()
storage = MemoryStorage()
logger = logging.getLogger(__name__)


class QuizStates(StatesGroup):
    waiting_for_answer = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для подготовки к собеседованиям.\n"
        "Просто напиши, что хочешь, например:\n"
        "«5 вопросов по Python»\n"
        "«3 вопроса по Django»\n"
        "Я сгенерирую вопросы, а ты можешь ответить одним сообщением на все.\n"
        "Позже добавлю возможность отвечать по одному."
    )


def parse_user_intent(text: str) -> tuple[str, int] | None:
    text_lower = text.lower()
    numbers = re.findall(r'\b\d+\b', text_lower)
    count = int(numbers[0]) if numbers else 3
    topic = None
    if "вопросов по" in text_lower:
        topic = text_lower.split("вопросов по")[-1].strip()
    elif "про" in text_lower:
        topic = text_lower.split("про")[-1].strip()
    elif "по" in text_lower:
        topic = text_lower.split("по")[-1].strip()
    if topic:
        topic = re.sub(r'\d+', '', topic).strip()
        return topic, count
    return None


@router.message()
async def handle_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()

    session = storage.get_session(user_id)
    if session:
        await process_answer(message, session)
        return

    intent = parse_user_intent(text)
    if intent:
        topic, count = intent
        await generate_and_send_questions(message, topic, count)
    else:
        await message.answer(
            "Не понял запрос. Попробуйте написать что-то вроде:\n"
            "«3 вопроса по Python»\n"
            "«5 популярных вопросов про Django»"
        )


async def generate_and_send_questions(message: types.Message, topic: str, count: int):
    await message.answer(f"Генерирую {count} вопросов по теме «{topic}»...")
    try:
        questions = await generate_questions(topic, count)
    except Exception as e:
        logger.exception("Generation failed")
        await message.answer(f"❌ Ошибка: {e}")
        return

    session = QuizSession(user_id=message.from_user.id, questions=questions, mode="packet")
    storage.set_session(message.from_user.id, session)

    for i, q in enumerate(questions, 1):
        text = f"*{i}. {q.question}*"
        if q.theory:
            text += f"\n\n📘 *Теория:* {q.theory}"
        await message.answer(text, parse_mode="Markdown")

    await message.answer(
        "Ответьте одним сообщением на все вопросы.\n"
        "Напишите ваши ответы (можно нумерованным списком или просто текст)."
    )


async def process_answer(message: types.Message, session: QuizSession):
    user_answer = message.text
    questions = session.questions

    results = []
    for q in questions:
        try:
            result = await verify_answer(q, user_answer)
        except Exception as e:
            logger.exception("Verification failed")
            result = None
        results.append((q, result))

    report = "📊 *Результаты проверки:*\n"
    correct_count = 0
    for idx, (q, res) in enumerate(results, 1):
        if res is None:
            report += f"{idx}. ❌ *{q.question}* — ошибка проверки.\n"
        else:
            if res.correct:
                report += f"{idx}. ✅ *{q.question}* — верно.\n"
                correct_count += 1
            else:
                report += f"{idx}. ❌ *{q.question}* — {res.explanation}\n"
    report += f"\nПравильных ответов: {correct_count} из {len(questions)}"

    await message.answer(report, parse_mode="Markdown")

    storage.delete_session(message.from_user.id)