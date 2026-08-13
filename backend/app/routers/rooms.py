from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Reservation, ReservationStatus, Room, SpaceMessage, User
from app.schemas import RoomOut, SpaceMessageCreate, SpaceMessageOut
from app.domain.common import OCCUPYING_STATUSES, slot_label
from app.domain.rooms import get_active_rooms, get_room_by_id
from app.domain.settings import get_runtime_config
from app.uploads import store_image

router = APIRouter(prefix="/api/rooms", tags=["房间"])

MESSAGE_ELIGIBLE_STATUSES = (
    ReservationStatus.in_use,
    ReservationStatus.cleanup_pending,
    ReservationStatus.cleanup_rejected,
    ReservationStatus.completed,
    ReservationStatus.checked_in,
)


async def _require_room(db: AsyncSession, room_id: int) -> Room:
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    return room


async def _require_room_usage(db: AsyncSession, room_id: int, user_id: int) -> None:
    reservation_id = await db.scalar(select(Reservation.id).where(
        Reservation.room_id == room_id,
        Reservation.user_id == user_id,
        Reservation.status.in_(MESSAGE_ELIGIBLE_STATUSES),
    ).limit(1))
    if reservation_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "只有实际使用过该空间的用户才能留言")


def _message_out(message: SpaceMessage, author_name: str) -> dict:
    return {
        "id": message.id,
        "room_id": message.room_id,
        "content": message.content,
        "photo_urls": message.photo_urls or [],
        "author_name": author_name,
        "created_at": message.created_at,
    }


@router.get("", response_model=list[RoomOut])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    return await get_active_rooms(db)


@router.get("/{room_id}", response_model=RoomOut)
async def room_detail(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    return room


@router.get("/{room_id}/slots")
async def room_slots(room_id: int, date_value: date = Query(alias="date"), db: AsyncSession = Depends(get_db)):
    if not await db.get(Room, room_id):
        raise HTTPException(404, "房间不存在")
    config = await get_runtime_config(db)
    result = await db.execute(select(Reservation).where(
        Reservation.room_id == room_id,
        Reservation.date == date_value,
        Reservation.status.in_(OCCUPYING_STATUSES),
    ))
    reservations = list(result.scalars())
    total = (config["close_hour"] - config["open_hour"]) * 60 // config["slot_minutes"]
    slots = []
    for index in range(total):
        slot_start = config["open_hour"] * 60 + index * config["slot_minutes"]
        slot_end = slot_start + config["slot_minutes"]
        overlapping = [r for r in reservations if r.start_minute is not None and r.start_minute < slot_end and r.end_minute > slot_start]
        slots.append({
            "slot": index,
            "label": f"{slot_label(index, config)}-{slot_label(index + 1, config)}",
            "available": not overlapping,
            "reserved_people": sum(r.people_count for r in overlapping),
        })
    return {"date": date_value, "slots": slots}


@router.get("/{room_id}/messages", response_model=list[SpaceMessageOut])
async def list_messages(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    await _require_room(db, room_id)
    result = await db.execute(
        select(SpaceMessage)
        .options(joinedload(SpaceMessage.user))
        .where(SpaceMessage.room_id == room_id)
        .order_by(SpaceMessage.created_at.desc(), SpaceMessage.id.desc())
        .limit(100)
    )
    return [_message_out(message, message.user.name) for message in result.scalars()]


@router.post("/{room_id}/messages", response_model=SpaceMessageOut, status_code=201)
async def post_message(
    room_id: int,
    data: SpaceMessageCreate,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    await _require_room(db, room_id)
    user_id = int(token["sub"])
    await _require_room_usage(db, room_id, user_id)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    message = SpaceMessage(
        room_id=room_id,
        user_id=user_id,
        content=data.content,
        photo_urls=data.photo_urls,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return _message_out(message, user.name)


@router.post("/{room_id}/messages/photo", status_code=201)
async def upload_message_photo(
    room_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(get_current_user),
):
    await _require_room(db, room_id)
    user_id = int(token["sub"])
    await _require_room_usage(db, room_id, user_id)
    return await store_image(file, user_id, "message")
