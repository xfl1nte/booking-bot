import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

# Читаем токен из файла .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Не найден BOT_TOKEN в файле .env")

# Диспетчер решает, какая функция ответит на какое сообщение
dp = Dispatcher()

# Клавиатура с кнопками под полем ввода
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Записаться")],
        [KeyboardButton(text="Услуги и цены"), KeyboardButton(text="Контакты")],
    ],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! "
        "Я помогу записаться к мастеру. Выберите, что вас интересует:",
        reply_markup=main_keyboard,
    )


@dp.message(F.text == "Записаться")
async def book(message: Message):
    await message.answer("Запись скоро появится, этот раздел в разработке.")


@dp.message(F.text == "Услуги и цены")
async def services(message: Message):
    await message.answer(
        "Маникюр — 1500 ₽\n"
        "Покрытие гель-лаком — 2000 ₽\n"
        "Дизайн — от 300 ₽"
    )


@dp.message(F.text == "Контакты")
async def contacts(message: Message):
    await message.answer("Адрес: ул. Примерная, 1\nТелефон: +7 900 000-00-00")


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())