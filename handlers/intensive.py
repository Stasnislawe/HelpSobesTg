import logging
import asyncio
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from services.db_service import get_user_mistakes, get_user, create_user, create_quiz_attempt
from services.ollama_client import generate_quiz_questions
from models.schemas import QuizSessionData, Question
from handlers.quiz import start_quiz_session
from utils.helpers import safe_send, escape_markdown


router = Router()
logger = logging.getLogger(__name__)
MAX_ITEMS_PER_REQUEST = 10


@router.message(Command("intensive"))
async def cmd_intensive(message: types.Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    topic = args[1] if len(args) > 1 else None

    mistakes = await get_user_mistakes(message.from_user.id, topic, limit=5)
    if not mistakes:
        await safe_send(
            message,
            "❌ У вас нет ошибочных вопросов по этой теме.\n"
            "Попробуйте сначала ответить на несколько вопросов в обычном режиме."
        )
        return

    # Вопросы из ошибок
    old_questions = [
        Question(question=m["question_text"], correct_answer=m["correct_answer"], theory=None)
        for m in mistakes
    ]

    # Новые вопросы (до 2 штук)
    new_questions = []
    if topic:
        try:
            new_questions = await generate_quiz_questions(topic, count=2)
        except Exception as e:
            logger.exception("Failed to generate new questions for intensive")

    all_questions = old_questions + new_questions
    if len(all_questions) > MAX_ITEMS_PER_REQUEST:
        all_questions = all_questions[:MAX_ITEMS_PER_REQUEST]

    user = await get_user(message.from_user.id)
    if not user:
        user = await create_user(message.from_user.id)

    attempt_id = await create_quiz_attempt(
        message.from_user.id,
        topic or "intensive",
        len(all_questions)
    )

    session_data = QuizSessionData(
        user_id=message.from_user.id,
        questions=all_questions,
        mode=user.mode,
        current_index=0,
        attempt_id=attempt_id,
        topic=topic or "intensive"
    )
    await state.update_data(quiz=session_data.dict())

    # Отправляем приветственное сообщение
    intro_text = (
        f"🔥 *Интенсивный режим*\n"
        f"Повторяем {len(old_questions)} вопрос(ов), на которые вы ошиблись ранее.\n"
        f"Всего вопросов: {len(all_questions)}.\n"
        f"Режим: {'последовательный' if user.mode == 'sequential' else 'пакетный'}.\n"
        f"Удачи!"
    )
    safe_intro = escape_markdown(intro_text)
    await safe_send(message, safe_intro, parse_mode="MarkdownV2")

    await start_quiz_session(message, state, session_data)