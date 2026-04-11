import json
import logging
from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from services.learning_service import generate_topics_pool, generate_topic_theory, generate_topic_questions
from services.db_service import (
    create_learning_path, get_active_learning_path, deactivate_learning_path,
    create_or_get_progress, get_progress, update_progress,
    get_learning_path_by_id, get_user, create_quiz_attempt
)
from keyboards.inline import learning_keyboard, topic_completed_keyboard
from handlers.quiz import start_quiz_session
from models.schemas import QuizSessionData, Question
from utils.helpers import safe_send, escape_markdown


router = Router()
logger = logging.getLogger(__name__)


class LearningStates(StatesGroup):
    waiting_for_theory = State()
    waiting_for_questions = State()


# ---------- Команды ----------
@router.message(Command("start_learning"))
async def cmd_start_learning(message: types.Message, state: FSMContext):
    path = await get_active_learning_path(message.from_user.id)
    if not path:
        await safe_send(message, "У вас нет активного учебного плана. Создайте его через `/gp`.")
        return
    progress = await get_progress(message.from_user.id, path.id)
    if not progress:
        progress = await create_or_get_progress(message.from_user.id, path.id)
    if progress.is_finished:
        await safe_send(message, "Вы уже завершили обучение по этому плану. Для повторного прохождения создайте новый план через `/gp`.")
        return
    topics = json.loads(path.topics)
    current_idx = progress.current_topic_index
    if current_idx >= len(topics):
        await safe_send(message, "Поздравляю! Вы прошли все темы. Используйте `/final_test` для итоговой проверки.")
        return
    await show_topic(message, state, path.id, topics, current_idx, progress)


@router.message(Command("gp"))
async def cmd_generate_pool(message: types.Message, state: FSMContext):
    """
    Обработка команды /gp [start_topic] [num_topics]
    Примеры:
    /gp django 6
    /gp создай план обучения fullstack 7
    """
    print("DEBUG: /gp command received")
    text = message.text.strip()
    # Парсим аргументы
    parts = text.split()
    # Удаляем команду
    parts.pop(0)
    if not parts:
        await safe_send(message, "Укажите начальную тему. Например: `/gp django 4`")
        return

    # Пытаемся найти число в конце
    num_topics = 4  # по умолчанию
    # Ищем последний аргумент, который является числом
    if parts[-1].isdigit():
        num_topics = int(parts[-1])
        parts = parts[:-1]
    start_topic = " ".join(parts).strip()
    if not start_topic:
        await safe_send(message, "Укажите начальную тему.")
        return

    # Генерация пула
    progress_msg = await safe_send(message, f"🧠 Генерирую учебный план из {num_topics} тем, начиная с «{start_topic}»...")
    topics = await generate_topics_pool(start_topic, num_topics)
    await progress_msg.delete()
    if not topics or len(topics) != num_topics:
        await safe_send(message, "❌ Не удалось сгенерировать план. Попробуйте ещё раз или уточните тему.")
        return

    # Сохраняем временно в состояние (чтобы потом подтвердить)
    await state.update_data(pending_topics=topics, start_topic=start_topic)

    # Формируем красивое сообщение со списком тем
    topics_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(topics)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать обучение", callback_data="approve_pool")],
        [InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="regenerate_pool")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_pool")]
    ])
    await safe_send(message, f"📚 *Предлагаемый учебный план:*\n\n{topics_text}\n\nВам нравится?", parse_mode="MarkdownV2", reply_markup=keyboard)


@router.message(Command("progress"))
async def cmd_progress(message: types.Message):
    path = await get_active_learning_path(message.from_user.id)
    if not path:
        await safe_send(message, "Нет активного обучения. Создайте план через `/gp`.")
        return
    progress = await get_progress(message.from_user.id, path.id)
    if not progress:
        await safe_send(message, "Вы ещё не начали обучение. Используйте `/start_learning`.")
        return
    topics = json.loads(path.topics)
    completed = json.loads(progress.completed_topics) if progress.completed_topics else []
    current = progress.current_topic_index
    total = len(topics)
    percent = (len(completed) / total * 100) if total else 0
    bar_length = 10
    filled = int(bar_length * len(completed) / total) if total else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    text = f"📊 *Ваш прогресс*\n\n{bar} {percent:.0f}%\n"
    text += f"Пройдено тем: {len(completed)} из {total}\n"
    if current < total:
        text += f"Текущая тема: {topics[current]}\n"
    else:
        text += "🎉 Все темы пройдены! Используйте `/final_test`"
    await safe_send(message, text, parse_mode="MarkdownV2")


# ---------- Вспомогательные функции ----------
async def show_topic(message: types.Message, state: FSMContext, path_id: int, topics: list, topic_idx: int, progress):
    topic = topics[topic_idx]
    await safe_send(message, f"📚 *Тема {topic_idx+1} из {len(topics)}: {topic}*", parse_mode="MarkdownV2")
    progress_msg = await safe_send(message, f"Генерирую теорию по теме «{topic}»...")
    theory = await generate_topic_theory(topic)
    await progress_msg.delete()
    await safe_send(message, theory, parse_mode=None)
    await state.update_data(current_path_id=path_id, current_topic_idx=topic_idx, current_topic=topic)
    keyboard = learning_keyboard(topic_idx, len(topics), has_next=False)
    await safe_send(message, "Когда будете готовы, нажмите «Задать вопросы»", reply_markup=keyboard)
    await state.set_state(LearningStates.waiting_for_theory)


@router.callback_query(lambda c: c.data == "ask_questions", StateFilter(LearningStates.waiting_for_theory))
async def ask_questions(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    path_id = data.get("current_path_id")
    topic_idx = data.get("current_topic_idx")
    topic = data.get("current_topic")
    if not path_id:
        await callback.answer("Ошибка: не найден учебный план")
        return
    path = await get_learning_path_by_id(path_id)
    if not path:
        await callback.answer("План не найден")
        return
    topics = json.loads(path.topics)
    mistakes = await get_user_mistakes(callback.from_user.id, topic, limit=10)
    progress = await get_progress(callback.from_user.id, path_id)
    completed = json.loads(progress.completed_topics) if progress.completed_topics else []
    previous_questions = []  # можно доработать
    await callback.answer("Генерирую вопросы...")
    progress_msg = await safe_send(callback.message, f"Генерирую вопросы по теме «{topic}»...")
    questions = await generate_topic_questions(topic, count=5, previous_questions=previous_questions, user_mistakes=mistakes)
    await progress_msg.delete()
    if not questions:
        await safe_send(callback.message, "Не удалось сгенерировать вопросы. Попробуйте ещё раз.")
        return
    user = await get_user(callback.from_user.id)
    attempt_id = await create_quiz_attempt(callback.from_user.id, topic, len(questions))
    session_data = QuizSessionData(
        user_id=callback.from_user.id,
        questions=questions,
        mode=user.mode,
        current_index=0,
        attempt_id=attempt_id,
        topic=topic
    )
    await state.update_data(quiz=session_data.dict(), learning_mode=True, path_id=path_id, topic_idx=topic_idx)
    await start_quiz_session(callback.message, state, session_data)
    await callback.message.delete()
    await callback.answer()


@router.callback_query(lambda c: c.data == "next_topic")
async def next_topic(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    path_id = data.get("path_id") or data.get("current_path_id")
    topic_idx = data.get("topic_idx") or data.get("current_topic_idx")
    if not path_id:
        await callback.answer("Ошибка: не найден план")
        return
    path = await get_learning_path_by_id(path_id)
    topics = json.loads(path.topics)
    next_idx = topic_idx + 1
    if next_idx < len(topics):
        progress = await get_progress(callback.from_user.id, path_id)
        completed = json.loads(progress.completed_topics) if progress.completed_topics else []
        if topic_idx not in completed:
            completed.append(topic_idx)
        await update_progress(callback.from_user.id, path_id, current_topic_index=next_idx, completed_topics=completed)
        await show_topic(callback.message, state, path_id, topics, next_idx, progress)
        await callback.message.delete()
        await callback.answer()
    else:
        progress = await get_progress(callback.from_user.id, path_id)
        completed = json.loads(progress.completed_topics) if progress.completed_topics else []
        if topic_idx not in completed:
            completed.append(topic_idx)
        await update_progress(callback.from_user.id, path_id, is_finished=True, completed_topics=completed)
        await safe_send(callback.message, "🎉 Поздравляю! Вы прошли все темы. Теперь можете пройти итоговый тест командой `/final_test`.")
        await callback.message.delete()
        await callback.answer()


@router.callback_query(lambda c: c.data == "abort_learning")
async def abort_learning(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_send(callback.message, "Обучение прервано. Вы можете начать заново через `/start_learning`.")
    await callback.message.delete()
    await callback.answer()


@router.callback_query(lambda c: c.data == "approve_pool")
async def approve_pool(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topics = data.get("pending_topics")
    start_topic = data.get("start_topic")
    if not topics:
        await callback.answer("План не найден, создайте новый через /gp")
        await callback.message.delete()
        return

    # Сохраняем LearningPath
    path_id = await create_learning_path(callback.from_user.id, topics, title=f"План по {start_topic}")
    # Создаём прогресс
    progress = await create_or_get_progress(callback.from_user.id, path_id)

    await callback.message.delete()
    await safe_send(callback.message, f"✅ Учебный план сохранён!\n\n"
                                      f"Всего тем: {len(topics)}\n"
                                      f"Чтобы начать обучение, используйте `/start_learning`.\n"
                                      f"Текущая тема: {topics[0]}")
    await callback.answer("План утверждён")
    await state.clear()


@router.callback_query(lambda c: c.data == "regenerate_pool")
async def regenerate_pool(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    old_topics = data.get("pending_topics")
    start_topic = data.get("start_topic")
    if not start_topic:
        await callback.answer("Ошибка: не найдена начальная тема")
        return
    num_topics = len(old_topics) if old_topics else 4
    await callback.answer("Генерирую новый план...")
    new_topics = await generate_topics_pool(start_topic, num_topics)
    if not new_topics:
        await callback.message.answer("❌ Не удалось сгенерировать новый план. Попробуйте ещё раз.")
        return
    await state.update_data(pending_topics=new_topics)
    topics_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(new_topics)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать обучение", callback_data="approve_pool")],
        [InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="regenerate_pool")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_pool")]
    ])
    await callback.message.edit_text(f"📚 *Предлагаемый учебный план (новая версия):*\n\n{topics_text}\n\nВам нравится?", parse_mode="MarkdownV2", reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "reject_pool")
async def reject_pool(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await safe_send(callback.message, "План отклонён. Вы можете создать новый через /gp.")
    await callback.answer("План отклонён")
    await state.clear()