from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from telegram.ext import Application
import uvicorn

from app.bot import BotDeps, setup_handlers
from app.config import load_settings
from app.db import Database
from app.gigachat import GigaChatClient
from app.payments import YooKassa
from app.radar import Radar
from app.sources.hh import HHSource
from app.sources.placeholders import FLSource, KworkSource
from app.sources.rss import RSSSource

load_dotenv()
logging.basicConfig(level=logging.INFO)

settings = load_settings()
db = Database(settings.database_path)
gigachat = GigaChatClient(settings.gigachat_base_url, settings.gigachat_api_key, settings.gigachat_model)
yookassa = YooKassa(settings.yookassa_shop_id, settings.yookassa_secret_key, settings.yookassa_return_url)

tg_app = Application.builder().token(settings.bot_token).build()
deps = BotDeps(db=db, gigachat=gigachat, yookassa=yookassa, public_base_url=settings.public_base_url)
setup_handlers(tg_app, deps)

sources = [
    HHSource(),
    RSSSource("Habr", "https://career.habr.com/vacancies?q=python&type=all.rss", "Python"),
    RSSSource("Telegram", "https://rsshub.app/telegram/channel/freelance_choice", "Design"),
    KworkSource(),
    FLSource(),
]
radar = Radar(tg_app, db, sources, settings.poll_interval_seconds, deps.orders_cache)

api = FastAPI(title="Freelance Radar")


@api.get("/")
async def root() -> dict:
    return {"ok": True, "service": "freelance-radar"}


@api.get("/index.html")
async def index() -> FileResponse:
    return FileResponse("index.html")


@api.post("/webhook/yookassa")
async def yookassa_webhook(request: Request) -> dict:
    payload = await request.json()
    event = payload.get("event")
    obj = payload.get("object", {})
    if event == "payment.succeeded":
        payment_id = obj.get("id")
        user_id = await db.payment_user(payment_id)
        if user_id:
            await db.activate_subscription(user_id)
            await db.add_payment(payment_id, user_id, 690.0, "succeeded")
            await tg_app.bot.send_message(user_id, "✅ Оплата прошла. PRO активирован на 30 дней.")
    return {"ok": True}


async def run_all() -> None:
    await db.init()
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    radar_task = asyncio.create_task(radar.run())
    config = uvicorn.Config(api, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    api_task = asyncio.create_task(server.serve())

    try:
        await asyncio.gather(radar_task, api_task)
    finally:
        radar_task.cancel()
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()


if __name__ == "__main__":
    asyncio.run(run_all())
