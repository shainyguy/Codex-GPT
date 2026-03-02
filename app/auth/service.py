from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import LoginRequest, RegisterRequest
from app.core.config import get_settings
from app.core.models import Subscription, SubscriptionStatus, User
from app.core.security import create_access_token, hash_password, verify_password


settings = get_settings()


async def register_user(data: RegisterRequest, db: AsyncSession) -> str:
    exists = await db.scalar(select(User.id).where(User.email == data.email))
    if exists:
        raise HTTPException(status_code=409, detail='User already exists')

    user = User(email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    await db.flush()

    sub = Subscription(
        user_id=user.id,
        status=SubscriptionStatus.TRIAL,
        tariff='free',
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=settings.default_trial_days),
    )
    db.add(sub)
    await db.commit()
    return create_access_token(str(user.id))


async def login_user(data: LoginRequest, db: AsyncSession) -> str:
    user = await db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid login or password')
    return create_access_token(str(user.id))
