"""Idempotent demo data and allocation-rule seed."""
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.auth import hash_password
from app.database import async_session, init_db
from app.models import Room, RoomSceneRule, SceneType, UsageMode, User, UserRole


from app.reference_data import ROOMS, RULES


async def seed():
    from app.config import settings
    if settings.is_production:
        raise RuntimeError("演示 seed 仅限 development/test；生产请使用受控管理员建号")
    await init_db()
    async with async_session() as db:
        room_map = {}
        for row in ROOMS:
            room = (await db.execute(select(Room).where(Room.room_code == row[0]))).scalar_one_or_none()
            values = dict(name=row[1], description=row[2], category=row[3], capacity=row[4], can_reserve=row[5], is_public=row[6], who_can_reserve=row[7], has_fridge=row[8], has_instruments=row[9], floor_plan_x=row[10], floor_plan_y=row[11], is_active=True)
            if room:
                for key, value in values.items():
                    setattr(room, key, value)
            else:
                room = Room(room_code=row[0], **values)
                db.add(room)
            room_map[row[0]] = room
        await db.flush()
        for code, scene, priority, capacity, mode in RULES:
            existing = (await db.execute(select(RoomSceneRule).where(RoomSceneRule.room_id == room_map[code].id, RoomSceneRule.scene == scene))).scalar_one_or_none()
            if existing:
                existing.priority, existing.capacity, existing.usage_mode, existing.is_enabled = priority, capacity, mode, True
            else:
                db.add(RoomSceneRule(room_id=room_map[code].id, scene=scene, priority=priority, capacity=capacity, usage_mode=mode))
        admin = (await db.execute(select(User).where(User.student_id == "admin001"))).scalar_one_or_none()
        if not admin:
            db.add(User(student_id="admin001", name="系统管理员", phone="13800000000", class_name="笃学书院", password_hash=hash_password("admin123"), role=UserRole.admin))
        await db.commit()
        print("Seed complete: 12 rooms, 10 allocation rules, admin001/admin123 (change immediately).")


if __name__ == "__main__":
    asyncio.run(seed())
