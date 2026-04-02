import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage as FSMStorage
from config import BOT_TOKEN, PROXY_URL
from handlers import routers
from services.db_service import init_db


logging.basicConfig(level=logging.INFO)


async def main():
    # Инициализируем БД
    await init_db()

    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=FSMStorage())
    for router in routers:
        dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())