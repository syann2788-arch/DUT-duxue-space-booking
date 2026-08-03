from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import UserRole
from app.schemas import UserRegister, UserLogin, Token, UserOut, WechatBindRequest
from app.services import get_user_by_student_id, get_user_by_id, create_user
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=Token)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_student_id(db, data.student_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学号已注册")

    user = await create_user(
        db, data.student_id, data.name, data.phone,
        data.class_name, hash_password(data.password)
    )
    token = create_access_token({
        "sub": str(user.id),
        "student_id": user.student_id,
        "role": user.role.value,
    })
    return {"access_token": token, "user": user}


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_student_id(db, data.student_id)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="学号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token({
        "sub": str(user.id),
        "student_id": user.student_id,
        "role": user.role.value,
    })
    return {"access_token": token, "user": user}


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    u = await get_user_by_id(db, int(user["sub"]))
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return u


@router.post("/wechat/bind")
async def bind_wechat(
    data: WechatBindRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange wx.login code on the server; AppSecret never reaches the client."""
    from app.config import settings
    import httpx

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise HTTPException(status_code=503, detail="服务器尚未配置微信AppID/AppSecret")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.weixin.qq.com/sns/jscode2session", params={
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "js_code": data.code,
            "grant_type": "authorization_code",
        })
        payload = response.json()
    if "openid" not in payload:
        raise HTTPException(status_code=400, detail=f"微信登录凭证校验失败：{payload.get('errmsg', 'unknown')}")
    target = await get_user_by_id(db, int(user["sub"]))
    target.wechat_openid = payload["openid"]
    await db.commit()
    return {"message": "微信账号绑定成功"}
