from fastapi import APIRouter

from app.notifications import public_template_ids

router = APIRouter(prefix="/api/notifications", tags=["消息通知"])


@router.get("/templates")
async def templates():
    return {"template_ids": public_template_ids()}


from fastapi import Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import get_current_user
from app.database import get_db
from app.models import Notification, local_now


@router.get("/my")
async def my_notifications(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                           db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    predicate = (Notification.user_id == int(token["sub"])) & (Notification.scheduled_at <= local_now())
    total = int(await db.scalar(select(func.count()).select_from(Notification).where(predicate)) or 0)
    items = (await db.scalars(select(Notification).where(predicate).order_by(Notification.id.desc()).limit(limit).offset(offset))).all()
    return {"items": [{"id": n.id, "type": n.type, "payload": n.payload, "status": n.status,
                       "scheduled_at": n.scheduled_at, "sent_at": n.sent_at} for n in items],
            "total": total, "limit": limit, "offset": offset, "has_more": offset + len(items) < total}
