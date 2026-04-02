from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext


router = Router()


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Текущий тест отменён.")