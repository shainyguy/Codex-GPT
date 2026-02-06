from __future__ import annotations

import httpx


class GigaChatClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate_cover_letter(self, order_text: str) -> str:
        if not self.api_key:
            return "Подключите GIGACHAT_API_KEY, чтобы включить автогенерацию отклика."

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты senior-фрилансер. Пиши короткий, уверенный, персонализированный отклик на русском языке.",
                },
                {"role": "user", "content": f"Сделай отклик на заказ:\n{order_text}"},
            ],
            "temperature": 0.6,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
