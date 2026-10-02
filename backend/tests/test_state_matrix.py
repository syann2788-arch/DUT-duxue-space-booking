import asyncio
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.database import async_session
from app.domain.reservations import cancel_reservation, checkin_reservation, refresh_reservation_states
from app.models import (
    Notification, NotificationStatus, NotificationType, Reservation,
    ReservationStatus, Room, SceneType, UsageMode, User, Violation,
    ViolationType, local_now,
)
from app.notifications import TEMPLATE_IDS, _token_cache, deliver_due_notifications
from conftest import auth_header


def register(client, suffix: int) -> tuple[str, dict]:
    response = client.post("/api/auth/register", json={
        "student_id": f"202602{suffix:02d}",
        "name": f"状态机测试{suffix}",
        "phone": f"137000002{suffix:02d}",
        "class_name": "2602",
        "password": "Test1234",
    })
    assert response.status_code == 200, response.text
    return response.json()["access_token"], response.json()["user"]


def upload_card(client, token: str) -> str:
    response = client.post(
        "/api/reservations/campus-card-photo",
        headers=auth_header(token),
        files={"file": ("card.jpg", b"\xff\xd8\xff\xe0state-test", "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()["media_id"]


def test_admin_authorization_matrix_and_cross_user_ownership(client):
    owner_token, _ = register(client, 81)
    outsider_token, _ = register(client, 82)
    student = auth_header(owner_token)
    admin_operations = [
        ("get", "/api/admin/stats", None),
        ("get", "/api/admin/reservations", None),
        ("get", "/api/admin/cleanup", None),
        ("get", "/api/admin/users", None),
        ("get", "/api/admin/settings", None),
        ("get", "/api/admin/counselors", None),
        ("post", "/api/admin/reservations/review", {"reservation_ids": [1], "decision": "approved"}),
        ("put", "/api/admin/settings", {"values": {"advance_days": 7}}),
    ]
    for method, path, body in admin_operations:
        response = client.request(method, path, headers=student, json=body)
        assert response.status_code == 403, (method, path, response.text)

    day = (local_now().date() + timedelta(days=1)).isoformat()
    created = client.post("/api/reservations", headers=student, json={
        "scene": "study", "date": day, "start_slot": 20, "end_slot": 21,
        "people_count": 1, "purpose": "个人自习",
        "campus_card_media_id": upload_card(client, owner_token),
    })
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]
    outsider = auth_header(outsider_token)
    assert client.post(f"/api/reservations/{reservation_id}/cancel", headers=outsider).status_code == 404
    assert client.post("/api/reservations/checkin", headers=outsider, json={"reservation_id": reservation_id}).status_code == 404
    assert client.post(f"/api/reservations/{reservation_id}/cleanup", headers=outsider, json={
        "media_ids": ["00000000-0000-0000-0000-000000000000"]
    }).status_code == 404


async def set_user_active(user_id: int, active: bool) -> None:
    async with async_session() as db:
        user = await db.get(User, user_id)
        user.is_active = active
        await db.commit()


def test_disabled_account_invalidates_existing_and_new_sessions(client):
    token, user = register(client, 83)
    asyncio.run(set_user_active(user["id"], False))
    try:
        assert client.get("/api/auth/me", headers=auth_header(token)).status_code == 403
        assert client.get("/api/reservations/my", headers=auth_header(token)).status_code == 403
        login = client.post("/api/auth/login", json={"student_id": user["student_id"], "password": "Test1234"})
        assert login.status_code == 403
    finally:
        asyncio.run(set_user_active(user["id"], True))


async def create_boundary_reservation(user_id: int, status: ReservationStatus, start: datetime) -> int:
    async with async_session() as db:
        room = (await db.execute(select(Room).where(Room.room_code == "A101"))).scalar_one()
        reservation = Reservation(
            user_id=user_id, room_id=room.id, date=start.date(),
            start_slot=4, end_slot=5, start_minute=start.hour * 60 + start.minute,
            end_minute=start.hour * 60 + start.minute + 30,
            start_hour=start.hour, end_hour=start.hour + 1,
            scene=SceneType.meeting, usage_mode=UsageMode.exclusive,
            people_count=2, purpose="状态机时间边界测试预约", status=status,
        )
        db.add(reservation)
        await db.commit()
        return reservation.id


async def exercise_time_boundaries(user_id: int):
    start = datetime.combine(local_now().date() + timedelta(days=2), datetime.min.time()).replace(hour=10)
    cancellable = await create_boundary_reservation(user_id, ReservationStatus.pending, start)
    at_deadline = await create_boundary_reservation(user_id, ReservationStatus.pending, start)
    checkin_open = await create_boundary_reservation(user_id, ReservationStatus.approved, start)
    checkin_late = await create_boundary_reservation(user_id, ReservationStatus.approved, start)
    async with async_session() as db:
        cancelled = await cancel_reservation(db, cancellable, user_id, start - timedelta(minutes=30, microseconds=1))
    async with async_session() as db:
        with pytest.raises(ValueError, match="取消截止"):
            await cancel_reservation(db, at_deadline, user_id, start - timedelta(minutes=30))
    async with async_session() as db:
        checked_in = await checkin_reservation(db, checkin_open, user_id, start - timedelta(minutes=15))
    async with async_session() as db:
        with pytest.raises(ValueError, match="签到宽限期"):
            await checkin_reservation(db, checkin_late, user_id, start + timedelta(minutes=15, microseconds=1))
    return cancelled.status, checked_in.status


def test_cancellation_and_checkin_time_boundaries(client):
    _, user = register(client, 84)
    cancelled, checked_in = asyncio.run(exercise_time_boundaries(user["id"]))
    assert cancelled == ReservationStatus.cancelled
    assert checked_in == ReservationStatus.in_use


async def exercise_idempotent_state_refresh(user_id: int):
    start = datetime.combine(local_now().date() - timedelta(days=1), datetime.min.time()).replace(hour=10)
    reservation_id = await create_boundary_reservation(user_id, ReservationStatus.approved, start)
    async with async_session() as db:
        now = start + timedelta(hours=1)
        await refresh_reservation_states(db, now)
        await refresh_reservation_states(db, now)
    async with async_session() as db:
        reservation = await db.get(Reservation, reservation_id)
        violations = int(await db.scalar(select(func.count(Violation.id)).where(
            Violation.reservation_id == reservation_id,
            Violation.type == ViolationType.no_show,
        )) or 0)
        return reservation.status, violations


def test_state_refresh_is_idempotent(client):
    _, user = register(client, 85)
    status, violations = asyncio.run(exercise_idempotent_state_refresh(user["id"]))
    assert status == ReservationStatus.missed
    assert violations == 1


async def create_bound_notification(user_id: int) -> int:
    async with async_session() as db:
        user = await db.get(User, user_id)
        user.wechat_openid = f"openid-{user_id}"
        notification = Notification(
            user_id=user_id, type=NotificationType.submitted,
            payload={"room": "A101", "date": "2026-08-14"},
            scheduled_at=local_now() - timedelta(seconds=1),
        )
        db.add(notification)
        await db.commit()
        return notification.id


async def deliver_and_read(notification_id: int):
    async with async_session() as db:
        await deliver_due_notifications(db)
    async with async_session() as db:
        return await db.get(Notification, notification_id)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.weixin.qq.com")
            raise httpx.HTTPStatusError("provider unavailable", request=request, response=httpx.Response(self.status_code, request=request))


class FakeWechatClient:
    token_response = FakeResponse({"access_token": "test-token", "expires_in": 7200})
    send_response = FakeResponse({"errcode": 0})

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return self.token_response

    async def post(self, *args, **kwargs):
        return self.send_response


def test_wechat_provider_failures_are_retried_without_losing_outbox_rows(client, monkeypatch):
    from app import notifications
    from app.config import settings

    _, user = register(client, 86)
    notification_id = asyncio.run(create_bound_notification(user["id"]))
    monkeypatch.setattr(settings, "WECHAT_APP_ID", "test-app")
    monkeypatch.setattr(settings, "WECHAT_APP_SECRET", "test-secret")
    monkeypatch.setitem(TEMPLATE_IDS, NotificationType.submitted, "template-id")
    monkeypatch.setattr(notifications.httpx, "AsyncClient", FakeWechatClient)

    _token_cache.update({"value": "", "expires_at": None})
    FakeWechatClient.token_response = FakeResponse({}, 503)
    failed = asyncio.run(deliver_and_read(notification_id))
    assert failed.status == NotificationStatus.pending
    assert failed.attempts == 1
    assert failed.scheduled_at > local_now()
    assert "provider unavailable" in failed.error

    async def make_due():
        async with async_session() as db:
            row = await db.get(Notification, notification_id)
            row.scheduled_at = local_now() - timedelta(seconds=1)
            await db.commit()

    asyncio.run(make_due())
    _token_cache.update({"value": "", "expires_at": None})
    FakeWechatClient.token_response = FakeResponse({"access_token": "test-token", "expires_in": 7200})
    FakeWechatClient.send_response = FakeResponse({"errcode": 40037, "errmsg": "invalid template"})
    business_error = asyncio.run(deliver_and_read(notification_id))
    assert business_error.status == NotificationStatus.pending
    assert business_error.attempts == 2
    assert business_error.error == "invalid template"

    asyncio.run(make_due())
    FakeWechatClient.send_response = FakeResponse({"errcode": 0})
    delivered = asyncio.run(deliver_and_read(notification_id))
    assert delivered.status == NotificationStatus.sent
    assert delivered.attempts == 3
    assert delivered.error is None
