from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import ReservationStatus, SceneType, User
from app.queries import get_user_reservations
from app.schemas import CheckinRequest, CleanupSubmit, ReservationCreate, ReservationOut, ReservationPageOut
from app.uploads import store_private_image
from app.services import (
    cancel_reservation,
    checkin_reservation,
    create_reservation,
    get_scene_availability,
    get_runtime_config,
    submit_cleanup,
)

router = APIRouter(prefix="/api/reservations", tags=["预约"])


@router.get("/config")
async def public_booking_config(db: AsyncSession = Depends(get_db)):
    """Public values required to render slots; secrets are never stored here."""
    return await get_runtime_config(db)


@router.get("/availability")
async def scene_availability(
    scene: SceneType,
    date_value: date = Query(alias="date"),
    people_count: int = Query(default=1, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    user = await db.get(User, int(token["sub"]))
    if not user or not user.is_active:
        raise HTTPException(403, "账号不存在或已停用")
    return await get_scene_availability(db, scene, date_value, people_count, user.role)


@router.post("", response_model=ReservationOut, status_code=201)
async def reserve(data: ReservationCreate, db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    return await create_reservation(db, int(token["sub"]), data)


@router.get("/my", response_model=ReservationPageOut)
async def my_reservations(
    status_filter: list[ReservationStatus] | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    items, total = await get_user_reservations(
        db, int(token["sub"]), status_filter, limit=limit, offset=offset
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


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
async def upload_cleanup_photo(
    file: UploadFile = File(...),
    token: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await store_private_image(file, int(token["sub"]), "cleanup", db)


@router.post("/campus-card-photo", status_code=201)
async def upload_campus_card_photo(
    file: UploadFile = File(...),
    token: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await store_private_image(file, int(token["sub"]), "campus_card", db)


@router.post("/{reservation_id}/cleanup", response_model=ReservationOut)
async def cleanup(
    reservation_id: int,
    data: CleanupSubmit,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    return await submit_cleanup(db, reservation_id, int(token["sub"]), data.media_ids)
