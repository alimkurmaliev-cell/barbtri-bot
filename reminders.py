"""
Напоминания клиентам: за 1 час и за 5 минут до визита.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot

import config
from config import DB_PATH
from keyboards import get_reminder_inline_keyboard


logger = logging.getLogger(__name__)


async def _get_pending_reminders(kind: str):
    """
    Возвращает записи, которым нужно отправить напоминание.
    kind = '1h' или '5m'.
    """
    now = datetime.now()
    field = "reminded_1h" if kind == "1h" else "reminded_5m"
    window_start = 55 if kind == "1h" else 3  # минут до визита (нижняя граница)
    window_end = 65 if kind == "1h" else 7  # минут до визита (верхняя граница)

    result = []
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"""SELECT id, user_id, name, service, barber, date, time 
FROM bookings 
WHERE status != 'отменено' AND {field} = 0"""
        )
        rows = await cursor.fetchall()

    for row in rows:
        booking_id, user_id, name, service, barber, date_str, time_str = row
        try:
            visit_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except ValueError:
            continue

        delta_min = (visit_dt - now).total_seconds() / 60
        if window_start <= delta_min <= window_end:
            result.append({
                "id": booking_id,
                "user_id": user_id,
                "name": name,
                "service": service,
                "barber": barber,
                "date": date_str,
                "time": time_str,
            })
    return result


async def _mark_sent(booking_id: int, kind: str):
    field = "reminded_1h" if kind == "1h" else "reminded_5m"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE bookings SET {field} = 1 WHERE id = ?", (booking_id,))
        await db.commit()


async def reminder_loop(bot: Bot):
    """
    Фоновая задача: каждые 60 секунд проверяет, кому пора напомнить.
    """
    logger.info("Планировщик напоминаний запущен.")
    while True:
        try:
            # 1. Напоминание за час
            for b in await _get_pending_reminders("1h"):
                try:
                    text = (
                        f"⏰ Напоминание о записи\n\n"
                        f"У вас визит через час:\n"
                        f"💈 Мастер: {b['barber']}\n"
                        f"✂️ Услуга: {b['service']}\n"
                        f"📅 {b['date']} в {b['time']}\n\n"
                        "Готовы прийти?"
                    )
                    await bot.send_message(
                        chat_id=b["user_id"],
                        text=text,
                        parse_mode="Markdown",
                        reply_markup=get_reminder_inline_keyboard(b["id"]),
                    )
                    await _mark_sent(b["id"], "1h")
                    logger.info(f"Напоминание за час отправлено #{b['id']}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания за час #{b['id']}: {e}")

            # 2. Напоминание за 5 минут
            for b in await _get_pending_reminders("5m"):
                try:
                    text = (
                        f"⏰ Через 5 минут ваша запись!\n\n"
                        f"💈 Мастер: {b['barber']}\n"
                        f"⏰ Время: {b['time']}\n\n"
                        "Всё в силе?"
                    )
                    await bot.send_message(
                        chat_id=b["user_id"],
                        text=text,
                        parse_mode="Markdown",
                        reply_markup=get_reminder_inline_keyboard(b["id"]),
                    )
                    await _mark_sent(b["id"], "5m")
                    logger.info(f"Напоминание за 5 минут отправлено #{b['id']}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания за 5 минут #{b['id']}: {e}")

        except Exception as e:
            logger.error(f"Ошибка в цикле напоминаний: {e}")

        # Проверка каждую минуту
        await asyncio.sleep(60)