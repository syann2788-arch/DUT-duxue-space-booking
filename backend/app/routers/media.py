from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import settings
from app.database import get_db
from app.models import MediaAccessLog, PrivateMedia, local_now


router = APIRouter(prefix="/api", tags=["媒体"])
public_router = APIRouter(tags=["公开媒体"])


@public_router.get("/uploads/{filename}")
async def public_message_media(filename: str):
    if not filename.startswith("message_") or Path(filename).name != filename:
        raise HTTPException(404, "文件不存在")
    path = Path(settings.UPLOAD_DIR) / filename
    if not path.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path)


@router.get("/media/{media_id}")
async def private_media(
    media_id: str,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    actor_id = int(admin["sub"])
    media = await db.get(PrivateMedia, media_id)
    if not media or not media.is_active:
        raise HTTPException(404, "媒体不存在")
    if media.expires_at <= local_now():
        raise HTTPException(410, "媒体已超过保留期限")
    path = Path(settings.PRIVATE_UPLOAD_DIR) / media.storage_key
    if Path(media.storage_key).name != media.storage_key or not path.is_file():
        raise HTTPException(404, "媒体文件不存在")
    db.add(MediaAccessLog(media_id=media.id, actor_id=actor_id, action="admin_download"))
    await db.commit()
    return FileResponse(path, media_type=media.content_type, filename=f"{media.purpose.value}{path.suffix}")
