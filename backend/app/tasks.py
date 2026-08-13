from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine
from app.models import SystemSetting, local_now
from app.notifications import deliver_due_notifications
from app.observability import log_event
from app.domain.media import purge_expired_private_media
from app.domain.reservations import refresh_reservation_states
from app.domain.restrictions import expire_restrictions
from app.domain.reviews import auto_approve_pending
from app.domain.settings import get_runtime_config


LEADER_LOCK_ID = 0x4455585545
_local_tick_lock = asyncio.Lock()


@asynccontextmanager
async def leader_lock():
    if engine.dialect.name == "postgresql":
        async with engine.connect() as connection:
            acquired = bool(await connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": LEADER_LOCK_ID}
            ))
            try:
                yield acquired
            finally:
                if acquired:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": LEADER_LOCK_ID}
                    )
        return
    if _local_tick_lock.locked():
        yield False
        return
    await _local_tick_lock.acquire()
    try:
        yield True
    finally:
        _local_tick_lock.release()


async def _set_worker_state(db: AsyncSession, key: str, value) -> None:
    setting = await db.get(SystemSetting, key)
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key=key, value=value, description="独立任务 worker 运行状态"))
    await db.commit()


async def minute_tick() -> dict:
    job_id = uuid4().hex
    async with leader_lock() as acquired:
        if not acquired:
            log_event("worker_tick_skipped", job_id=job_id, reason="leader_lock_busy")
            return {"status": "skipped", "job_id": job_id}
        async with async_session() as db:
            started = local_now()
            await _set_worker_state(db, "worker_last_started_at", started.isoformat())
            log_event("worker_tick_started", job_id=job_id)
            try:
                await refresh_reservation_states(db)
                await expire_restrictions(db)
                expired_media = await purge_expired_private_media(db)
                config = await get_runtime_config(db)
                now = local_now()
                last = (await db.execute(
                    select(SystemSetting)
                    .where(SystemSetting.key == "last_auto_approval_date")
                    .with_for_update()
                )).scalar_one_or_none()
                approved = 0
                if now.strftime("%H:%M") == config["auto_approval_time"] and (
                    not last or last.value != now.date().isoformat()
                ):
                    approved = await auto_approve_pending(db)
                    if last:
                        last.value = now.date().isoformat()
                    else:
                        db.add(SystemSetting(
                            key="last_auto_approval_date",
                            value=now.date().isoformat(),
                            description="内部任务游标",
                        ))
                    await db.commit()
                notifications = await deliver_due_notifications(db)
                finished = local_now()
                result = {
                    "status": "ok",
                    "job_id": job_id,
                    "approved": approved,
                    "expired_media": expired_media,
                    "notifications": notifications,
                    "duration_ms": round((finished - started).total_seconds() * 1000, 2),
                }
                await _set_worker_state(db, "worker_last_success_at", finished.isoformat())
                await _set_worker_state(db, "worker_last_result", result)
                log_event("worker_tick_succeeded", **result)
                return result
            except Exception as exc:
                await db.rollback()
                await _set_worker_state(db, "worker_last_error", {
                    "job_id": job_id,
                    "at": local_now().isoformat(),
                    "type": exc.__class__.__name__,
                    "message": str(exc)[:500],
                })
                log_event("worker_tick_failed", job_id=job_id, error_type=exc.__class__.__name__, error=str(exc)[:500])
                raise
