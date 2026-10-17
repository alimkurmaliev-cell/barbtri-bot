"""
Логика клиента: запись, мои записи, отмена, напоминания.
"""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

import config
import database as db
from keyboards import (
    get_services_keyboard,
    get_dates_keyboard,
    get_barbers_keyboard,
    get_time_slots_keyboard,
    get_confirmation_keyboard,
    get_phone_keyboard,
    get_reminder_inline_keyboard,
    get_my_bookings_keyboard,
)
from utils import (
    resolve_date_string,
    validate_time_format,
    parse_human_time,
    validate_phone,
    validate_name,
    now_str,
    today_str,
)

logger = logging.getLogger(__name__)
router = Router()

# Команды (со слэшем) не перехватываются шагами записи — идут в свои хэндлеры
NOT_COMMAND = ~F.text.startswith("/")


class BookingStates(StatesGroup):
    name = State()
    phone = State()
    service = State()
    barber = State()
    date = State()
    time = State()
    confirm = State()


# ==================== СТАРТ ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(BookingStates.name)
    await message.answer(
        "Здравствуйте! 👋 Добро пожаловать в наш барбершоп.\n\n"
        "Я помогу вам записаться к мастеру.\n"
        "Пожалуйста, введите ваше имя:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


# ==================== ШАГ 1: ИМЯ ====================

@router.message(BookingStates.name, NOT_COMMAND)
async def process_name(message: Message, state: FSMContext):
    name = validate_name(message.text or "")
    if not name:
        await message.answer(
            "Пожалуйста, введите корректное имя (только буквы, от 2 до 50 символов):"
        )
        return

    await state.update_data(name=name)
    await state.set_state(BookingStates.phone)
    await message.answer(
        f"Отлично, {name}! Оставьте ваш номер телефона для связи.\n"
        "Можно отправить кнопкой ниже или ввести вручную:",
        reply_markup=get_phone_keyboard(),
    )


# ==================== ШАГ 2: ТЕЛЕФОН ====================

@router.message(BookingStates.phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = validate_phone(message.contact.phone_number or "")
    if not phone:
        await message.answer("Не удалось распознать номер. Введите вручную:")
        return
    await state.update_data(phone=phone)
    await _ask_service(message, state)


@router.message(BookingStates.phone, NOT_COMMAND)
async def process_phone_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "Ввести вручную":
        await message.answer(
            "Введите номер телефона в формате +7XXXXXXXXXX:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    phone = validate_phone(text)
    if not phone:
        await message.answer(
            "Некорректный номер. Введите в формате +7XXXXXXXXXX "
            "или нажмите «Отправить телефон»:",
            reply_markup=get_phone_keyboard(),
        )
        return

    await state.update_data(phone=phone)
    await _ask_service(message, state)


async def _ask_service(message: Message, state: FSMContext):
    await state.set_state(BookingStates.service)
    await message.answer(
        "Выберите желаемую услугу:",
        reply_markup=get_services_keyboard(),
    )


# ==================== ШАГ 3: УСЛУГА ====================

@router.message(BookingStates.service, NOT_COMMAND)
async def process_service(message: Message, state: FSMContext):
    service = (message.text or "").strip()
    if service not in config.SERVICES:
        await message.answer(
            "Пожалуйста, выберите услугу из списка:",
            reply_markup=get_services_keyboard(),
        )
        return

    await state.update_data(service=service)
    await state.set_state(BookingStates.barber)
    await message.answer(
        "Выберите мастера (или «Любой» — подберём свободного):",
        reply_markup=get_barbers_keyboard(),
    )


# ==================== ШАГ 4: БАРБЕР ====================

@router.message(BookingStates.barber, NOT_COMMAND)
async def process_barber(message: Message, state: FSMContext):
    barber = (message.text or "").strip()
    if barber != "Любой" and barber not in config.BARBERS:
        await message.answer(
            "Пожалуйста, выберите мастера из списка:",
            reply_markup=get_barbers_keyboard(),
        )
        return

    await state.update_data(barber=barber)
    await state.set_state(BookingStates.date)
    await message.answer(
        "На какой день хотите записаться?\n"
        "Выберите день из ближайших 7 дней или введите дату вручную (ДД.ММ.ГГГГ):",
        reply_markup=get_dates_keyboard(),
    )


# ==================== ШАГ 5: ДАТА ====================

@router.message(BookingStates.date, NOT_COMMAND)
async def process_date(message: Message, state: FSMContext):
    date_str = resolve_date_string(message.text or "")
    if not date_str:
        await message.answer(
            "Пожалуйста, выберите дату кнопкой или введите в формате ДД.ММ.ГГГГ:",
            reply_markup=get_dates_keyboard(),
        )
        return

    data = await state.get_data()
    barber = data.get("barber")

    # Собираем свободные слоты
    if barber == "Любой":
        # Слот свободен, если хотя бы у одного барбера он свободен
        slots_set = set()
        for b in config.BARBERS:
            free = await db.get_free_slots(b, date_str)
            slots_set.update(free)
        slots = sorted(slots_set)
    else:
        slots = await db.get_free_slots(barber, date_str)

    # Если дата сегодня — убираем прошедшие слоты
    if date_str == today_str():
        now = datetime.now()
        now_hm = f"{now.hour:02d}:{now.minute:02d}"
        slots = [s for s in slots if s > now_hm]

    if not slots:
        await message.answer(
            "На эту дату свободных слотов нет. Выберите другую дату:",
            reply_markup=get_dates_keyboard(),
        )
        return

    await state.update_data(date=date_str, slots=slots)
    await state.set_state(BookingStates.time)
    await message.answer(
        f"Свободное время на {date_str}:\nВыберите слот:",
        reply_markup=get_time_slots_keyboard(slots),
    )


# ==================== ШАГ 6: ВРЕМЯ ====================

@router.message(BookingStates.time, NOT_COMMAND)
async def process_time(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "Отмена":
        await state.clear()
        await message.answer("Запись отменена. Напишите /start, чтобы начать заново.",
                             reply_markup=ReplyKeyboardRemove())
        return

    # Пытаемся распознать время — кнопкой или текстом
    time_str = validate_time_format(text) or parse_human_time(text)
    if not time_str:
        await message.answer(
            "Не понял время. Выберите слот кнопкой или напишите, например, 14:00:"
        )
        return

    data = await state.get_data()
    slots = data.get("slots", [])
    if time_str not in slots:
        await message.answer(
            "Это время недоступно. Выберите из свободных слотов:",
            reply_markup=get_time_slots_keyboard(slots),
        )
        return

    await state.update_data(time=time_str)
    await state.set_state(BookingStates.confirm)

    summary = (
        "📋 Проверьте данные записи:\n\n"
        f"👤 Имя: {data.get('name')}\n"
        f"📞 Телефон: {data.get('phone')}\n"
        f"✂️ Услуга: {data.get('service')}\n"
        f"💈 Мастер: {data.get('barber')}\n"
        f"📅 Дата: {data.get('date')}\n"
        f"⏰ Время: {time_str}\n\n"
        "Всё верно?"
    )
    await message.answer(summary, parse_mode="Markdown",
                         reply_markup=get_confirmation_keyboard())


# ==================== ШАГ 7: ПОДТВЕРЖДЕНИЕ ====================

@router.message(BookingStates.confirm, NOT_COMMAND)
async def process_confirm(message: Message, state: FSMContext):
    answer = (message.text or "").strip()

    if answer == "Начать заново":
        await state.clear()
        await state.set_state(BookingStates.name)
        await message.answer("Хорошо, начнём заново.\nВведите ваше имя:",
                             reply_markup=ReplyKeyboardRemove())
        return

    if answer != "Подтвердить":
        await message.answer("Нажмите «Подтвердить» или «Начать заново»:",
                             reply_markup=get_confirmation_keyboard())
        return

    data = await state.get_data()
    barber = data.get("barber")
    date_str = data.get("date")
    time_str = data.get("time")

    # Если «Любой» — выбираем конкретного барбера, у кого слот свободен
    if barber == "Любой":
        chosen = None
        for b in config.BARBERS:
            if await db.is_slot_free(b, date_str, time_str):
                chosen = b
                break
        if not chosen:
            await state.clear()
            await message.answer(
                "К сожалению, это время только что заняли. Начните заново — /start",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        barber = chosen

    # Проверка занятости (на случай гонки)
    if not await db.is_slot_free(barber, date_str, time_str):
        await state.clear()
        await message.answer(
            "К сожалению, это время только что заняли. Начните заново — /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    booking_id = await db.create_booking(
        user_id=message.from_user.id,
        name=data.get("name"),
        phone=data.get("phone"),
        service=data.get("service"),
        barber=barber,
        date=date_str,
        time=time_str,
    )
    await state.clear()

    await message.answer(
        "🎉 Ваша запись создана!\n\n"
        f"bsite: {barber}\n"
        f"📅 {date_str} в {time_str}\n\n"
        "За час и за 5 минут до визита я пришлю напоминание.\n"
        "Посмотреть свои записи: /my",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    logger.info(f"Создана запись #{booking_id} для {message.from_user.id}")


# ==================== МОИ ЗАПИСИ ====================

@router.message(Command("my"))
async def cmd_my(message: Message, state: FSMContext):
    await state.clear()
    bookings = await db.get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer("У вас нет активных записей.\nЗаписаться: /start")
        return

    lines = ["📋 Ваши записи:\n"]
    for b in bookings:
        # b = (id, user_id, name, phone, service, barber, date, time, status, ...)
        lines.append(
            f"• {b[6]} в {b[7]} — {b[4]} у {b[5]} (статус: {b[8]})"
        )
    lines.append("\nНажмите на запись, чтобы отменить её:")
    await message.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_my_bookings_keyboard(bookings),
    )


@router.callback_query(F.data.startswith("cancel|"))
async def process_cancel(callback: CallbackQuery):
    booking_id = int(callback.data.split("|")[1])
    await db.cancel_booking(booking_id)
    await callback.message.edit_text("✅ Запись отменена.")
    await callback.answer()


# ==================== НАПОМИНАНИЯ ====================

@router.callback_query(F.data.startswith("rem_yes|"))
async def reminder_yes(callback: CallbackQuery):
    await callback.message.edit_text("✅ Спасибо! Ждём вас.")
    await callback.answer()


@router.callback_query(F.data.startswith("rem_no|"))
async def reminder_no(callback: CallbackQuery):
    booking_id = int(callback.data.split("|")[1])
    await db.cancel_booking(booking_id)
    await callback.message.edit_text(
        "Жаль, что не получится. Запись отменена. Записаться снова: /start"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rem_move|"))
async def reminder_move(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split("|")[1])
    await db.cancel_booking(booking_id)
    await callback.message.edit_text(
        "🔄 Старая запись отменена. Давайте выберем новое время!"
    )
    await callback.answer()
    await state.clear()
    await state.set_state(BookingStates.name)
    await callback.message.answer(
        "Введите ваше имя для новой записи:",
        reply_markup=ReplyKeyboardRemove(),
    )