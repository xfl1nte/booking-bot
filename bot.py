import asyncio
import logging
import os
import re
from datetime import date, timedelta

import phonenumbers
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Не найден BOT_TOKEN в файле .env")

dp = Dispatcher()

# ---------- Настройки салона ----------

SERVICES = {
    "Маникюр": 1500,
    "Маникюр с покрытием": 2000,
    "Педикюр": 1800,
}
TIME_SLOTS = ["10:00", "12:00", "14:00", "16:00", "18:00"]
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ---------- Шаги записи ----------

class Booking(StatesGroup):
    service = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


# ---------- Клавиатуры ----------

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Записаться")],
        [KeyboardButton(text="Услуги и цены"), KeyboardButton(text="Контакты")],
    ],
    resize_keyboard=True,
)

phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отправить мой номер", request_contact=True)],
        [KeyboardButton(text="Назад")],
    ],
    resize_keyboard=True,
)


def make_keyboard(buttons, per_row=2):
    """Собирает клавиатуру из списка текстов и добавляет кнопку «Назад»."""
    keyboard = []
    for i in range(0, len(buttons), per_row):
        row = buttons[i:i + per_row]
        keyboard.append([KeyboardButton(text=text) for text in row])
    keyboard.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ---------- Вспомогательные функции ----------

def get_dates(days=7):
    """Возвращает ближайшие дни, начиная с завтрашнего, например «Пн 10.11»."""
    today = date.today()
    result = []
    for i in range(1, days + 1):
        day = today + timedelta(days=i)
        result.append(f"{WEEKDAYS[day.weekday()]} {day.strftime('%d.%m')}")
    return result


def is_valid_name(name):
    """Имя: от 2 до 50 символов, только буквы, пробелы и дефисы."""
    if not 2 <= len(name) <= 50:
        return False
    only_allowed = all(ch.isalpha() or ch in " -" for ch in name)
    has_letters = any(ch.isalpha() for ch in name)
    return only_allowed and has_letters


def normalize_phone(text, region="RU"):
    """Приводит номер к виду +79991234567. Возвращает None, если номер некорректный."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    # Только цифры 0-9, обычные пробелы, скобки, дефисы и «+» в начале
    if not re.fullmatch(r"\+?[0-9 ()-]+", text):
        return None
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


# ---------- Вопросы на каждом шаге ----------

async def ask_service(message: Message, state: FSMContext, error=""):
    await state.set_state(Booking.service)
    await message.answer(error + "Выберите услугу:", reply_markup=make_keyboard(list(SERVICES)))


async def ask_date(message: Message, state: FSMContext, error=""):
    await state.set_state(Booking.date)
    await message.answer(error + "Выберите дату:", reply_markup=make_keyboard(get_dates()))


async def ask_time(message: Message, state: FSMContext, error=""):
    await state.set_state(Booking.time)
    await message.answer(error + "Выберите время:", reply_markup=make_keyboard(TIME_SLOTS, per_row=3))


async def ask_name(message: Message, state: FSMContext, error=""):
    await state.set_state(Booking.name)
    await message.answer(error + "Как вас зовут?", reply_markup=make_keyboard([]))


async def ask_phone(message: Message, state: FSMContext, error=""):
    await state.set_state(Booking.phone)
    await message.answer(
        error + "Отправьте номер телефона кнопкой ниже или напишите его вручную:",
        reply_markup=phone_keyboard,
    )


async def ask_confirm(message: Message, state: FSMContext, error=""):
    data = await state.get_data()
    await state.set_state(Booking.confirm)
    await message.answer(
        error + "Проверьте запись:\n\n"
        f"Услуга: {data['service']} — {SERVICES[data['service']]} ₽\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n\n"
        "Всё верно?",
        reply_markup=make_keyboard(["Подтвердить"]),
    )


# С какого шага на какой возвращает кнопка «Назад»
PREVIOUS_STEP = {
    Booking.date.state: ask_service,
    Booking.time.state: ask_date,
    Booking.name.state: ask_time,
    Booking.phone.state: ask_name,
    Booking.confirm.state: ask_phone,
}


# ---------- Общие команды ----------

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! "
        "Я помогу записаться к мастеру. Выберите, что вас интересует:",
        reply_markup=main_keyboard,
    )


@dp.message(F.text == "Назад")
async def go_back(message: Message, state: FSMContext):
    current = await state.get_state()
    previous = PREVIOUS_STEP.get(current)
    if previous is None:
        # Первый шаг записи или пользователь вообще не в записи
        await state.clear()
        await message.answer("Главное меню:", reply_markup=main_keyboard)
        return
    await previous(message, state)


@dp.message(F.text == "Услуги и цены")
@dp.message(Command("services"))
async def services(message: Message):
    lines = [f"{name} — {price} ₽" for name, price in SERVICES.items()]
    await message.answer("\n".join(lines))


@dp.message(F.text == "Контакты")
@dp.message(Command("contacts"))
async def contacts(message: Message):
    await message.answer("Адрес: ул. Примерная, 1\nТелефон: +7 900 000-00-00")


# ---------- Запись ----------

@dp.message(F.text == "Записаться")
@dp.message(Command("book"))
async def book_start(message: Message, state: FSMContext):
    await state.clear()
    await ask_service(message, state)


@dp.message(Booking.service)
async def choose_service(message: Message, state: FSMContext):
    if message.text not in SERVICES:
        await ask_service(message, state, error="Пожалуйста, выберите услугу кнопкой. ")
        return
    await state.update_data(service=message.text)
    await ask_date(message, state)


@dp.message(Booking.date)
async def choose_date(message: Message, state: FSMContext):
    if message.text not in get_dates():
        await ask_date(message, state, error="Пожалуйста, выберите дату кнопкой. ")
        return
    await state.update_data(date=message.text)
    await ask_time(message, state)


@dp.message(Booking.time)
async def choose_time(message: Message, state: FSMContext):
    if message.text not in TIME_SLOTS:
        await ask_time(message, state, error="Пожалуйста, выберите время кнопкой. ")
        return
    await state.update_data(time=message.text)
    await ask_name(message, state)


@dp.message(Booking.name)
async def enter_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not is_valid_name(name):
        await ask_name(message, state, error="Имя должно состоять из букв. ")
        return
    await state.update_data(name=name)
    await ask_phone(message, state)


@dp.message(Booking.phone)
async def enter_phone(message: Message, state: FSMContext):
    if message.contact:
        # Принимаем только собственный контакт, а не пересланный чужой
        if message.contact.user_id != message.from_user.id:
            await ask_phone(message, state, error="Пожалуйста, отправьте свой номер. ")
            return
        raw_phone = message.contact.phone_number
        # Telegram иногда присылает номер без «+»
        if not raw_phone.startswith("+"):
            raw_phone = "+" + raw_phone
    else:
        raw_phone = message.text

    phone = normalize_phone(raw_phone)
    if phone is None:
        await ask_phone(message, state, error="Не похоже на номер телефона. ")
        return
    await state.update_data(phone=phone)
    await ask_confirm(message, state)


@dp.message(Booking.confirm, F.text == "Подтвердить")
async def confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await message.answer(
        f"Готово! Вы записаны на {data['date']} в {data['time']}. Ждём вас!",
        reply_markup=main_keyboard,
    )


@dp.message(Booking.confirm)
async def confirm_other(message: Message, state: FSMContext):
    await ask_confirm(
        message, state,
        error="Нажмите «Подтвердить» или «Назад», чтобы что-то изменить.\n\n",
    )


# ---------- Всё остальное ----------

@dp.message()
async def unknown(message: Message):
    await message.answer(
        "Не понял вас. Воспользуйтесь кнопками меню или отправьте /start.",
        reply_markup=main_keyboard,
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="book", description="Записаться"),
        BotCommand(command="services", description="Услуги и цены"),
        BotCommand(command="contacts", description="Контакты"),
    ])
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())