from fastapi import APIRouter

from app.notifications import public_template_ids

router = APIRouter(prefix="/api/notifications", tags=["消息通知"])


@router.get("/templates")
async def templates():
    return {"template_ids": public_template_ids()}
