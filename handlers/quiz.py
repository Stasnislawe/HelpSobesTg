import logging
from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery

from services.ollama_client import (
    generate_quiz_questions,
    verify_answer,
    generate_theory,
    generate_questions_with_answers
)
from models.schemas import QuizSessionData, Question
from services.db_service import (
    get_user, create_user, create_quiz_attempt, save_answer, finish_quiz_attempt
)
from utils.intent_parser import parse_intent
from keyboards.inline import quiz_control_keyboard

logger = logging.getLogger(__name__)
router = Router()


class QuizStates(StatesGroup):
    waiting_for_sequential_answer = State()


@router.message(Command("cancel"))
async def cancel_quiz(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Текущий тест отменён.")


@router.message()
async def handle_message(message: types.Message, state: FSMContext):
    if await state.get_state() == QuizStates.waiting_for_sequential_answer.state:
        await process_sequential_answer(message, state)
        return

    intent, topic, count = parse_intent(message.text)
    if not topic:
        await message.answer("Не понял тему. Примеры:\n• 4 вопроса по python\n• расскажи про джанго\n• 3 вопроса по js с ответами")
        return

    if intent == "theory":
        await send_theory(message, topic)
    elif intent == "qa":
        if count is None:
            count = 3
        await send_qa(message, topic, count)
    else:
        if count is None:
            count = 1
        await start_quiz(message, topic, count, state)


async def start_quiz(message: types.Message, topic: str, count: int, state: FSMContext):
    await message.answer(f"❓ Генерирую {count} вопросов по теме «{topic}»...")
    try:
        questions = await generate_quiz_questions(topic, count)
    except Exception as e:
        logger.exception("Generation failed")
        await message.answer(f"❌ Ошибка: {e}")
        return

    user = await get_user(message.from_user.id)
    if not user:
        user = await create_user(message.from_user.id)

    mode = user.mode
    attempt_id = await create_quiz_attempt(message.from_user.id, topic, len(questions))

    session_data = QuizSessionData(
        user_id=message.from_user.id,
        questions=questions,
        mode=mode,
        current_index=0,
        attempt_id=attempt_id,
        topic=topic
    )
    await state.update_data(quiz=session_data.dict())

    if mode == "packet":
        await start_packet_quiz(message, questions, attempt_id)
    else:
        await start_sequential_quiz(message, state, session_data)


async def start_packet_quiz(message: types.Message, questions: list[Question], attempt_id: int):
    for i, q in enumerate(questions, 1):
        await message.answer(f"*{i}. {q.question}*", parse_mode="Markdown")
    await message.answer("Ответьте одним сообщением на все вопросы.\nЧтобы отменить - /cancel")


async def start_sequential_quiz(message: types.Message, state: FSMContext, session_data: QuizSessionData):
    q = session_data.questions[0]
    total = len(session_data.questions)
    text = f"*Вопрос 1 из {total}:*\n\n{q.question}"
    await message.answer(text, parse_mode="Markdown", reply_markup=quiz_control_keyboard())
    await state.set_state(QuizStates.waiting_for_sequential_answer)


async def process_sequential_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    session_data = QuizSessionData(**data.get("quiz"))
    attempt_id = session_data.attempt_id
    current_index = session_data.current_index
    question = session_data.questions[current_index]

    try:
        result = await verify_answer(question, message.text)
    except Exception as e:
        logger.exception("Verification failed")
        await message.answer("❌ Ошибка проверки ответа. Попробуйте ещё раз.")
        return

    await save_answer(
        message.from_user.id, attempt_id, question.question,
        message.text, result.correct, result.explanation
    )
    await message.answer(f"{'✅' if result.correct else '❌'} *Результат:*\n{result.explanation}", parse_mode="Markdown")

    next_index = current_index + 1
    if next_index < len(session_data.questions):
        session_data.current_index = next_index
        await state.update_data(quiz=session_data.dict())
        q = session_data.questions[next_index]
        text = f"*Вопрос {next_index+1} из {len(session_data.questions)}:*\n\n{q.question}"
        await message.answer(text, parse_mode="Markdown", reply_markup=quiz_control_keyboard())
    else:
        await finish_quiz(message, state, session_data, attempt_id)


async def finish_quiz(message: types.Message, state: FSMContext, session_data: QuizSessionData, attempt_id: int):
    from services.db_service import count_correct_answers_for_attempt
    correct_count = await count_correct_answers_for_attempt(attempt_id)
    await finish_quiz_attempt(attempt_id, correct_count)
    await state.clear()

    total = session_data.total_questions if hasattr(session_data, 'total_questions') else len(session_data.questions)
    percent = (correct_count / total * 100) if total > 0 else 0
    await message.answer(
        f"✅ Тест завершён!\n"
        f"Правильных ответов: {correct_count} из {total} ({percent:.1f}%)\n"
        f"Используйте /stats для просмотра общей статистики."
    )


@router.callback_query(lambda c: c.data == "finish_quiz", StateFilter(QuizStates.waiting_for_sequential_answer))
async def finish_quiz_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    session_data = QuizSessionData(**data.get("quiz"))
    attempt_id = session_data.attempt_id
    await finish_quiz(callback.message, state, session_data, attempt_id)
    await callback.answer("Тест завершён.")


async def send_theory(message: types.Message, topic: str):
    await message.answer(f"📚 Генерирую теорию по теме «{topic}»...")
    theory = await generate_theory(topic)
    await message.answer(theory, parse_mode="Markdown")


async def send_qa(message: types.Message, topic: str, count: int):
    await message.answer(f"📖 Генерирую {count} вопросов с ответами по теме «{topic}»...")
    qa_list = await generate_questions_with_answers(topic, count)
    for i, item in enumerate(qa_list, 1):
        text = f"*{i}. {item['question']}*\n\n✅ *Ответ:* {item['answer']}"
        await message.answer(text, parse_mode="Markdown")