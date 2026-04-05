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