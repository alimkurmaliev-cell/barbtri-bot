"""
Точка входа. Запускает бота и фоновые задачи.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import init_db
from reminders import reminder_loop
from handlers import client, admin, barber


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    if not config.TELEGRAM_TOKEN or config.TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Не указан TELEGRAM_TOKEN в .env")
        return

    # Инициализация базы данных (создаст таблицы, если их нет)
    await init_db()
    logger.info("База данных готова.")

    bot = Bot(token=config.TELEGRAM_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Роутеры
    dp.include_router(client.router)
    dp.include_router(admin.router)
    dp.include_router(barber.router)

    # Фоновая задача напоминаний
    asyncio.create_task(reminder_loop(bot))

    await setup_commands(bot)

    logger.info("Бот запущен.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

async def setup_commands(bot: Bot):
    """Устанавливает меню команд для клиентов и для админа."""

    # 1. Команды для всех (обычные клиенты)
    client_commands = [
        BotCommand(command="start", description="Записаться в барбершоп"),
        BotCommand(command="my", description="Мои записи"),
    ]
    await bot.set_my_commands(client_commands, scope=BotCommandScopeDefault())

    # 2. Команды для админа (только для его chat_id)
    if config.ADMIN_ID:
        admin_commands = [
            BotCommand(command="start", description="Записаться в барбершоп"),
            BotCommand(command="my", description="Мои записи"),
            BotCommand(command="admin", description="Админ-панель"),
            BotCommand(command="revenue", description="Выручка по барберу"),
            BotCommand(command="report", description="Отчёт за неделю/месяц"),
        ]
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=config.ADMIN_ID),
            )
        except Exception as e:
            logger.error(f"Не удалось установить команды для админа: {e}")

    logger.info("Меню команд установлено.")


if __name__ == "__main__":
    asyncio.run(main())


