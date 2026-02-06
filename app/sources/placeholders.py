from __future__ import annotations

from app.sources.base import Source


class KworkSource(Source):
    name = "Kwork"

    async def fetch(self):
        return []


class FLSource(Source):
    name = "FL"

    async def fetch(self):
        return []
