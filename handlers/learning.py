import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from services.learning_service import generate_topics_pool
from services.db_service import create_learning_path, get_active_learning_path, deactivate_learning_path, create_or_get_progress
from utils.helpers import safe_send


router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start_learning"))
async def cmd_start_learning(message: types.Message):
    await safe_send(message, "Функция обучения в разработке. Скоро появится!")


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