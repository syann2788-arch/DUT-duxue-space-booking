from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Reservation, Room
from app.schemas import RoomOut
from app.services import OCCUPYING_STATUSES, get_active_rooms, get_room_by_id, get_runtime_config, slot_label

router = APIRouter(prefix="/api/rooms", tags=["房间"])


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
