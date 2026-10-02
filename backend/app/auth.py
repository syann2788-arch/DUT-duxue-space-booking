from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.database import get_db
from app.models import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate both the JWT and the account's current server-side state."""
    payload = decode_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(401, "无效的认证令牌")
    current = await db.get(User, user_id)
    if not current or not current.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号不存在或已停用")
    if payload.get("version", 0) != current.session_version:
        raise HTTPException(401, "密码已更新，请重新登录")
    if current.must_change_password and request.url.path not in {"/api/auth/me", "/api/auth/password/change"}:
        raise HTTPException(403, "请先修改初始密码")
    return payload


async def require_admin(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    current = await db.get(User, int(user["sub"]))
    if not current or not current.is_active or current.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


async def require_counselor_or_admin(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    current = await db.get(User, int(user["sub"]))
    if not current or not current.is_active or current.role not in (UserRole.counselor, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要辅导员或管理员权限")
    return user
