from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')
settings = get_settings()


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid credentials',
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get('sub'))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        raise credentials_exception
    return user
