import asyncio
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.database import SCHEMA_REVISION, async_session, current_schema_revision, init_db
from app.models import Notification, NotificationStatus, NotificationType, SystemSetting, User, local_now
from app.notifications import _access_token, _token_cache, deliver_due_notifications
from app.tasks import leader_lock, minute_tick


def test_readiness_and_error_contract_include_trace_ids(client):
    ready = client.get("/api/ready", headers={"x-request-id": "test-request-123"})
    assert ready.status_code == 200, ready.text
    assert ready.headers["x-request-id"] == "test-request-123"
    assert ready.json()["database"] == "ok"
    assert ready.json()["schema"]["required"] == SCHEMA_REVISION

    invalid = client.post("/api/auth/login", json={"student_id": [], "password": {}})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"
    assert invalid.json()["message"] == "请求参数校验失败"
    assert invalid.json()["request_id"] == invalid.headers["x-request-id"]
    assert isinstance(invalid.json()["details"], list)

    from app.main import unexpected_error
    response = asyncio.run(unexpected_error(None, RuntimeError("sensitive internal detail")))
    assert response.status_code == 500
    assert b"sensitive internal detail" not in response.body
    assert b"INTERNAL_ERROR" in response.body


def test_local_schema_revision_is_optional_but_migration_revision_is_known(client):
    assert asyncio.run(current_schema_revision()) is None
    assert SCHEMA_REVISION == "20260813_02"


def test_production_rejects_unmigrated_schema(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError, match="数据库版本不匹配"):
        asyncio.run(init_db())


async def run_overlapping_ticks(monkeypatch):
    import app.tasks as tasks

    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_refresh(db):
        entered.set()
        await release.wait()

    monkeypatch.setattr(tasks, "refresh_reservation_states", slow_refresh)
    monkeypatch.setattr(tasks, "expire_restrictions", lambda db: asyncio.sleep(0, result=0))
    monkeypatch.setattr(tasks, "purge_expired_private_media", lambda db: asyncio.sleep(0, result=0))
    monkeypatch.setattr(tasks, "deliver_due_notifications", lambda db: asyncio.sleep(0, result=0))

    first = asyncio.create_task(minute_tick())
    await entered.wait()
    second = await minute_tick()
    release.set()
    first_result = await first
    async with async_session() as db:
        heartbeat = await db.get(SystemSetting, "worker_last_success_at")
    return first_result, second, heartbeat


def test_worker_uses_single_leader_and_records_heartbeat(client, monkeypatch):
    first, second, heartbeat = asyncio.run(run_overlapping_ticks(monkeypatch))
    assert first["status"] == "ok"
    assert second["status"] == "skipped"
    assert heartbeat and heartbeat.value


async def create_unbound_notification() -> int:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.student_id == "admin001"))).scalar_one()
        notification = Notification(
            user_id=user.id,
            type=NotificationType.submitted,
            payload={"room": "A101", "date": "2026-08-13"},
            scheduled_at=local_now() - timedelta(minutes=1),
        )
        db.add(notification)
        await db.commit()
        return notification.id


async def notification_state(notification_id: int):
    async with async_session() as db:
        return await db.get(Notification, notification_id)


def test_unbound_notification_does_not_remain_pending(client):
    notification_id = asyncio.run(create_unbound_notification())
    async def deliver():
        async with async_session() as db:
            return await deliver_due_notifications(db)
    assert asyncio.run(deliver()) >= 1
    notification = asyncio.run(notification_state(notification_id))
    assert notification.status == NotificationStatus.failed
    assert "未绑定微信" in notification.error
    assert notification.attempts == 1


class FakeTokenClient:
    def __init__(self):
        self.calls = 0

    async def get(self, *args, **kwargs):
        self.calls += 1
        return httpx.Response(200, json={"access_token": "cached-token", "expires_in": 7200})


def test_wechat_access_token_is_cached(monkeypatch):
    _token_cache.update({"value": "", "expires_at": None})
    fake = FakeTokenClient()

    async def exercise():
        first = await _access_token(fake)
        second = await _access_token(fake)
        return first, second

    first, second = asyncio.run(exercise())
    assert first == second == "cached-token"
    assert fake.calls == 1
