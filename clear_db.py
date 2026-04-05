import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


DATABASE_URL = "sqlite+aiosqlite:///bot.db"


async def clear_database():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        # Удаляем все данные из таблиц (сохраняя структуру)
        await conn.execute(text("DELETE FROM answers"))
        await conn.execute(text("DELETE FROM quiz_attempts"))
        await conn.execute(text("DELETE FROM user_mistakes"))
        await conn.execute(text("DELETE FROM users"))
        print("✅ База данных очищена. Все таблицы обнулены.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_database())