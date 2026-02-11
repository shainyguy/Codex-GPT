import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_BOT_TOKEN
import requests

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# простая стартовая команда
@dp.message(commands=["start"])
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить WB", callback_data="wb")],
        [InlineKeyboardButton(text="Оплатить ЮKassa", callback_data="pay")]
    ])
    await message.answer("Привет! Я PriceGhost бот.", reply_markup=keyboard)

# обработка нажатий
@dp.callback_query(lambda c: True)
async def process_callback(callback_query):
    data = callback_query.data
    if data == "wb":
        await callback_query.message.answer("WB интеграция пока тестовая.")
        # тут добавим вызовы API Wildberries
    elif data == "pay":
        await callback_query.message.answer("ЮKassa интеграция подключена.")
        # тут добавим создание платежа через Yookassa

# пример запроса к GigaChat
async def giga_chat_response(prompt: str):
    url = "https://api.gigachat.ru/v1/generate"
    headers = {"Authorization": f"Bearer {config.GIGACHAT_API_KEY}"}
    json_data = {"prompt": prompt}
    r = requests.post(url, json=json_data, headers=headers)
    if r.status_code == 200:
        return r.json().get("text", "")
    return "Ошибка ответа GigaChat"

# запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
