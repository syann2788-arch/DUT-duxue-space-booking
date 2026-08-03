import asyncio
from datetime import date, timedelta

from conftest import auth_header
from app.database import async_session
from app.models import Reservation, ReservationStatus


async def force_finished(reservation_id: int):
    async with async_session() as db:
        reservation = await db.get(Reservation, reservation_id)
        reservation.date = date.today() - timedelta(days=1)
        reservation.status = ReservationStatus.cleanup_pending
        await db.commit()


def register(client, suffix: int) -> str:
    response = client.post("/api/auth/register", json={
        "student_id": f"202600{suffix:02d}",
        "name": f"测试学生{suffix}",
        "phone": f"139000000{suffix:02d}",
        "class_name": "2601",
        "password": "Test1234",
    })
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_and_config(client):
    assert client.get("/api/health").json()["version"] == "2.0.0"
    config = client.get("/api/reservations/config").json()
    assert config["slot_minutes"] == 30
    assert config["max_minutes_per_day"] == 240


def test_allocation_review_limit_priority_and_export(client):
    day = (date.today() + timedelta(days=1)).isoformat()
    student1 = register(client, 1)
    student2 = register(client, 2)
    student3 = register(client, 3)

    booking = {"scene": "study", "date": day, "start_slot": 2, "end_slot": 4, "people_count": 2, "purpose": "课程复习"}
    first = client.post("/api/reservations", json=booking, headers=auth_header(student1))
    assert first.status_code == 201, first.text
    assert first.json()["room"]["room_code"] == "A102"
    assert first.json()["start_minute"] == 9 * 60
    assert first.json()["status"] == "pending"

    # Shared study capacity permits another group in A102.
    second = client.post("/api/reservations", json=booking, headers=auth_header(student2))
    assert second.status_code == 201, second.text
    assert second.json()["room"]["room_code"] == "A102"

    # Existing 1h + another 3.5h exceeds the configurable 4-hour daily sum.
    over_limit = client.post("/api/reservations", json={**booking, "start_slot": 8, "end_slot": 15}, headers=auth_header(student1))
    assert over_limit.status_code == 400

    admin_login = client.post("/api/auth/login", json={"student_id": "admin001", "password": "admin123"})
    assert admin_login.status_code == 200, admin_login.text
    admin = auth_header(admin_login.json()["access_token"])
    reviewed = client.post("/api/admin/reservations/review", headers=admin, json={
        "reservation_ids": [first.json()["id"], second.json()["id"]], "decision": "approved", "note": "测试通过",
    })
    assert reviewed.json()["processed"] == 2

    music = client.post("/api/reservations", headers=auth_header(student2), json={
        "scene": "music", "date": day, "start_slot": 18, "end_slot": 20, "people_count": 1, "purpose": "钢琴练习",
    })
    assert music.status_code == 201, music.text
    event = client.post("/api/reservations", headers=auth_header(student3), json={
        "scene": "event", "date": day, "start_slot": 18, "end_slot": 20, "people_count": 40, "purpose": "书院讲座",
    })
    assert event.status_code == 201, event.text
    my_music = client.get("/api/reservations/my", headers=auth_header(student2)).json()
    displaced = next(item for item in my_music if item["id"] == music.json()["id"])
    assert displaced["status"] == "rejected"

    export = client.get("/api/admin/export.xlsx", headers=admin)
    assert export.status_code == 200
    assert export.content[:2] == b"PK"

    # Closed-loop cleanup: upload -> admin reject + timed restriction -> booking blocked.
    asyncio.run(force_finished(first.json()["id"]))
    photo = client.post(
        "/api/reservations/photos", headers=auth_header(student1),
        files={"file": ("cleanup.jpg", b"\xff\xd8\xff\xe0test-jpeg-data", "image/jpeg")},
    )
    assert photo.status_code == 201, photo.text
    submitted = client.post(
        f"/api/reservations/{first.json()['id']}/cleanup",
        headers=auth_header(student1), json={"photo_urls": [photo.json()["url"]]},
    )
    assert submitted.status_code == 200, submitted.text
    queue = client.get("/api/admin/cleanup", headers=admin).json()
    cleanup_id = next(item["cleanup"]["id"] for item in queue if item["id"] == first.json()["id"])
    rejected = client.post(f"/api/admin/cleanup/{cleanup_id}/review", headers=admin, json={
        "decision": "rejected", "note": "照片无法确认清扫完成", "restrict_user": True,
        "restriction_level": "timed", "restriction_days": 7,
    })
    assert rejected.status_code == 200, rejected.text
    blocked = client.post("/api/reservations", json={**booking, "date": (date.today() + timedelta(days=2)).isoformat()}, headers=auth_header(student1))
    assert blocked.status_code == 403
