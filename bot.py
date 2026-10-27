"""
Точка входа бота. Запуск: python bot.py
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from database import init_db
from handlers import router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Не найден BOT_TOKEN. Скопируйте .env.example в .env и укажите токен от @BotFather."
        )

    await init_db()

    # Если api.telegram.org заблокирован у вашего провайдера/страны, можно
    # задать в .env адрес прокси (например, Cloudflare Worker), через который
    # бот будет ходить к Telegram. Если переменная не задана — работает как обычно.
    proxy_base = os.getenv("TELEGRAM_API_PROXY", "").strip()
    session = None
    if proxy_base:
        api_server = TelegramAPIServer.from_base(proxy_base)
        # Таймаут сессии должен быть больше polling_timeout ниже (иначе сессия
        # оборвёт запрос раньше, чем Telegram успеет ответить через прокси).
        session = AiohttpSession(api=api_server, timeout=15)
        logger.info("Использую прокси для запросов к Telegram: %s", proxy_base)

    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Бот запущен, начинаю polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    # Короткий polling_timeout (5 сек вместо стандартных 10) снижает риск
    # обрыва долгого запроса через прокси (Cloudflare Worker) и уменьшает
    # задержку между отправкой команды и её получением ботом.
    await dp.start_polling(bot, polling_timeout=5)


if __name__ == "__main__":
    asyncio.run(main())