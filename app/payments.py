from __future__ import annotations

import base64
import uuid

import httpx


class YooKassa:
    def __init__(self, shop_id: str, secret_key: str, return_url: str) -> None:
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.return_url = return_url

    async def create_subscription_payment(self, user_id: int, amount: float = 690.0) -> dict:
        if not self.shop_id or not self.secret_key:
            return {"id": "demo-payment", "confirmation_url": "https://yookassa.ru"}

        key = base64.b64encode(f"{self.shop_id}:{self.secret_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {key}",
            "Idempotence-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        payload = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": self.return_url},
            "description": f"Freelance Radar PRO для user_id={user_id}",
            "metadata": {"user_id": str(user_id)},
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.yookassa.ru/v3/payments", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        return {"id": data["id"], "confirmation_url": data["confirmation"]["confirmation_url"]}
