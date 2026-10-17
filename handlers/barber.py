"""
Админ-панель владельца: /admin.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import config
import database as db
from utils import today_str, tomorrow_str, upcoming_days, friendly_day_label


router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, что это владелец."""
    return user_id == config.ADMIN_ID


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню админа."""
    buttons = [
        [InlineKeyboardButton(text="📅 Записи (выбрать день)", callback_data="adm_days")],
        [InlineKeyboardButton(text="💰 Выручка за день (выбрать день)", callback_data="adm_revdays")],
        [InlineKeyboardButton(text="💈 Выручка по барберу", callback_data="adm_revenue_barber")],
        [InlineKeyboardButton(text="📊 Отчёт за неделю", callback_data="adm_report_week")],
        [InlineKeyboardButton(text="📊 Отчёт за месяц", callback_data="adm_report_month")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return

    await message.answer(
        "🔧 Админ-панель\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "adm_today")
async def adm_today(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_bookings(callback, today_str(), "сегодня")


@router.callback_query(F.data == "adm_tomorrow")
async def adm_tomorrow(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_bookings(callback, tomorrow_str(), "завтра")


async def _show_bookings(callback: CallbackQuery, date_str: str, label: str):
    bookings = await db.get_bookings_by_date(date_str)
    if not bookings:
        await callback.message.edit_text(
            f"📅 На {label} ({date_str}) записей нет.",
            reply_markup=admin_menu_keyboard(),
        )
        await callback.answer()
        return

    lines = [f"📅 Записи на {label} ({date_str}):\n"]
    for b in bookings:
        # b = (id, user_id, name, phone, service, barber, date, time, status, ...)
        lines.append(
            f"⏰ {b[7]} — {b[2]}, {b[4]}\n"
            f"  💈 {b[5]} | 📞 {b[3]} | статус: {b[8]}\n"
        )

    text = "\n".join(lines)
    # Telegram ограничивает длину сообщения 4096 символами
    if len(text) > 4000:
        text = text[:4000] + "\n…(список обрезан)"

    await callback.message.edit_text(text, parse_mode="Markdown",
                                     reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_revenue_today")
async def adm_revenue_today(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_revenue(callback, today_str(), "сегодня")


@router.callback_query(F.data == "adm_revenue_tomorrow")
async def adm_revenue_tomorrow(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_revenue(callback, tomorrow_str(), "завтра")


async def _show_revenue(callback: CallbackQuery, date_str: str, label: str):
    bookings = await db.get_bookings_by_date(date_str)
    total = await db.get_revenue_by_date(date_str)

    # Разбивка по барберам
    by_barber = {}
    for b in bookings:
        barber = b[5]
        service = b[4]
        price = config.SERVICES_PRICES.get(service, 0)
        by_barber[barber] = by_barber.get(barber, 0) + price

    text = f"💰 Выручка за {label} ({date_str}): **{total} ₽**\n\n"
    if by_barber:
        text += "По барберам:\n"
        for barber_name, amount in by_barber.items():
            text += f"💈 {barber_name}: {amount} ₽\n"
    else:
        text += "Записей нет."

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


# ==================== ВЫБОР ДНЯ (ЗАПИСИ / ВЫРУЧКА) ====================

def day_picker_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Инлайн-календарь на ближайшие 7 дней."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"{prefix}|{date_str}")]
        for label, date_str in upcoming_days(7)
    ]
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="adm_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "adm_menu")
async def adm_menu(callback: CallbackQuery):
    """Возврат в главное меню админа."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            "🔧 Админ-панель\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=admin_menu_keyboard(),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "adm_days")
async def adm_days(callback: CallbackQuery):
    """Показывает календарь для выбора дня записей."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            "📅 Выберите день для просмотра записей:",
            reply_markup=day_picker_keyboard("adm_day"),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("adm_day|"))
async def adm_day(callback: CallbackQuery):
    """Записи за выбранный день."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    date_str = callback.data.split("|")[1]
    try:
        await _show_bookings(callback, date_str, friendly_day_label(date_str))
    except Exception:
        await callback.answer()


@router.callback_query(F.data == "adm_revdays")
async def adm_revdays(callback: CallbackQuery):
    """Показывает календарь для выбора дня выручки."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            "💰 Выберите день для просмотра выручки:",
            reply_markup=day_picker_keyboard("adm_revday"),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("adm_revday|"))
async def adm_revday(callback: CallbackQuery):
    """Выручка за выбранный день."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    date_str = callback.data.split("|")[1]
    try:
        await _show_revenue(callback, date_str, friendly_day_label(date_str))
    except Exception:
        await callback.answer()