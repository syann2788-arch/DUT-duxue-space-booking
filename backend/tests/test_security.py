import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import Settings, settings, validate_runtime_security
from app.database import async_session
from app.models import MediaAccessLog, PrivateMedia, local_now
from app.services import purge_expired_private_media
from conftest import auth_header


def register(client, suffix: int) -> tuple[str, dict]:
    response = client.post("/api/auth/register", json={
        "student_id": f"202601{suffix:02d}",
        "name": f"隐私测试学生{suffix}",
        "phone": f"138000001{suffix:02d}",
        "class_name": "2601",
        "password": "Test1234",
    })
    assert response.status_code == 200, response.text
    return response.json()["access_token"], response.json()["user"]


def upload_private(client, token: str, kind: str) -> str:
    path = "/api/reservations/campus-card-photo" if kind == "campus_card" else "/api/reservations/photos"
    response = client.post(
        path,
        headers=auth_header(token),
        files={"file": (f"{kind}.jpg", b"\xff\xd8\xff\xe0private-test", "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()["media_id"]


async def media_audit_count(media_id: str) -> int:
    async with async_session() as db:
        return int(await db.scalar(
            select(func.count(MediaAccessLog.id)).where(MediaAccessLog.media_id == media_id)
        ) or 0)


async def expire_and_purge(media_id: str) -> tuple[bool, bool, int]:
    async with async_session() as db:
        media = await db.get(PrivateMedia, media_id)
        path = Path(settings.PRIVATE_UPLOAD_DIR) / media.storage_key
        existed_before = path.is_file()
        media.expires_at = local_now() - timedelta(seconds=1)
        await db.commit()
        purged = await purge_expired_private_media(db)
        await db.refresh(media)
        return existed_before, path.exists(), purged


def test_production_rejects_default_or_weak_secret():
    validate_runtime_security(Settings(APP_ENV="development", SECRET_KEY="change-me-in-production"))
    with pytest.raises(RuntimeError):
        validate_runtime_security(Settings(APP_ENV="production", SECRET_KEY="change-me-in-production"))
    with pytest.raises(RuntimeError):
        validate_runtime_security(Settings(APP_ENV="production", SECRET_KEY="too-short"))
    with pytest.raises(RuntimeError):
        validate_runtime_security(Settings(
            APP_ENV="development",
            DATABASE_URL="postgresql+asyncpg://app:password@db/app",
            SECRET_KEY="change-me-in-production",
        ))
    validate_runtime_security(Settings(APP_ENV="production", SECRET_KEY="s" * 48))


def test_sensitive_media_is_private_owned_audited_and_expirable(client):
    owner_token, owner = register(client, 70)
    outsider_token, outsider = register(client, 71)
    assert "wechat_openid" not in owner
    assert "wechat_openid" not in outsider

    media_id = upload_private(client, owner_token, "campus_card")
    assert client.get(f"/api/media/{media_id}").status_code in {401, 403}
    assert client.get(f"/api/media/{media_id}", headers=auth_header(owner_token)).status_code == 403
    assert client.get(f"/api/media/{media_id}", headers=auth_header(outsider_token)).status_code == 403
    assert client.get(f"/uploads/{media_id}.jpg").status_code == 404

    day = (local_now().date() + timedelta(days=1)).isoformat()
    foreign_reference = client.post("/api/reservations", headers=auth_header(outsider_token), json={
        "scene": "study", "date": day, "start_slot": 0, "end_slot": 1,
        "people_count": 1, "purpose": "个人自习", "campus_card_media_id": media_id,
    })
    assert foreign_reference.status_code == 403

    wrong_purpose_id = upload_private(client, owner_token, "cleanup")
    wrong_purpose = client.post("/api/reservations", headers=auth_header(owner_token), json={
        "scene": "study", "date": day, "start_slot": 0, "end_slot": 1,
        "people_count": 1, "purpose": "个人自习", "campus_card_media_id": wrong_purpose_id,
    })
    assert wrong_purpose.status_code == 403

    created = client.post("/api/reservations", headers=auth_header(owner_token), json={
        "scene": "study", "date": day, "start_slot": 0, "end_slot": 1,
        "people_count": 1, "purpose": "个人自习", "campus_card_media_id": media_id,
    })
    assert created.status_code == 201, created.text
    assert "campus_card_media_id" not in created.json()
    assert "campus_card_photo_url" not in created.json()
    assert "user" not in created.json()

    admin_login = client.post("/api/auth/login", json={"student_id": "admin001", "password": "admin123"})
    admin = auth_header(admin_login.json()["access_token"])
    downloaded = client.get(f"/api/media/{media_id}", headers=admin)
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"\xff\xd8\xff")
    assert asyncio.run(media_audit_count(media_id)) == 1

    pending = client.get("/api/admin/reservations?status_filter=pending", headers=admin)
    admin_record = next(item for item in pending.json() if item["id"] == created.json()["id"])
    assert admin_record["campus_card_media_id"] == media_id
    assert admin_record["user"]["student_id"] == "20260170"
    assert "wechat_openid" not in admin_record["user"]

    expiring_id = upload_private(client, owner_token, "cleanup")
    existed_before, exists_after, purged = asyncio.run(expire_and_purge(expiring_id))
    assert existed_before is True
    assert exists_after is False
    assert purged == 1
    assert client.get(f"/api/media/{expiring_id}", headers=admin).status_code == 404
