from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Order:
    external_id: str
    title: str
    description: str
    url: str
    source: str
    category: str
    created_at: datetime
