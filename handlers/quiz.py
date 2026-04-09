import logging
import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery

from services.ollama_client import (
    generate_quiz_questions,
    verify_answer,
    generate_theory,
    generate_questions_with_answers,
    generate_answer_to_question
)
from services.db_service import (
    get_user, create_user, create_quiz_attempt, save_answer, finish_quiz_attempt,
    add_or_update_mistake, count_correct_answers_for_attempt
)
from utils.intent_parser import parse_intent
from keyboards.inline import quiz_control_keyboard, topic_completed_keyboard
from models.schemas import QuizSessionData, Question
from utils.helpers import safe_send, escape_markdown


logger = logging.getLogger(__name__)
router = Router()


MAX_ITEMS_PER_REQUEST = 10


class QuizStates(StatesGroup):
    waiting_for_sequential_answer = State()


@router.message(Command("cancel"))
async def cancel_quiz(message: types.Message, state: FSMContext):
    await state.clear()
    await safe_send(message, "✅ Текущий тест отменён.")


@router.message()
async def handle_message(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'):
        return

    current_state = await state.get_state()
    if current_state == QuizStates.waiting_for_sequential_answer.state:
        # Игнорируем пустые или нетекстовые сообщения
        if not message.text or not message.text.strip():
            await safe_send(message, "⚠️ Пожалуйста, напишите текстовый ответ на вопрос. Пустые сообщения не принимаются.")
            return
        await process_sequential_answer(message, state)
        return

    intent, topic, count, full_question = await parse_intent(message.text)
    if not topic:
        await safe_send(message, "Не понял тему. Напишите, например:\n"
                                 "• «4 вопроса по python»\n"
                                 "• «расскажи про джанго»\n"
                                 "• «3 вопроса по js с ответами»")
        return

    if count and count > MAX_ITEMS_PER_REQUEST:
        await safe_send(message, f"⚠️ Вы запросили {count} вопросов. Максимум {MAX_ITEMS_PER_REQUEST}. Я сгенерирую {MAX_ITEMS_PER_REQUEST}.")
        count = MAX_ITEMS_PER_REQUEST
    elif count is None:
        if intent == "quiz":
            count = 1
        elif intent == "qa":
            count = 3

    if intent == "explain":
        await send_explanation(message, full_question or topic or message.text)
        return

    if intent == "theory":
        await send_theory(message, topic)
    elif intent == "qa":
        await send_qa(message, topic, count)
    else:
        await start_quiz(message, topic, count, state)


async def start_quiz(message: types.Message, topic: str, count: int, state: FSMContext):
    await safe_send(message, f"❓ Генерирую {count} вопросов по теме «{topic}»...")
    try:
        questions = await generate_quiz_questions(topic, count)
    except Exception as e:
        logger.exception("Generation failed")
        await safe_send(message, f"❌ Ошибка при генерации вопросов: {e}")
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
    await start_quiz_session(message, state, session_data)


async def start_quiz_session(message: types.Message, state: FSMContext, session_data: QuizSessionData):
    if session_data.mode == "packet":
        await start_packet_quiz(message, session_data.questions, session_data.attempt_id, session_data.topic)
    else:
        await start_sequential_quiz(message, state, session_data)


async def start_packet_quiz(message: types.Message, questions: list[Question], attempt_id: int, topic: str):
    for i, q in enumerate(questions, 1):
        text = f"*{i}. {q.question}*"
        safe_text = escape_markdown(text)
        await safe_send(message, safe_text, parse_mode="MarkdownV2")
        await asyncio.sleep(1.5)
    await safe_send(message, "Ответьте одним сообщением на все вопросы.\n"
                             "Напишите ваши ответы (можно нумерованным списком или просто текст).\n"
                             "Чтобы отменить, используйте /cancel")


async def start_sequential_quiz(message: types.Message, state: FSMContext, session_data: QuizSessionData):
    q = session_data.questions[0]
    total = len(session_data.questions)
    text = f"*Вопрос 1 из {total}:*\n\n{q.question}"
    safe_text = escape_markdown(text)
    await safe_send(message, safe_text, parse_mode="MarkdownV2", reply_markup=quiz_control_keyboard())
    await safe_send(message, "✏️ Напишите ваш ответ текстом. Чтобы прервать тест, нажмите кнопку 'Завершить тест' или используйте /cancel.")
    await state.set_state(QuizStates.waiting_for_sequential_answer)


async def process_sequential_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    session_data = QuizSessionData(**data.get("quiz"))
    attempt_id = session_data.attempt_id
    current_index = session_data.current_index
    question = session_data.questions[current_index]

    user_answer = message.text.strip()
    if len(user_answer) < 2:
        await safe_send(message, "⚠️ Слишком короткий ответ. Пожалуйста, напишите развёрнутый ответ.")
        return

    try:
        result = await verify_answer(question, user_answer)
    except Exception as e:
        logger.exception("Verification failed")
        await safe_send(message, "❌ Ошибка при проверке ответа. Пожалуйста, попробуйте ещё раз.")
        return

    await save_answer(
        message.from_user.id,
        attempt_id,
        question.question,
        message.text,
        result.correct,
        result.explanation
    )

    if not result.correct:
        await safe_send(message,
                        f"❌ Неправильно.\n\n✅ *Правильный ответ:*\n{question.correct_answer}\n\n{result.explanation}",
                        parse_mode="MarkdownV2")
    else:
        await safe_send(message, f"✅ Верно!\n{result.explanation}", parse_mode=None)

    next_index = current_index + 1
    if next_index < len(session_data.questions):
        session_data.current_index = next_index
        await state.update_data(quiz=session_data.dict())
        q = session_data.questions[next_index]
        text = f"*Вопрос {next_index+1} из {len(session_data.questions)}:*\n\n{q.question}"
        safe_text = escape_markdown(text)
        await safe_send(message, safe_text, parse_mode="MarkdownV2", reply_markup=quiz_control_keyboard())
    else:
        await finish_quiz(message, state, session_data, attempt_id)


async def finish_quiz(message: types.Message, state: FSMContext, session_data: QuizSessionData, attempt_id: int):
    correct_count = await count_correct_answers_for_attempt(attempt_id)
    await finish_quiz_attempt(attempt_id, correct_count)
    total = len(session_data.questions)
    percent = (correct_count / total * 100) if total > 0 else 0

    data = await state.get_data()
    learning_mode = data.get("learning_mode")
    if learning_mode:
        # Сохраняем данные обучения, но чистим только данные викторины
        await state.update_data(quiz=None)  # удаляем данные викторины
        await safe_send(message, f"✅ Тема пройдена!\nПравильных ответов: {correct_count} из {total} ({percent:.1f}%)", reply_markup=topic_completed_keyboard())
        await state.update_data(topic_completed=True)
        # Не очищаем всё состояние, чтобы сохранить learning_mode, path_id, topic_idx
    else:
        await safe_send(message, f"✅ Тест завершён!\nПравильных ответов: {correct_count} из {total} ({percent:.1f}%)\nИспользуйте /stats для просмотра общей статистики.")
        await state.clear()  # только для обычного теста


@router.callback_query(lambda c: c.data == "finish_quiz", StateFilter(QuizStates.waiting_for_sequential_answer))
async def finish_quiz_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    session_data = QuizSessionData(**data.get("quiz"))
    attempt_id = session_data.attempt_id
    await finish_quiz(callback.message, state, session_data, attempt_id)
    await callback.answer("Тест завершён.")


async def send_theory(message: types.Message, topic: str):
    await safe_send(message, f"📚 Генерирую теорию по теме «{topic}»...")
    theory = await generate_theory(topic)
    await safe_send(message, theory, parse_mode=None)


async def send_qa(message: types.Message, topic: str, count: int):
    if count > MAX_ITEMS_PER_REQUEST:
        count = MAX_ITEMS_PER_REQUEST
        await safe_send(message, f"⚠️ Ограничиваю до {MAX_ITEMS_PER_REQUEST} вопросов с ответами.")

    await safe_send(message, f"📖 Генерирую {count} вопросов с ответами по теме «{topic}»...")
    qa_list = await generate_questions_with_answers(topic, count)

    for i, item in enumerate(qa_list, 1):
        text = f"{i}. {item['question']}\n\n✅ Ответ: {item['answer']}"
        await safe_send(message, text, parse_mode=None)
        await asyncio.sleep(1.5)


async def send_explanation(message: types.Message, question_text: str):
    await safe_send(message, f"📚 Генерирую ответ на вопрос...")
    explanation = await generate_answer_to_question(question_text)
    await safe_send(message, explanation, parse_mode=None)