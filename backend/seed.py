"""Idempotent demo data and allocation-rule seed."""
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.auth import hash_password
from app.database import async_session, init_db
from app.models import Room, RoomSceneRule, SceneType, UsageMode, User, UserRole


ROOMS = [
    # code, name, description, category, capacity, reservable, public, permission, fridge, instruments, x, y
    ("A101", "日新阁", "创新与共享自习空间", "综合空间", 12, True, False, "all", False, False, .88, .65),
    ("A102", "格物居", "共享自习空间，也可用于会议", "图书自习", 20, True, True, "all", False, False, .95, .25),
    ("A103", "致知堂", "适合讲座、演出和大型活动", "大型活动", 100, True, False, "all", False, False, .15, .80),
    ("A104", "悠然亭", "公开生活空间，可就餐休息", "生活空间", 20, False, True, "none", True, False, .78, .25),
    ("A105", "聚思轩", "小组讨论与共享自习空间", "会议室", 8, True, False, "all", False, False, .58, .25),
    ("A106", "汇心驿", "师生谈心空间，仅辅导员预约", "谈心室", 6, True, False, "counselor", False, False, .45, .25),
    ("B101", "文治堂", "院长办公室", "办公空间", 4, False, False, "none", False, False, .35, .25),
    ("B102", "韵音阁", "器乐练习空间", "音乐练习", 4, True, False, "all", False, True, .22, .25),
    ("C101", "辅导员宿舍", "非公共空间", "宿舍", 1, False, False, "none", False, False, .12, .80),
    ("C102", "辅导员宿舍", "非公共空间", "宿舍", 1, False, False, "none", False, False, .28, .25),
    ("C103", "辅导员宿舍", "非公共空间", "宿舍", 1, False, False, "none", False, False, .05, .80),
    ("C104", "辅导员宿舍", "非公共空间", "宿舍", 1, False, False, "none", False, False, .42, .25),
]

RULES = [
    ("A102", SceneType.study, 1, 20, UsageMode.shared),
    ("A101", SceneType.study, 2, 12, UsageMode.shared),
    ("A105", SceneType.study, 3, 8, UsageMode.shared),
    ("A105", SceneType.meeting, 1, 8, UsageMode.exclusive),
    ("A101", SceneType.meeting, 2, 12, UsageMode.exclusive),
    ("A102", SceneType.meeting, 3, 20, UsageMode.exclusive),
    ("A103", SceneType.event, 1, 100, UsageMode.exclusive),
    ("B102", SceneType.music, 1, 4, UsageMode.exclusive),
]


async def seed():
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
        print("Seed complete: 12 rooms, 8 allocation rules, admin001/admin123 (change immediately).")


if __name__ == "__main__":
    asyncio.run(seed())
