"""
Все клавиатуры бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import SERVICES, DATE_OPTIONS, BARBERS
from utils import upcoming_days


# ==================== REPLY-КЛАВИАТУРЫ ====================

def get_services_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора услуги."""
    buttons = [[KeyboardButton(text=s)] for s in SERVICES]
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


def get_dates_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора даты: ближайшие 7 дней (по 2 кнопки в ряд)."""
    buttons = []
    row = []
    for label, _date_str in upcoming_days(7):
        row.append(KeyboardButton(text=label))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


def get_barbers_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора барбера + «Любой»."""
    buttons = [[KeyboardButton(text=b)] for b in BARBERS]
    buttons.append([KeyboardButton(text="Любой")])
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


def get_time_slots_keyboard(slots: list) -> ReplyKeyboardMarkup:
    """Клавиатура свободных слотов времени."""
    buttons = []
    row = []
    for i, slot in enumerate(slots, 1):
        row.append(KeyboardButton(text=slot))
        if i % 3 == 0:  # по 3 кнопки в ряд
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton(text="Отмена")])
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


def get_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения."""
    buttons = [
        [KeyboardButton(text="Подтвердить")],
        [KeyboardButton(text="Начать заново")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


def get_phone_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отправки телефона."""
    buttons = [[KeyboardButton(text="Отправить телефон", request_contact=True)]]
    buttons.append([KeyboardButton(text="Ввести вручную")])
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


# ==================== INLINE-КЛАВИАТУРЫ ====================

def get_reminder_inline_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    """Напоминание: Готов / Не готов / Перенести."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Готов", callback_data=f"rem_yes|{booking_id}"),
            InlineKeyboardButton(text="❌ Не готов", callback_data=f"rem_no|{booking_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Перенести", callback_data=f"rem_move|{booking_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_my_bookings_keyboard(bookings: list) -> InlineKeyboardMarkup:
    """Список записей клиента с кнопками отмены."""
    buttons = []
    for b in bookings:
        # b = (id, user_id, name, phone, service, barber, date, time, status, ...)
        booking_id = b[0]
        label = f"{b[6]} {b[7]} — {b[4]} ({b[5]})"
        buttons.append([
            InlineKeyboardButton(text=f"❌ {label}", callback_data=f"cancel|{booking_id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)