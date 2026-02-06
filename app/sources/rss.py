from __future__ import annotations

from datetime import datetime, timezone

import feedparser

from app.models import Order
from app.sources.base import Source


class RSSSource(Source):
    def __init__(self, name: str, url: str, category_hint: str) -> None:
        self.name = name
        self.url = url
        self.category_hint = category_hint

    async def fetch(self) -> list[Order]:
        parsed = feedparser.parse(self.url)
        orders: list[Order] = []
        for entry in parsed.entries[:20]:
            eid = entry.get("id") or entry.get("link")
            if not eid:
                continue
            orders.append(
                Order(
                    external_id=f"{self.name.lower()}:{eid}",
                    title=entry.get("title", "Без названия"),
                    description=entry.get("summary", ""),
                    url=entry.get("link", self.url),
                    source=self.name,
                    category=self.category_hint,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return orders
