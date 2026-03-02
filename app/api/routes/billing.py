from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.billing.service import activate_subscription, grant_tokens
from app.billing.yookassa_service import PRICES, create_payment, get_payment
from app.core.config import get_settings
from app.core.database import get_db
from app.core.models import BillingPeriod, Payment, Subscription, TokenUsageLog, TokenWallet, User


router = APIRouter(prefix='/billing', tags=['billing'])
settings = get_settings()


@router.get('/wallets')
async def wallets(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await db.scalars(select(TokenWallet).where(TokenWallet.user_id == user.id))
    return list(items)


@router.get('/usage')
async def usage(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logs = await db.scalars(select(TokenUsageLog).where(TokenUsageLog.user_id == user.id).order_by(TokenUsageLog.id.desc()).limit(100))
    return list(logs)


@router.post('/subscribe/{period}')
async def subscribe(period: BillingPeriod, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pay = create_payment(user.id, period, f'{settings.base_url}/webapp/index.html')
    record = Payment(user_id=user.id, provider_payment_id=pay.id, amount_rub=PRICES[period], period=period, status='pending')
    db.add(record)
    await db.commit()
    return {'confirmation_url': pay.confirmation.confirmation_url}


@router.post('/webhook/yookassa')
async def yookassa_webhook(payload: dict, db: AsyncSession = Depends(get_db)):
    event = payload.get('event')
    obj = payload.get('object', {})
    if event != 'payment.succeeded':
        return {'ok': True}
    payment_id = obj.get('id')
    payment = await db.scalar(select(Payment).where(Payment.provider_payment_id == payment_id))
    if not payment:
        raise HTTPException(status_code=404, detail='Payment not found')
    payment.status = 'succeeded'
    await activate_subscription(db, payment, payment.period)
    await grant_tokens(db, payment.user_id, 'openai:gpt-4o-mini', 500000)
    await db.commit()
    return {'ok': True}


@router.get('/subscription')
async def subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sub = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    return {'status': sub.status, 'tariff': sub.tariff, 'period_end': sub.current_period_end, 'now': datetime.now(timezone.utc)}
