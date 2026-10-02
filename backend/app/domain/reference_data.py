"""Insert missing reference records without overwriting school configuration."""
from sqlalchemy import select, text
from app.models import Room, RoomSceneRule
from app.reference_data import ROOMS, RULES
from app.domain.audit import record_admin_action


async def initialize_reference_data(db):
    # Serialize concurrent CLI runs on PostgreSQL until the caller commits.
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4455585246})
    rooms = {room.room_code: room for room in (await db.scalars(select(Room))).all()}
    created_rooms = 0
    for row in ROOMS:
        if row[0] in rooms:
            continue
        room = Room(room_code=row[0], name=row[1], description=row[2], category=row[3],
                    capacity=row[4], can_reserve=row[5], is_public=row[6], who_can_reserve=row[7],
                    has_fridge=row[8], has_instruments=row[9], floor_plan_x=row[10],
                    floor_plan_y=row[11], is_active=True)
        db.add(room)
        rooms[row[0]] = room
        created_rooms += 1
    await db.flush()
    existing = {(rule.room_id, rule.scene) for rule in (await db.scalars(select(RoomSceneRule))).all()}
    created_rules = 0
    for code, scene, priority, capacity, mode in RULES:
        key = (rooms[code].id, scene)
        if key in existing:
            continue
        db.add(RoomSceneRule(room_id=key[0], scene=scene, priority=priority,
                             capacity=capacity, usage_mode=mode, is_enabled=True))
        existing.add(key)
        created_rules += 1
    result = {"created_rooms": created_rooms, "created_rules": created_rules}
    if created_rooms or created_rules:
        record_admin_action(db, None, "reference_data.initialize", "reference_data", "defaults", result)
    await db.flush()
    return result
