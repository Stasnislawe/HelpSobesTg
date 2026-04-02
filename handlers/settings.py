from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from services.db_service import get_user, update_user_settings
from keyboards.inline import settings_keyboard


router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        user = await create_user(message.from_user.id)  # предполагаем, что create_user есть

    await message.answer(
        "⚙️ Настройки:",
        reply_markup=settings_keyboard(user.mode, user.default_question_count)
    )


@router.callback_query(lambda c: c.data.startswith("set_mode_"))
async def set_mode(callback: CallbackQuery):
    mode = callback.data.split("_")[-1]  # packet или sequential
    await update_user_settings(callback.from_user.id, mode=mode)
    await callback.answer(f"Режим изменён на {'пакетный' if mode == 'packet' else 'последовательный'}")
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard(mode, 3))  # нужна актуальная клавиатура


@router.callback_query(lambda c: c.data.startswith("set_count_"))
async def set_count(callback: CallbackQuery):
    count = int(callback.data.split("_")[-1])
    await update_user_settings(callback.from_user.id, default_question_count=count)
    await callback.answer(f"Количество вопросов по умолчанию: {count}")
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard("packet", count))  # нужно передать текущий режим