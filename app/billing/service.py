from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.models import (
    BillingPeriod,
    Payment,
    Subscription,
    SubscriptionStatus,
    TokenUsageLog,
    TokenWallet,
)


MODEL_PRICES = {
    'openai:gpt-4o-mini': 2,
    'anthropic:claude-3-5-haiku-latest': 3,
    'gemini:gemini-1.5-flash': 2,
    'mistral:mistral-small-latest': 2,
    'cohere:command-r-plus': 3,
    'deepseek:deepseek-chat': 1,
    'yandexgpt:yandexgpt-lite': 2,
    'gigachat:GigaChat': 1,
}

TARIFF_LIMITS = {
    'free': 40000,
    'weekly': 300000,
    'monthly': 1500000,
}


async def ensure_subscription_access(db: AsyncSession, user_id: int) -> Subscription:
    sub = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    now = datetime.now(timezone.utc)
    if not sub:
        raise HTTPException(status_code=403, detail='No subscription')
    if sub.status == SubscriptionStatus.CANCELED:
        raise HTTPException(status_code=403, detail='Subscription canceled')
    if sub.status == SubscriptionStatus.TRIAL and sub.trial_ends_at and sub.trial_ends_at < now:
        sub.status = SubscriptionStatus.EXPIRED
    if sub.current_period_end and sub.current_period_end < now and sub.status == SubscriptionStatus.ACTIVE:
        sub.status = SubscriptionStatus.EXPIRED
    if sub.status == SubscriptionStatus.EXPIRED:
        raise HTTPException(status_code=403, detail='Subscription expired')
    return sub


async def debit_tokens(
    db: AsyncSession,
    user_id: int,
    agent_id: int | None,
    model_name: str,
    request_tokens: int,
    response_tokens: int,
) -> None:
    total = request_tokens + response_tokens
    key = model_name
    price = MODEL_PRICES.get(key, 2)
    amount = total * price

    wallet = await db.scalar(select(TokenWallet).where(TokenWallet.user_id == user_id, TokenWallet.model_name == key).with_for_update())
    if wallet is None:
        wallet = TokenWallet(user_id=user_id, model_name=key, balance=0)
        db.add(wallet)
        await db.flush()

    if wallet.balance < amount:
        raise HTTPException(status_code=402, detail='Insufficient token balance')

    wallet.balance -= amount
    db.add(
        TokenUsageLog(
            user_id=user_id,
            agent_id=agent_id,
            model_name=key,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total,
            meta={'cost': amount},
        )
    )


async def grant_tokens(db: AsyncSession, user_id: int, model_name: str, amount: int) -> None:
    wallet = await db.scalar(select(TokenWallet).where(TokenWallet.user_id == user_id, TokenWallet.model_name == model_name).with_for_update())
    if not wallet:
        wallet = TokenWallet(user_id=user_id, model_name=model_name, balance=0)
        db.add(wallet)
    wallet.balance += amount


async def activate_subscription(db: AsyncSession, payment: Payment, period: BillingPeriod) -> None:
    sub = await db.scalar(select(Subscription).where(Subscription.user_id == payment.user_id))
    now = datetime.now(timezone.utc)
    sub.status = SubscriptionStatus.ACTIVE
    sub.tariff = 'weekly' if period == BillingPeriod.WEEK else 'monthly'
    sub.period = period
    sub.current_period_end = now.replace(microsecond=0)
    if period == BillingPeriod.WEEK:
        from datetime import timedelta
        sub.current_period_end = now + timedelta(days=7)
    else:
        from datetime import timedelta
        sub.current_period_end = now + timedelta(days=30)
