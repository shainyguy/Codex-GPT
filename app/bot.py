from __future__ import annotations

from dataclasses import dataclass, field

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.db import Database
from app.gigachat import GigaChatClient
from app.payments import YooKassa

CATEGORIES = ["Python", "Design"]


@dataclass
class BotDeps:
    db: Database
    gigachat: GigaChatClient
    yookassa: YooKassa
    public_base_url: str
    orders_cache: dict[str, str] = field(default_factory=dict)


def menu_inline(deps: BotDeps) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Python", callback_data="cat:Python")],
            [InlineKeyboardButton("Design", callback_data="cat:Design")],
            [InlineKeyboardButton("Оформить PRO — 690₽/мес", callback_data="pay")],
            [
                InlineKeyboardButton(
                    "Открыть мини-приложение",
                    web_app=WebAppInfo(url=f"{deps.public_base_url}/index.html"),
                )
            ],
        ]
    )


def menu_reply(deps: BotDeps) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🌐 Мини-приложение", web_app=WebAppInfo(url=f"{deps.public_base_url}/index.html"))]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: BotDeps = context.application.bot_data["deps"]
    user_id = update.effective_user.id
    await deps.db.ensure_user(user_id)
    await update.message.reply_text(
        "Добро пожаловать в Freelance Radar. Выбери категории для мониторинга:",
        reply_markup=menu_inline(deps),
    )
    await update.message.reply_text(
        "Быстрый доступ к мини-приложению закреплён снизу как кнопка.",
        reply_markup=menu_reply(deps),
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: BotDeps = context.application.bot_data["deps"]
    await update.message.reply_text("Главное меню:", reply_markup=menu_inline(deps))
    await update.message.reply_text("Кнопка мини-приложения:", reply_markup=menu_reply(deps))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: BotDeps = context.application.bot_data["deps"]
    user_id = update.effective_user.id
    active = await deps.db.is_active(user_id)
    categories = await deps.db.get_categories(user_id)
    await update.message.reply_text(
        f"Статус: {'активен' if active else 'требуется PRO'}\nКатегории: {', '.join(categories)}"
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: BotDeps = context.application.bot_data["deps"]
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("cat:"):
        cat = data.split(":", 1)[1]
        current = set(await deps.db.get_categories(user_id))
        if cat in current:
            current.remove(cat)
        else:
            current.add(cat)
        await deps.db.set_categories(user_id, current or CATEGORIES)
        await query.edit_message_text(
            f"Категории обновлены: {', '.join(sorted(current or CATEGORIES))}"
        )
        return

    if data == "pay":
        payment = await deps.yookassa.create_subscription_payment(user_id)
        await deps.db.add_payment(payment["id"], user_id, 690.0, "pending")
        await query.message.reply_text(f"Оплатите подписку: {payment['confirmation_url']}")
        return

    if data.startswith("gen:"):
        token = data.split(":", 1)[1]
        order_text = deps.orders_cache.get(token, "Описание заказа недоступно.")
        answer = await deps.gigachat.generate_cover_letter(order_text)
        await query.message.reply_text(f"✍️ Готовый отклик:\n\n{answer}")



def setup_handlers(app: Application, deps: BotDeps) -> None:
    app.bot_data["deps"] = deps
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(on_callback))
