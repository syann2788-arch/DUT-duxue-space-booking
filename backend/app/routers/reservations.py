from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import ReservationStatus
from app.schemas import CheckinRequest, CleanupSubmit, ReservationCreate, ReservationOut
from app.services import (
    cancel_reservation,
    checkin_reservation,
    create_reservation,
    get_runtime_config,
    get_user_reservations,
    submit_cleanup,
)

router = APIRouter(prefix="/api/reservations", tags=["预约"])


@router.get("/config")
async def public_booking_config(db: AsyncSession = Depends(get_db)):
    """Public values required to render slots; secrets are never stored here."""
    return await get_runtime_config(db)


@router.post("", response_model=ReservationOut, status_code=201)
async def reserve(data: ReservationCreate, db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    return await create_reservation(db, int(token["sub"]), data)


@router.get("/my", response_model=list[ReservationOut])
async def my_reservations(
    status_filter: ReservationStatus | None = None,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    return await get_user_reservations(db, int(token["sub"]), status_filter)


@router.post("/{reservation_id}/cancel")
async def cancel(reservation_id: int, db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    try:
        reservation = await cancel_reservation(db, reservation_id, int(token["sub"]))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not reservation:
        raise HTTPException(404, "预约不存在或当前状态不可取消")
    return {"message": "取消成功"}


@router.post("/checkin")
async def checkin(data: CheckinRequest, db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    try:
        reservation = await checkin_reservation(db, data.reservation_id, int(token["sub"]))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not reservation:
        raise HTTPException(404, "预约不存在、未审核通过或状态错误")
    return {"message": "签到成功"}


@router.post("/photos", status_code=201)
async def upload_cleanup_photo(file: UploadFile = File(...), token: dict = Depends(get_current_user)):
    return await _store_photo(file, token, "cleanup")


@router.post("/campus-card-photo", status_code=201)
async def upload_campus_card_photo(file: UploadFile = File(...), token: dict = Depends(get_current_user)):
    return await _store_photo(file, token, "campus_card")


async def _store_photo(file: UploadFile, token: dict, prefix: str) -> dict:
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "仅支持 JPG、PNG、WebP 图片")
    content = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"单张照片不能超过{settings.MAX_UPLOAD_MB}MB")
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    signatures_ok = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
    }
    if not signatures_ok[file.content_type]:
        raise HTTPException(400, "文件内容与图片格式不匹配")
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{token['sub']}_{uuid4().hex}{suffix}"
    (upload_dir / filename).write_bytes(content)
    return {"url": f"/uploads/{filename}"}


@router.post("/{reservation_id}/cleanup", response_model=ReservationOut)
async def cleanup(
    reservation_id: int,
    data: CleanupSubmit,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    return await submit_cleanup(db, reservation_id, int(token["sub"]), data.photo_urls)
