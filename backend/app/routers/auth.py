import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UserProfileOut, UserRegister, UserLogin, Token, UserOut, WechatBindRequest, WechatLoginRequest
from app.services import create_user, get_active_restriction, get_user_by_id, get_user_by_student_id
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _token_response(user: User) -> dict:
    token = create_access_token({
        "sub": str(user.id),
        "student_id": user.student_id,
        "role": user.role.value,
    })
    return {"access_token": token, "user": user}


async def _code2session(code: str) -> str:
    """Exchange a one-time wx.login code without exposing the AppSecret."""
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise HTTPException(status_code=503, detail="服务器尚未配置微信AppID/AppSecret")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.weixin.qq.com/sns/jscode2session", params={
                "appid": settings.WECHAT_APP_ID,
                "secret": settings.WECHAT_APP_SECRET,
                "js_code": code,
                "grant_type": "authorization_code",
            })
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="微信登录服务暂时不可用") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="微信登录服务返回异常") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="微信登录服务返回异常")
    openid = payload.get("openid")
    if not openid:
        raise HTTPException(
            status_code=400,
            detail=f"微信登录凭证校验失败：{payload.get('errmsg', 'unknown')}",
        )
    return openid


@router.post("/register", response_model=Token)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_student_id(db, data.student_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学号已注册")

    user = await create_user(
        db, data.student_id, data.name, data.phone,
        data.class_name, hash_password(data.password)
    )
    return _token_response(user)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_student_id(db, data.student_id)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="学号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    return _token_response(user)


@router.get("/me", response_model=UserProfileOut)
async def me(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    u = await get_user_by_id(db, int(user["sub"]))
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    restriction = await get_active_restriction(db, u)
    profile = UserOut.model_validate(u).model_dump()
    profile.update({
        "booking_restricted": restriction is not None,
        "restriction_level": restriction.level if restriction else None,
        "restriction_reason": restriction.reason if restriction else None,
        "restriction_ends_at": restriction.ends_at if restriction else None,
    })
    return profile


@router.post("/wechat/login", response_model=Token)
async def login_wechat(data: WechatLoginRequest, db: AsyncSession = Depends(get_db)):
    openid = await _code2session(data.code)
    user = (await db.execute(select(User).where(User.wechat_openid == openid))).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该微信尚未绑定账号，请先使用学号密码登录",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return _token_response(user)


@router.post("/wechat/bind")
async def bind_wechat(
    data: WechatBindRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange wx.login code on the server; AppSecret never reaches the client."""
    openid = await _code2session(data.code)
    target = await get_user_by_id(db, int(user["sub"]))
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    bound_user = (await db.execute(select(User).where(User.wechat_openid == openid))).scalar_one_or_none()
    if bound_user and bound_user.id != target.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该微信已绑定其他账号")
    target.wechat_openid = openid
    await db.commit()
    return {"message": "微信账号绑定成功"}
