from __future__ import annotations

import asyncio
import hashlib
import logging
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application

from app.db import Database
from app.sources.base import Source

logger = logging.getLogger(__name__)


class Radar:
    def __init__(
        self,
        app: Application,
        db: Database,
        sources: list[Source],
        poll_interval: int,
        orders_cache: dict[str, str],
    ) -> None:
        self.app = app
        self.db = db
        self.sources = sources
        self.poll_interval = poll_interval
        self.orders_cache = orders_cache

    async def run(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(self.poll_interval)

    async def tick(self) -> None:
        users = await self.db.users()
        if not users:
            return

        for source in self.sources:
            try:
                orders = await source.fetch()
            except Exception as exc:
                logger.warning("Source %s failed: %s", source.name, exc)
                continue

            for user_id in users:
                if not await self.db.is_active(user_id):
                    continue
                categories = await self.db.get_categories(user_id)
                for order in orders:
                    if order.category not in categories:
                        continue
                    is_seen = await self.db.mark_seen(user_id, order.external_id)
                    if is_seen:
                        continue

                    token = hashlib.sha1(order.external_id.encode()).hexdigest()[:24]
                    self.orders_cache[token] = f"{order.title}\n{order.description}\n{order.url}"
                    keyboard = InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("Открыть заказ", url=order.url)],
                            [InlineKeyboardButton("Сгенерировать отклик", callback_data=f"gen:{token}")],
                        ]
                    )
                    text = (
                        f"🔥 {escape(order.title)}\n"
                        f"Источник: {escape(order.source)}\n"
                        f"Категория: {escape(order.category)}\n"
                        f"{escape(order.description[:500])}"
                    )
                    try:
                        await self.app.bot.send_message(user_id, text, reply_markup=keyboard)
                    except BadRequest as exc:
                        logger.warning(
                            "Telegram rejected message for user %s (order %s): %s",
                            user_id,
                            order.external_id,
                            exc,
                        )
