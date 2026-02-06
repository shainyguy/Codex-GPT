from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.models import Order
from app.sources.base import Source


class HHSource(Source):
    name = "HH"

    async def fetch(self) -> list[Order]:
        params = {
            "text": "(фриланс OR freelance) (python OR design)",
            "per_page": 20,
            "order_by": "publication_time",
        }
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://api.hh.ru/vacancies", params=params)
            resp.raise_for_status()
            data = resp.json()

        result: list[Order] = []
        for item in data.get("items", []):
            title = item.get("name", "Без названия")
            raw = f"{title} {item.get('snippet', {}).get('requirement', '')}".lower()
            category = "Python" if "python" in raw else "Design"
            result.append(
                Order(
                    external_id=f"hh:{item['id']}",
                    title=title,
                    description=item.get("snippet", {}).get("responsibility") or "",
                    url=item.get("alternate_url", "https://hh.ru"),
                    source=self.name,
                    category=category,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return result
