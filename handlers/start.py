from aiogram import Router, types
from aiogram.filters import Command
from services.db_service import get_user, create_user


router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        user = await create_user(message.from_user.id)

    await message.answer(
        "👋 Привет! Я бот для подготовки к собеседованиям.\n\n"
        "Я умею генерировать вопросы по разным темам: Python, Django, JavaScript и другим.\n"
        "Просто напиши, что хочешь, например:\n"
        "• «5 вопросов по Python»\n"
        "• «3 вопроса про Django»\n"
        "• «10 вопросов о JavaScript»\n\n"
        "Ты можешь отвечать на все вопросы сразу одним сообщением, "
        "или настроить последовательный режим (вопрос за вопросом) через /settings.\n\n"
        "Команды:\n"
        "/settings – настройки\n"
        "/stats – моя статистика\n"
        "/cancel – прервать текущий тест"
    )