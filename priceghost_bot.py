# priceghost_bot.py
import logging
import sqlite3
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# ---------------------
# Настройки
# ---------------------
API_TOKEN = "5191951105:AAESbK_-oU4DNWn195_w9uYy6Y_XUSmQiaI"
GIGACHAT_API_KEY = "YOUR_GIGACHAT_API_KEY"

BOT = Bot(token=API_TOKEN)
DP = Dispatcher(BOT)

DB_PATH = "priceghost.db"

# ---------------------
# Логирование
# ---------------------
logging.basicConfig(level=logging.INFO)

# ---------------------
# База данных
# ---------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            platform TEXT,
            current_price REAL,
            last_checked TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            price REAL,
            date TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    conn.close()

# ---------------------
# Парсинг цен
# ---------------------
def get_price_ozon(url: str):
    # Пример: используем JSON API Ozon
    try:
        api_url = f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url={url}"
        r = requests.get(api_url)
        data = r.json()
        price = data['page']['components'][0]['data']['offer']['price']['value']
        return price
    except Exception as e:
        logging.error(f"Ozon parse error: {e}")
        return None

def get_price_wb(url: str):
    # Пример: разбираем артикул из ссылки Wildberries и берём JSON
    try:
        article = url.rstrip("/").split("/")[-1]
        api_url = f"https://card.wb.ru/cards/detail?nm={article}&locale=ru"
        r = requests.get(api_url)
        data = r.json()
        price = data['data']['products'][0]['priceU'] / 100  # в рублях
        return price
    except Exception as e:
        logging.error(f"WB parse error: {e}")
        return None

# ---------------------
# Добавление продукта
# ---------------------
async def add_product(user_id: int, url: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if "ozon.ru" in url:
        platform = "ozon"
        price = get_price_ozon(url)
    elif "wildberries.ru" in url:
        platform = "wb"
        price = get_price_wb(url)
    else:
        return None, "Платформа не поддерживается"

    if price is None:
        return None, "Не удалось получить цену"

    cursor.execute("INSERT INTO products (user_id, url, platform, current_price, last_checked) VALUES (?, ?, ?, ?, datetime('now'))",
                   (user_id, url, platform, price))
    product_id = cursor.lastrowid
    cursor.execute("INSERT INTO price_history (product_id, price, date) VALUES (?, ?, datetime('now'))", (product_id, price))
    conn.commit()
    conn.close()
    return price, None

# ---------------------
# Команды Telegram
# ---------------------
@DP.message(Command(commands=["start"]))
async def start(message: types.Message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (message.from_user.id, message.from_user.username))
    conn.commit()
    conn.close()
    await message.answer("Привет! Пришли мне ссылку на товар с Ozon или Wildberries, и я буду отслеживать цену.")

@DP.message()
async def add_product_handler(message: types.Message):
    url = message.text.strip()
    price, err = await add_product(message.from_user.id, url)
    if err:
        await message.answer(err)
    else:
        await message.answer(f"Товар добавлен. Текущая цена: {price}₽")

# ---------------------
# Проверка цен
# ---------------------
def check_prices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, url, platform, current_price FROM products")
    products = cursor.fetchall()
    for product in products:
        pid, user_id, url, platform, old_price = product
        if platform == "ozon":
            price = get_price_ozon(url)
        elif platform == "wb":
            price = get_price_wb(url)
        else:
            continue
        if price is None:
            continue
        if price < old_price:
            asyncio.run(BOT.send_message(user_id, f"Цена упала с {old_price}₽ до {price}₽\n{url}"))
            cursor.execute("UPDATE products SET current_price=?, last_checked=datetime('now') WHERE id=?", (price, pid))
            cursor.execute("INSERT INTO price_history (product_id, price, date) VALUES (?, ?, datetime('now'))", (pid, price))
    conn.commit()
    conn.close()

# ---------------------
# Планировщик
# ---------------------
scheduler = AsyncIOScheduler()
scheduler.add_job(check_prices, 'interval', hours=24)
scheduler.start()

# ---------------------
# Запуск бота
# ---------------------
if __name__ == "__main__":
    init_db()
    import asyncio
    asyncio.run(DP.start_polling(BOT))
