from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import ReservationStatus, SceneType, User
from app.schemas import CleanupSubmit, ReservationCreate, ReservationSelfOut
from app.uploads import store_image
from app.services import (
    cancel_reservation,
    create_reservation,
    get_scene_availability,
    get_runtime_config,
    get_user_reservations,
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


@router.post("", response_model=ReservationSelfOut, status_code=201)
async def reserve(data: ReservationCreate, db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    return await create_reservation(db, int(token["sub"]), data)


@router.get("/my", response_model=list[ReservationSelfOut])
async def my_reservations(
    status_filter: ReservationStatus | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    return await get_user_reservations(db, int(token["sub"]), status_filter, limit, offset)


@router.post("/{reservation_id}/cancel")
async def cancel(reservation_id: int, db: AsyncSession = Depends(get_db), token: dict = Depends(get_current_user)):
    try:
        reservation = await cancel_reservation(db, reservation_id, int(token["sub"]))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not reservation:
        raise HTTPException(404, "预约不存在或当前状态不可取消")
    return {"message": "取消成功"}


@router.post("/photos", status_code=201)
async def upload_cleanup_photo(file: UploadFile = File(...), token: dict = Depends(get_current_user)):
    return await store_image(file, int(token["sub"]), "cleanup")


@router.post("/campus-card-photo", status_code=201)
async def upload_campus_card_photo(file: UploadFile = File(...), token: dict = Depends(get_current_user)):
    return await store_image(file, int(token["sub"]), "campus_card")


@router.post("/{reservation_id}/cleanup", response_model=ReservationSelfOut)
async def cleanup(
    reservation_id: int,
    data: CleanupSubmit,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    return await submit_cleanup(db, reservation_id, int(token["sub"]), data.photo_urls)
