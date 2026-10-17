"""
Работа с базой данных SQLite.
Все обращения к данным — только через этот файл.
"""

import aiosqlite
from datetime import datetime
from config import DB_PATH, WORK_HOURS, SERVICES_PRICES


async def init_db():
    """Создаёт таблицы, если их нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
CREATE TABLE IF NOT EXISTS barbers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    telegram_id INTEGER,
    active INTEGER DEFAULT 1
)
""")
        await db.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    service TEXT NOT NULL,
    barber TEXT,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    status TEXT DEFAULT 'ожидает',
    created_at TEXT,
    reminded_1h INTEGER DEFAULT 0,
    reminded_5m INTEGER DEFAULT 0
)
""")
        await db.execute("""
CREATE TABLE IF NOT EXISTS breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barber TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
)
""")
        await db.commit()


async def create_booking(user_id, name, phone, service, barber, date, time):
    """Создаёт запись. Возвращает id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO bookings 
(user_id, name, phone, service, barber, date, time, status, created_at) 
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, phone, service, barber, date, time,
             "ожидает", datetime.now().strftime("%d.%m.%Y %H:%M"))
        )
        await db.commit()
        return cursor.lastrowid


async def is_slot_free(barber, date, time):
    """Проверяет, свободно ли время у барбера (нет записи и нет перерыва)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверка занятости
        cursor = await db.execute(
            "SELECT COUNT(*) FROM bookings WHERE barber = ? AND date = ? AND time = ? AND status != 'отменено'",
            (barber, date, time)
        )
        row = await cursor.fetchone()
        if row[0] > 0:
            return False

        # Проверка перерыва
        cursor = await db.execute(
            "SELECT COUNT(*) FROM breaks WHERE barber = ? AND date = ? AND start_time <= ? AND end_time > ?",
            (barber, date, time, time)
        )
        row = await cursor.fetchone()
        return row[0] == 0


async def get_free_slots(barber, date):
    """Возвращает список свободных слотов для барбера на дату."""
    free = []
    for t in WORK_HOURS:
        if await is_slot_free(barber, date, t):
            free.append(t)
    return free


async def get_bookings_by_date(date, barber=None):
    """Возвращает записи на дату (опционально — по барберу)."""
    async with aiosqlite.connect(DB_PATH) as db:
        if barber:
            cursor = await db.execute(
                "SELECT * FROM bookings WHERE date = ? AND barber = ? AND status != 'отменено' ORDER BY time",
                (date, barber)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM bookings WHERE date = ? AND status != 'отменено' ORDER BY time",
                (date,)
            )
        return await cursor.fetchall()


async def get_user_bookings(user_id):
    """Возвращает активные записи пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND status != 'отменено' ORDER BY date, time",
            (user_id,)
        )
        return await cursor.fetchall()


async def get_revenue_by_date(date):
    """Возвращает выручку за дату (сумма цен услуг без отменённых записей)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT service FROM bookings WHERE date = ? AND status != 'отменено'",
            (date,)
        )
        rows = await cursor.fetchall()
        return sum(SERVICES_PRICES.get(r[0], 0) for r in rows)


async def cancel_booking(booking_id):
    """Отменяет запись по id."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bookings SET status = 'отменено' WHERE id = ?", (booking_id,))
        await db.commit()
        return True


async def get_bookings_by_barber_and_date(barber, date):
    """Возвращает все записи барбера на дату (только услуги, для выручки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT service, time FROM bookings 
               WHERE barber = ? AND date = ? AND status != 'отменено' 
               ORDER BY time""",
            (barber, date)
        )
        return await cursor.fetchall()


# Даты хранятся как ДД.ММ.ГГГГ — сравниваем в SQL через ГГГГММДД
_DATE_KEY_SQL = "substr(date, 7, 4) || substr(date, 4, 2) || substr(date, 1, 2)"


def _ymd(date_str: str) -> str:
    """ДД.ММ.ГГГГ -> ГГГГММДД (для корректного сравнения дат)."""
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y%m%d")
    except ValueError:
        return ""


async def get_bookings_by_barber_and_range(barber, date_from, date_to):
    """Записи барбера за период (для выручки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"""SELECT service, date, time FROM bookings 
               WHERE barber = ? AND {_DATE_KEY_SQL} >= ? AND {_DATE_KEY_SQL} <= ?
                 AND status != 'отменено' 
               ORDER BY {_DATE_KEY_SQL}, time""",
            (barber, _ymd(date_from), _ymd(date_to))
        )
        return await cursor.fetchall()


async def get_all_bookings_by_range(date_from, date_to, barber=None):
    """Все записи за период (для общего отчёта)."""
    async with aiosqlite.connect(DB_PATH) as db:
        if barber:
            cursor = await db.execute(
                f"""SELECT service, date, time, barber FROM bookings 
                   WHERE barber = ? AND {_DATE_KEY_SQL} >= ? AND {_DATE_KEY_SQL} <= ?
                     AND status != 'отменено' 
                   ORDER BY {_DATE_KEY_SQL}, time""",
                (barber, _ymd(date_from), _ymd(date_to))
            )
        else:
            cursor = await db.execute(
                f"""SELECT service, date, time, barber FROM bookings 
                   WHERE {_DATE_KEY_SQL} >= ? AND {_DATE_KEY_SQL} <= ?
                     AND status != 'отменено' 
                   ORDER BY {_DATE_KEY_SQL}, time""",
                (_ymd(date_from), _ymd(date_to))
            )
        return await cursor.fetchall()