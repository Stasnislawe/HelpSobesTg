from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def settings_keyboard(mode: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Пакетный режим" + (" ✅" if mode == "packet" else ""), callback_data="set_mode_packet"),
            InlineKeyboardButton(text="🔁 Последовательный" + (" ✅" if mode == "sequential" else ""), callback_data="set_mode_sequential")
        ],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_settings")]
    ])


def quiz_control_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Завершить тест", callback_data="finish_quiz")]
    ])


def learning_keyboard(current_topic_index: int, total_topics: int, has_next: bool):
    """Клавиатура для управления обучением"""
    buttons = []
    # Кнопка "Задать вопросы" (показываем всегда)
    buttons.append([InlineKeyboardButton(text="❓ Задать вопросы по теме", callback_data="ask_questions")])
    # Кнопка "Следующая тема" (только если есть следующая и текущая тема пройдена)
    if has_next:
        buttons.append([InlineKeyboardButton(text="➡️ Следующая тема", callback_data="next_topic")])
    # Кнопка "Завершить обучение" (всегда)
    buttons.append([InlineKeyboardButton(text="❌ Завершить обучение", callback_data="abort_learning")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topic_completed_keyboard():
    """Клавиатура после прохождения темы (вопросы заданы)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Следующая тема", callback_data="next_topic")],
        [InlineKeyboardButton(text="❌ Завершить обучение", callback_data="abort_learning")]
    ])