import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings, validate_runtime_settings
from app.database import async_session
from app.models import Notification, NotificationStatus, NotificationType, User
from app.notifications import TEMPLATE_IDS, _TOKEN_CACHE, _access_token, deliver_due_notifications
from app.schemas import CleanupSubmit, ReservationAdminOut, ReservationBaseOut, ReservationSelfOut


def test_production_configuration_rejects_demo_security_defaults():
    unsafe = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://user:pass@db/app",
        SECRET_KEY="change-me-in-production",
        ALLOW_OPEN_REGISTRATION=True,
        CORS_ORIGINS="http://localhost:5173",
    )
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings(unsafe)
    message = str(exc.value)
    assert "SECRET_KEY" in message or "32" in message
    assert "开放注册" in message


def test_reservation_response_models_are_explicit_privacy_whitelists():
    assert "campus_card_photo_url" not in ReservationBaseOut.model_fields
    assert "user" not in ReservationBaseOut.model_fields
    assert "campus_card_photo_url" in ReservationSelfOut.model_fields
    assert "user" not in ReservationSelfOut.model_fields
    assert "user" in ReservationAdminOut.model_fields


def test_cleanup_submission_rejects_external_or_wrong_purpose_images():
    assert CleanupSubmit(photo_urls=["/uploads/cleanup_1_ok.jpg"]).photo_urls
    for value in ("/uploads/campus_card_1.jpg", "https://example.com/fake.jpg"):
        with pytest.raises(ValidationError):
            CleanupSubmit(photo_urls=[value])


def test_registration_can_be_closed_without_changing_routes(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ALLOW_OPEN_REGISTRATION", False)
    response = client.post("/api/auth/register", json={
        "student_id": "20990001",
        "name": "测试用户",
        "phone": "13900000001",
        "class_name": "9901",
        "password": "test1234",
    })
    assert response.status_code == 403
    assert "开放注册已关闭" in response.json()["detail"]


def test_unbound_notification_is_failed_instead_of_pending_forever(client, monkeypatch):
    from app.config import settings

    register = client.post("/api/auth/register", json={
        "student_id": "20990002",
        "name": "通知测试",
        "phone": "13900000002",
        "class_name": "9902",
        "password": "test1234",
    })
    assert register.status_code == 200
    user_id = register.json()["user"]["id"]

    async def exercise():
        async with async_session() as db:
            db.add(Notification(
                user_id=user_id,
                type=NotificationType.submitted,
                payload={"room": "A101"},
            ))
            await db.commit()
        async with async_session() as db:
            processed = await deliver_due_notifications(db)
            item = (await db.execute(select(Notification).where(
                Notification.user_id == user_id,
            ))).scalar_one()
            return processed, item.status, item.attempts, item.error

    monkeypatch.setattr(settings, "WECHAT_APP_ID", "test-app")
    monkeypatch.setattr(settings, "WECHAT_APP_SECRET", "test-secret")
    monkeypatch.setitem(TEMPLATE_IDS, NotificationType.submitted, "template-id")
    processed, status, attempts, error = asyncio.run(exercise())
    assert processed >= 1
    assert status == NotificationStatus.failed
    assert attempts == 1
    assert "no bound WeChat" in error


def test_wechat_access_token_is_cached():
    class FakeResponse:
        def json(self):
            return {"access_token": "cached-token", "expires_in": 7200}

    class FakeClient:
        calls = 0

        async def get(self, *_args, **_kwargs):
            self.calls += 1
            return FakeResponse()

    async def exercise():
        client = FakeClient()
        _TOKEN_CACHE.update(value="", expires_at=0.0)
        first = await _access_token(client)
        second = await _access_token(client)
        return client.calls, first, second

    calls, first, second = asyncio.run(exercise())
    assert (calls, first, second) == (1, "cached-token", "cached-token")
