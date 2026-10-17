"""
Дополнительные админ-хэндлеры: /revenue и выручка по мастерам.
Панель владельца (/admin) с записями — в handlers/barber.py.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import config
import database as db
from utils import today_str, tomorrow_str, parse_date_word, get_period_dates
from handlers.barber import is_admin, admin_menu_keyboard


router = Router()


def _match_barber(text: str):
    """Ищет барбера по имени без учёта регистра. Возвращает имя или None."""
    for b in config.BARBERS:
        if b.lower() == text.lower():
            return b
    return None


def revenue_barbers_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора мастера для выручки."""
    buttons = [
        [InlineKeyboardButton(text=f"💈 {b}", callback_data=f"rev_barber|{i}")]
        for i, b in enumerate(config.BARBERS)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def revenue_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «выбрать другого мастера»."""
    buttons = [
        [InlineKeyboardButton(text="🔙 Выбрать другого мастера", callback_data="rev_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _barber_revenue_text(barber: str, date_str: str, date_label: str) -> str:
    """Текст с выручкой мастера за дату."""
    rows = await db.get_bookings_by_barber_and_date(barber, date_str)
    if not rows:
        return f"📅 У мастера {barber} на {date_label} записей нет."

    lines = [f"💈 **Выручка {barber} за {date_label}:**\n"]
    total = 0
    for service, time_str in rows:
        price = config.SERVICES_PRICES.get(service, 0)
        total += price
        lines.append(f"⏰ {time_str} — {service} — {price} ₽")

    lines.append(f"\n💰 **Итого: {total} ₽**")
    return "\n".join(lines)


def report_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора отчёта."""
    buttons = [
        [InlineKeyboardButton(text="📊 Общая статистика за неделю", callback_data="rep_all|week")],
        [InlineKeyboardButton(text="📊 Общая статистика за месяц", callback_data="rep_all|month")],
        [InlineKeyboardButton(text="💈 По мастеру за неделю", callback_data="rep_barbers|week")],
        [InlineKeyboardButton(text="💈 По мастеру за месяц", callback_data="rep_barbers|month")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def report_barbers_keyboard(period: str) -> InlineKeyboardMarkup:
    """Выбор мастера для отчёта за период."""
    buttons = [
        [InlineKeyboardButton(text=f"💈 {b}", callback_data=f"rep_barber|{period}|{i}")]
        for i, b in enumerate(config.BARBERS)
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="rep_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def report_back_keyboard(period: str) -> InlineKeyboardMarkup:
    """Назад к выбору мастера / в меню отчётов."""
    buttons = [
        [InlineKeyboardButton(text="🔙 Выбрать другого мастера", callback_data=f"rep_barbers|{period}")],
        [InlineKeyboardButton(text="📋 В меню отчётов", callback_data="rep_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def report_menu_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню отчётов."""
    buttons = [
        [InlineKeyboardButton(text="🔙 В меню отчётов", callback_data="rep_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _barber_report_text(barber: str, period: str) -> str:
    """Отчёт по мастеру за период (7 или 30 дней)."""
    date_from, date_to = get_period_dates(period)
    label = "7 дней" if period == "week" else "30 дней"
    rows = await db.get_bookings_by_barber_and_range(barber, date_from, date_to)

    if not rows:
        return f"💈 У мастера {barber} за {label} ({date_from} — {date_to}) записей нет."

    lines = [f"💈 **Выручка {barber} за {label}** ({date_from} — {date_to})\n"]
    total = 0
    for service, date_str, time_str in rows:
        price = config.SERVICES_PRICES.get(service, 0)
        total += price
        lines.append(f"⏰ {date_str} {time_str} — {service} — {price} ₽")

    lines.append(f"\nЗаписей: {len(rows)}")
    lines.append(f"💰 **Итого: {total} ₽**")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…(список обрезан)"
    return text


@router.message(Command("revenue"))
async def cmd_revenue(message: Message, state: FSMContext):
    """
    Выручка по барберу.
    /revenue Руслан — за сегодня
    /revenue Руслан вчера — за вчера
    /revenue Руслан 08.10 — за конкретную дату
    /revenue Руслан 08.10.2025 — за конкретную дату
    """
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return

    args = (message.text or "").split(maxsplit=2)
    if len(args) < 2:
        # Без аргументов — показываем кнопки выбора мастера
        await message.answer(
            "Выберите мастера для просмотра выручки:",
            reply_markup=revenue_barbers_keyboard(),
        )
        return

    barber = _match_barber(args[1].strip())
    if not barber:
        await message.answer(
            f"Мастер «{args[1]}» не найден.\n"
            f"Доступные: {', '.join(config.BARBERS)}"
        )
        return

    # Определяем дату
    if len(args) >= 3:
        date_str = parse_date_word(args[2].strip())
        if not date_str:
            await message.answer(
                "Не понял дату. Примеры: сегодня, вчера, 08.10, 08.10.2025"
            )
            return
        date_label = f"{args[2].strip()} ({date_str})"
    else:
        date_str = today_str()
        date_label = f"сегодня ({date_str})"

    text = await _barber_revenue_text(barber, date_str, date_label)
    await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "adm_revenue_barber")
async def adm_revenue_barber(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    lines = ["💈 **Выручка по мастерам за сегодня:**\n"]
    date_str = today_str()
    grand_total = 0

    for barber in config.BARBERS:
        rows = await db.get_bookings_by_barber_and_date(barber, date_str)
        barber_total = sum(config.SERVICES_PRICES.get(r[0], 0) for r in rows)
        grand_total += barber_total
        lines.append(f"• {barber}: {barber_total} ₽ ({len(rows)} зап.)")

    lines.append(f"\n💰 **Общая сумма: {grand_total} ₽**")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext):
    """
    Полный отчёт за период.
    /report week — за 7 дней
    /report month — за 30 дней
    """
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        # Без аргументов — меню выбора отчёта
        await message.answer(
            "Выберите отчёт:",
            reply_markup=report_menu_keyboard(),
        )
        return

    if args[1].strip().lower() not in ("week", "month"):
        await message.answer(
            "Укажите период:\n"
            "/report week — за последние 7 дней\n"
            "/report month — за последние 30 дней"
        )
        return

    period = args[1].strip().lower()
    await _send_report(message, period)


@router.callback_query(F.data == "adm_report_week")
async def adm_report_week(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _send_report(callback.message, "week", edit=True)
    await callback.answer()


@router.callback_query(F.data == "adm_report_month")
async def adm_report_month(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _send_report(callback.message, "month", edit=True)
    await callback.answer()


async def _send_report(message: Message, period: str, edit: bool = False, reply_markup=None):
    """Собирает и отправляет отчёт за период."""
    date_from, date_to = get_period_dates(period)
    label = "7 дней" if period == "week" else "30 дней"
    rows = await db.get_all_bookings_by_range(date_from, date_to)
    markup = reply_markup or admin_menu_keyboard()

    if not rows:
        text = f"📊 За последние {label} ({date_from} — {date_to}) записей нет."
        if edit:
            await message.edit_text(text, reply_markup=markup)
        else:
            await message.answer(text)
        return

    # rows: (service, date, time, barber)
    grand_total = 0
    by_barber = {}
    by_service = {}
    for service, date_str, time_str, barber in rows:
        price = config.SERVICES_PRICES.get(service, 0)
        grand_total += price
        by_barber[barber] = by_barber.get(barber, 0) + price
        by_service[service] = by_service.get(service, 0) + price

    lines = [f"📊 **Отчёт за {label}** ({date_from} — {date_to})\n"]
    lines.append(f"Всего записей: {len(rows)}\n")

    lines.append("**По мастерам:**")
    for barber, amount in sorted(by_barber.items(), key=lambda x: -x[1]):
        lines.append(f"💈 {barber}: {amount} ₽")

    lines.append("\n**По услугам:**")
    for service, amount in sorted(by_service.items(), key=lambda x: -x[1]):
        lines.append(f"✂️ {service}: {amount} ₽")

    lines.append(f"\n💰 **Общая выручка: {grand_total} ₽**")
    text = "\n".join(lines)

    if edit:
        await message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=markup,
        )
    else:
        await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data.startswith("rev_barber|"))
async def rev_barber_pick(callback: CallbackQuery):
    """Показывает выручку выбранного мастера (за сегодня)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    try:
        idx = int(callback.data.split("|")[1])
        barber = config.BARBERS[idx]
    except (IndexError, ValueError):
        await callback.answer("Неизвестный мастер", show_alert=True)
        return

    date_str = today_str()
    text = await _barber_revenue_text(barber, date_str, f"сегодня ({date_str})")
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=revenue_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "rev_back")
async def rev_back(callback: CallbackQuery):
    """Возврат к выбору мастера."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите мастера для просмотра выручки:",
        reply_markup=revenue_barbers_keyboard(),
    )
    await callback.answer()


# ==================== МЕНЮ ОТЧЁТОВ ====================

@router.callback_query(F.data == "rep_menu")
async def rep_menu(callback: CallbackQuery):
    """Возврат в меню отчётов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите отчёт:",
        reply_markup=report_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_all|"))
async def rep_all(callback: CallbackQuery):
    """Общая статистика по всем мастерам за период."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    period = callback.data.split("|")[1]
    if period not in ("week", "month"):
        await callback.answer("Неизвестный период", show_alert=True)
        return

    await _send_report(
        callback.message,
        period,
        edit=True,
        reply_markup=report_menu_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_barbers|"))
async def rep_barbers(callback: CallbackQuery):
    """Выбор мастера для отчёта за период."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    period = callback.data.split("|")[1]
    if period not in ("week", "month"):
        await callback.answer("Неизвестный период", show_alert=True)
        return

    label = "неделю" if period == "week" else "месяц"
    await callback.message.edit_text(
        f"Выберите мастера для отчёта за {label}:",
        reply_markup=report_barbers_keyboard(period),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_barber|"))
async def rep_barber_pick(callback: CallbackQuery):
    """Отчёт по выбранному мастеру за период."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    parts = callback.data.split("|")
    period = parts[1]
    try:
        idx = int(parts[2])
        barber = config.BARBERS[idx]
    except (IndexError, ValueError):
        await callback.answer("Неизвестный мастер", show_alert=True)
        return

    if period not in ("week", "month"):
        await callback.answer("Неизвестный период", show_alert=True)
        return

    text = await _barber_report_text(barber, period)
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=report_back_keyboard(period),
    )
    await callback.answer()
