from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from app.models import Order


class Source(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> Sequence[Order]:
        raise NotImplementedError
