from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from services.db_service import get_user, update_user_settings, create_user
from keyboards.inline import settings_keyboard
from utils.helpers import safe_send


router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        user = await create_user(message.from_user.id)

    await safe_send(
        message,
        "⚙️ Настройки:",
        reply_markup=settings_keyboard(user.mode)
    )


@router.callback_query(lambda c: c.data.startswith("set_mode_"))
async def set_mode(callback: CallbackQuery):
    mode = callback.data.split("_")[-1]  # packet или sequential
    await update_user_settings(callback.from_user.id, mode=mode)
    await callback.answer(f"Режим изменён на {'пакетный' if mode == 'packet' else 'последовательный'}")

    user = await get_user(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard(user.mode))


@router.callback_query(lambda c: c.data == "close_settings")
async def close_settings(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Настройки закрыты")