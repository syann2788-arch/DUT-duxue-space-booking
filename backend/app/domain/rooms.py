"""Room catalogue and public status use cases."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import PublicStatus, Room


async def get_active_rooms(db: AsyncSession) -> list[Room]:
    result = await db.execute(
        select(Room).options(selectinload(Room.scene_rules)).where(Room.is_active.is_(True)).order_by(Room.room_code)
    )
    return list(result.scalars().unique())


async def get_room_by_id(db: AsyncSession, room_id: int) -> Room | None:
    result = await db.execute(select(Room).options(selectinload(Room.scene_rules)).where(Room.id == room_id))
    return result.scalar_one_or_none()


async def update_public_status(db: AsyncSession, room_id: int, public_status: PublicStatus) -> Room | None:
    room = await db.get(Room, room_id)
    if not room or not room.is_public:
        return None
    room.public_status = public_status
    await db.commit()
    await db.refresh(room)
    return room
