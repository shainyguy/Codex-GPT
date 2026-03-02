import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.models import TokenWallet


router = APIRouter(tags=['ws'])
settings = get_settings()


@router.websocket('/ws/tokens')
async def token_ws(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload['sub'])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        while True:
            async with AsyncSessionLocal() as db:
                wallets = await db.scalars(select(TokenWallet).where(TokenWallet.user_id == user_id))
                data = [{'model': w.model_name, 'balance': w.balance} for w in wallets]
            await websocket.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
