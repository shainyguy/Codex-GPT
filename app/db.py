from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    categories TEXT NOT NULL DEFAULT 'Python,Design',
                    trial_started_at TEXT,
                    subscription_until TEXT
                );

                CREATE TABLE IF NOT EXISTS seen_orders (
                    user_id INTEGER NOT NULL,
                    external_id TEXT NOT NULL,
                    PRIMARY KEY (user_id, external_id)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    payment_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    amount REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def ensure_user(self, user_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, trial_started_at)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, now),
            )
            await db.commit()

    async def get_categories(self, user_id: int) -> list[str]:
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT categories FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
        return [x.strip() for x in (row[0] if row else "Python,Design").split(",") if x.strip()]

    async def set_categories(self, user_id: int, categories: Iterable[str]) -> None:
        value = ",".join(sorted(set(categories)))
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET categories = ? WHERE user_id = ?", (value, user_id)
            )
            await db.commit()

    async def is_active(self, user_id: int) -> bool:
        await self.ensure_user(user_id)
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT trial_started_at, subscription_until FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()

        trial_started = datetime.fromisoformat(row[0])
        if now <= trial_started + timedelta(days=3):
            return True

        if row[1]:
            subscription_until = datetime.fromisoformat(row[1])
            return now <= subscription_until
        return False

    async def activate_subscription(self, user_id: int, days: int = 30) -> None:
        now = datetime.now(timezone.utc)
        until = now + timedelta(days=days)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET subscription_until = ? WHERE user_id = ?",
                (until.isoformat(), user_id),
            )
            await db.commit()

    async def mark_seen(self, user_id: int, external_id: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    "INSERT INTO seen_orders (user_id, external_id) VALUES (?, ?)",
                    (user_id, external_id),
                )
                await db.commit()
                return False
            except aiosqlite.IntegrityError:
                return True

    async def users(self) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def add_payment(self, payment_id: str, user_id: int, amount: float, status: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO payments (payment_id, user_id, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (payment_id, user_id, amount, status, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()

    async def payment_user(self, payment_id: str) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT user_id FROM payments WHERE payment_id = ?", (payment_id,)
            )
            row = await cursor.fetchone()
        return row[0] if row else None
