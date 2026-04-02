from aiogram import Router, types
from aiogram.filters import Command
from services.db_service import get_user_stats


router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = await get_user_stats(message.from_user.id)
    if not stats or stats["total_questions"] == 0:
        await message.answer("📊 У вас пока нет пройденных тестов.")
        return

    total_percent = (stats["total_correct"] / stats["total_questions"]) * 100 if stats["total_questions"] else 0
    text = f"📊 *Ваша статистика*\n\n"
    text += f"Всего попыток: {stats['total_attempts']}\n"
    text += f"Всего вопросов: {stats['total_questions']}\n"
    text += f"Правильных ответов: {stats['total_correct']}\n"
    text += f"Общая успеваемость: {total_percent:.1f}%\n\n"
    text += "*По темам:*\n"
    for topic, data in stats["topics"].items():
        percent = (data["correct"] / data["total"]) * 100 if data["total"] else 0
        text += f"• {topic}: {data['correct']}/{data['total']} ({percent:.1f}%)\n"

    await message.answer(text, parse_mode="Markdown")