import asyncio
import io
from datetime import date, timedelta

from openpyxl import load_workbook
from conftest import auth_header
from app.database import async_session
from app.models import Reservation, ReservationStatus


async def force_finished(reservation_id: int):
    async with async_session() as db:
        reservation = await db.get(Reservation, reservation_id)
        reservation.date = date.today() - timedelta(days=1)
        reservation.status = ReservationStatus.cleanup_pending
        await db.commit()


async def force_missed(reservation_ids: list[int]):
    async with async_session() as db:
        for reservation_id in reservation_ids:
            reservation = await db.get(Reservation, reservation_id)
            reservation.date = date.today() - timedelta(days=1)
            reservation.start_minute = 8 * 60
            reservation.end_minute = 8 * 60 + 30
            reservation.status = ReservationStatus.approved
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
    student4 = register(client, 4)

    booking = {"scene": "study", "date": day, "start_slot": 2, "end_slot": 4, "people_count": 1, "purpose": "个人自习", "campus_card_photo_url": "/uploads/campus_card_test.jpg"}
    first = client.post("/api/reservations", json=booking, headers=auth_header(student1))
    assert first.status_code == 201, first.text
    assert first.json()["room"]["room_code"] == "A102"
    assert first.json()["start_minute"] == 9 * 60
    assert first.json()["status"] == "pending"

    # Shared study capacity permits another one-person reservation in A102.
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
        "scene": "music", "date": day, "start_slot": 18, "end_slot": 20, "people_count": 1,
        "purpose": "进行个人钢琴练习训练", "campus_card_photo_url": "/uploads/campus_card_test.jpg",
    })
    assert music.status_code == 201, music.text
    assert music.json()["room"]["room_code"] == "B102"
    piano = client.post("/api/reservations", headers=auth_header(student3), json={
        "scene": "music", "date": day, "start_slot": 18, "end_slot": 20, "people_count": 1,
        "purpose": "进行声乐与钢琴联合训练", "campus_card_photo_url": "/uploads/campus_card_test.jpg",
    })
    assert piano.status_code == 201, piano.text
    assert piano.json()["room"]["room_code"] == "A103"
    event = client.post("/api/reservations", headers=auth_header(student4), json={
        "scene": "event", "date": day, "start_slot": 18, "end_slot": 20, "people_count": 40,
        "purpose": "举办书院大型主题宣讲活动", "campus_card_photo_url": "/uploads/campus_card_test.jpg",
    })
    assert event.status_code == 409

    export = client.get("/api/admin/export.xlsx", headers=admin)
    assert export.status_code == 200
    assert export.content[:2] == b"PK"
    workbook = load_workbook(io.BytesIO(export.content), read_only=True)
    assert workbook.sheetnames == ["预约记录", "预约限制记录"]
    headers = [cell.value for cell in next(workbook["预约记录"].iter_rows())]
    assert "玉兰卡照片" in headers
    assert "违规标记" in headers

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
    # Requirement: submitting the cleanup photo immediately unlocks booking;
    # the administrator reviews it asynchronously afterwards.
    unlocked = client.post("/api/reservations", json={**booking, "date": (date.today() + timedelta(days=2)).isoformat()}, headers=auth_header(student1))
    assert unlocked.status_code == 201, unlocked.text
    queue = client.get("/api/admin/cleanup", headers=admin).json()
    cleanup_id = next(item["cleanup"]["id"] for item in queue if item["id"] == first.json()["id"])
    rejected = client.post(f"/api/admin/cleanup/{cleanup_id}/review", headers=admin, json={
        "decision": "rejected", "note": "照片无法确认清扫完成", "restrict_user": True,
        "restriction_level": "timed", "restriction_days": 7,
    })
    assert rejected.status_code == 200, rejected.text
    blocked = client.post("/api/reservations", json={**booking, "date": (date.today() + timedelta(days=2)).isoformat()}, headers=auth_header(student1))
    assert blocked.status_code == 403


def test_three_violations_trigger_thirty_day_ban(client):
    token = register(client, 11)
    admin_login = client.post("/api/auth/login", json={"student_id": "admin001", "password": "admin123"})
    admin = auth_header(admin_login.json()["access_token"])
    reservation_ids = []
    for index in range(3):
        payload = {
            "scene": "study",
            "date": (date.today() + timedelta(days=index + 1)).isoformat(),
            "start_slot": 4,
            "end_slot": 5,
            "people_count": 1,
            "purpose": "个人自习",
            "campus_card_photo_url": "/uploads/campus_card_test.jpg",
        }
        created = client.post("/api/reservations", json=payload, headers=auth_header(token))
        assert created.status_code == 201, created.text
        reservation_ids.append(created.json()["id"])
    reviewed = client.post("/api/admin/reservations/review", headers=admin, json={
        "reservation_ids": reservation_ids, "decision": "approved", "note": "测试通过",
    })
    assert reviewed.status_code == 200
    asyncio.run(force_missed(reservation_ids))
    client.get("/api/reservations/my", headers=auth_header(token))

    # Use the admin API instead of relying on database-assigned user ids.
    users = client.get("/api/admin/users?search=20260011", headers=admin).json()
    user_id = users[0]["id"]
    violations = client.get(f"/api/admin/users/{user_id}/violations", headers=admin).json()
    restrictions = client.get(f"/api/admin/users/{user_id}/restrictions", headers=admin).json()
    assert len(violations) == 3
    automatic = next(item for item in restrictions if "自动禁约30天" in item["reason"])
    assert automatic["level"] == "timed"

    blocked = client.post("/api/reservations", json={
        "scene": "study", "date": (date.today() + timedelta(days=4)).isoformat(), "start_slot": 6, "end_slot": 7,
        "people_count": 1, "purpose": "个人自习", "campus_card_photo_url": "/uploads/campus_card_test.jpg",
    }, headers=auth_header(token))
    assert blocked.status_code == 403
    assert "自动禁约30天" in blocked.text
