"""
Вспомогательные функции: даты, время, валидация.
"""

import re
from datetime import datetime, timedelta
import zoneinfo

from config import TIMEZONE

TZ = zoneinfo.ZoneInfo(TIMEZONE)


def resolve_date_string(user_text: str) -> str:
    """
    Преобразует текст кнопки или ввод пользователя в дату ДД.ММ.ГГГГ.
    Понимает: «Сегодня (11.10)», «Завтра», «Пн 13.10», «13.10», «13.10.2026».
    Возвращает пустую строку, если не удалось распознать.
    """
    now = datetime.now(TZ)
    text = user_text.strip()
    low = text.lower()

    # Дата внутри текста (кнопки вида «Пн 13.10» или «Сегодня (11.10)»)
    match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else now.year
        try:
            target = datetime(year, month, day).date()
        except ValueError:
            return ""
        # Если год не указан и дата «ушла» далеко в прошлое — имеется в виду следующий год
        if not match.group(3) and (now.date() - target).days > 30:
            try:
                target = datetime(year + 1, month, day).date()
            except ValueError:
                return ""
        return target.strftime("%d.%m.%Y")

    if low == "сегодня":
        target = now.date()
    elif low == "завтра":
        target = (now + timedelta(days=1)).date()
    elif low == "послезавтра":
        target = (now + timedelta(days=2)).date()
    else:
        return ""
    return target.strftime("%d.%m.%Y")


def validate_time_format(time_text: str) -> str:
    """
    Проверяет формат ЧЧ:ММ или H:MM. Возвращает ЧЧ:ММ или пустую строку.
    """
    time_text = time_text.strip()
    match = re.match(r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$", time_text)
    if match:
        hours, minutes = match.groups()
        return f"{int(hours):02d}:{minutes}"
    return ""


def parse_human_time(text: str) -> str:
    """
    Пытается понять «через час», «через 30 минут», «в 14:00», «в два часа».
    Возвращает ЧЧ:ММ или пустую строку.
    """
    text = text.strip().lower()

    # «через N минут/час(а/ов)»
    match = re.search(r"через\s+(\d+)\s*(минут|мин|час|часа|часов|ч)", text)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        delta = timedelta(hours=num) if unit.startswith("ч") else timedelta(minutes=num)
        target = datetime.now(TZ) + delta
        # Округляем до ближайших 30 минут
        minute = 0 if target.minute < 30 else 30
        return f"{target.hour:02d}:{minute:02d}"

    # «в HH:MM» или «HH:MM»
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"

    return ""


def validate_phone(text: str) -> str:
    """
    Проверяет номер телефона. Возвращает нормализованный номер или пустую строку.
    """
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in "78":
        return f"+7{digits[1:]}"
    if len(digits) == 10:
        return f"+7{digits}"
    return ""


def validate_name(text: str) -> str:
    """Проверяет имя. Возвращает имя или пустую строку."""
    name = text.strip()
    if 2 <= len(name) <= 50 and re.match(r"^[a-zA-Zа-яА-ЯёЁ\s\-]+$", name):
        return name
    return ""


def now_str() -> str:
    """Текущая дата и время в формате ДД.ММ.ГГГГ ЧЧ:ММ."""
    return datetime.now(TZ).strftime("%d.%m.%Y %H:%M")


def today_str() -> str:
    """Сегодняшняя дата в формате ДД.ММ.ГГГГ."""
    return datetime.now(TZ).strftime("%d.%m.%Y")


def tomorrow_str() -> str:
    """Завтрашняя дата в формате ДД.ММ.ГГГГ."""
    return (datetime.now(TZ) + timedelta(days=1)).strftime("%d.%m.%Y")


def parse_date_word(word: str) -> str:
    """
    Преобразует слово в дату ДД.ММ.ГГГГ.
    Поддерживает: вчера, сегодня, завтра, позавчера, ДД.ММ.ГГГГ, ДД.ММ.
    """
    now = datetime.now(TZ)
    word = word.strip().lower()

    if word == "вчера":
        return (now - timedelta(days=1)).strftime("%d.%m.%Y")
    if word == "позавчера":
        return (now - timedelta(days=2)).strftime("%d.%m.%Y")
    if word == "сегодня":
        return now.strftime("%d.%m.%Y")
    if word == "завтра":
        return (now + timedelta(days=1)).strftime("%d.%m.%Y")

    # ДД.ММ.ГГГГ
    try:
        return datetime.strptime(word, "%d.%m.%Y").strftime("%d.%m.%Y")
    except ValueError:
        pass

    # ДД.ММ — подставляем текущий год
    try:
        dt = datetime.strptime(word, "%d.%m").replace(year=now.year)
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        pass

    return ""


def get_period_dates(period: str) -> tuple:
    """
    Возвращает (date_from, date_to) для периода.
    period = 'week' | 'month'
    """
    now = datetime.now(TZ)
    if period == "week":
        date_from = (now - timedelta(days=6)).date()
    elif period == "month":
        date_from = (now - timedelta(days=29)).date()
    else:
        return ("", "")
    date_to = now.date()
    return (
        date_from.strftime("%d.%m.%Y"),
        date_to.strftime("%d.%m.%Y"),
    )


def date_in_range(date_str: str, date_from: str, date_to: str) -> bool:
    """Проверяет, попадает ли ДД.ММ.ГГГГ в диапазон."""
    try:
        d = datetime.strptime(date_str, "%d.%m.%Y")
        f = datetime.strptime(date_from, "%d.%m.%Y")
        t = datetime.strptime(date_to, "%d.%m.%Y")
        return f <= d <= t
    except ValueError:
        return False


# Короткие и полные названия дней недели (0 = понедельник)
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_FULL = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def upcoming_days(count: int = 7) -> list:
    """Список пар (метка кнопки, ДД.ММ.ГГГГ) для ближайших count дней."""
    now = datetime.now(TZ)
    result = []
    for i in range(count):
        d = (now + timedelta(days=i)).date()
        if i == 0:
            label = f"Сегодня ({d.strftime('%d.%m')})"
        elif i == 1:
            label = f"Завтра ({d.strftime('%d.%m')})"
        else:
            label = f"{WEEKDAYS_RU[d.weekday()]} {d.strftime('%d.%m')}"
        result.append((label, d.strftime("%d.%m.%Y")))
    return result


def friendly_day_label(date_str: str) -> str:
    """«сегодня», «завтра» или название дня недели для ДД.ММ.ГГГГ."""
    try:
        d = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        return date_str
    delta = (d - datetime.now(TZ).date()).days
    if delta == 0:
        return "сегодня"
    if delta == 1:
        return "завтра"
    return WEEKDAYS_FULL[d.weekday()]