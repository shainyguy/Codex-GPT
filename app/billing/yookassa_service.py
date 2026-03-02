import uuid

from yookassa import Configuration, Payment as YooPayment

from app.core.config import get_settings
from app.core.models import BillingPeriod


settings = get_settings()
if settings.yookassa_shop_id and settings.yookassa_secret_key:
    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key


PRICES = {BillingPeriod.WEEK: 299, BillingPeriod.MONTH: 990}


def create_payment(user_id: int, period: BillingPeriod, return_url: str) -> dict:
    amount = PRICES[period]
    payment = YooPayment.create(
        {
            'amount': {'value': f'{amount:.2f}', 'currency': 'RUB'},
            'capture': True,
            'confirmation': {'type': 'redirect', 'return_url': return_url},
            'description': f'Subscription {period.value}',
            'metadata': {'user_id': user_id, 'period': period.value},
        },
        str(uuid.uuid4()),
    )
    return payment


def get_payment(payment_id: str):
    return YooPayment.find_one(payment_id)
