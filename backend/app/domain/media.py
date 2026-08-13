"""Private media claiming, cleanup submission, and retention."""
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.domain.common import reservation_end
from app.domain.settings import get_runtime_config
from app.models import CleanupStatus, CleanupVerification, MediaPurpose, PrivateMedia, Reservation, ReservationStatus, local_now


async def claim_private_media(
    db: AsyncSession,
    media_ids: list[str],
    owner_id: int,
    purpose: MediaPurpose,
    reservation_id: int | None = None,
) -> list[PrivateMedia]:
    result = await db.execute(select(PrivateMedia).where(
        PrivateMedia.id.in_(media_ids)
    ).order_by(PrivateMedia.id).with_for_update())
    media = list(result.scalars())
    if len({item.id for item in media}) != len(set(media_ids)):
        raise HTTPException(400, "照片凭证不存在")
    now = local_now()
    for item in media:
        if item.owner_id != owner_id or item.purpose != purpose or not item.is_active:
            raise HTTPException(403, "照片凭证不属于当前用户或用途不匹配")
        if item.expires_at <= now:
            raise HTTPException(410, "照片凭证已超过保留期限")
        if item.reservation_id is not None and item.reservation_id != reservation_id:
            raise HTTPException(409, "照片凭证已用于其他预约")
    return media


async def purge_expired_private_media(db: AsyncSession) -> int:
    expired = list((await db.scalars(select(PrivateMedia).where(
        PrivateMedia.deleted_at.is_(None), PrivateMedia.expires_at <= local_now()
    ).with_for_update())).all())
    private_root = Path(settings.PRIVATE_UPLOAD_DIR)
    deleted_at = local_now()
    for item in expired:
        if Path(item.storage_key).name == item.storage_key:
            (private_root / item.storage_key).unlink(missing_ok=True)
        item.is_active = False
        item.deleted_at = deleted_at
    if expired:
        await db.commit()
    return len(expired)


async def submit_cleanup(db: AsyncSession, reservation_id: int, user_id: int, media_ids: list[str]) -> Reservation:
    reservation = (await db.execute(select(Reservation).options(
        joinedload(Reservation.cleanup)
    ).where(Reservation.id == reservation_id).with_for_update())).scalar_one_or_none()
    if not reservation or reservation.user_id != user_id:
        raise HTTPException(404, "预约不存在")
    config = await get_runtime_config(db)
    if local_now() < reservation_end(reservation, config):
        raise HTTPException(400, "预约结束后才能提交清扫照片")
    allowed = (
        ReservationStatus.in_use, ReservationStatus.checked_in,
        ReservationStatus.cleanup_pending, ReservationStatus.cleanup_rejected,
    )
    if reservation.status not in allowed:
        raise HTTPException(409, "当前预约状态不能提交清扫照片")
    media = await claim_private_media(db, media_ids, user_id, MediaPurpose.cleanup, reservation.id)
    cleanup = reservation.cleanup
    if cleanup:
        previous_ids = set(cleanup.media_ids or [])
        cleanup.photo_urls = []
        cleanup.media_ids = media_ids
        cleanup.status = CleanupStatus.pending
        cleanup.submitted_at = local_now()
        cleanup.review_note = None
    else:
        previous_ids = set()
        db.add(CleanupVerification(reservation_id=reservation.id, photo_urls=[], media_ids=media_ids))
    for item in media:
        item.reservation_id = reservation.id
    retired_ids = previous_ids - set(media_ids)
    if retired_ids:
        retired = list((await db.scalars(select(PrivateMedia).where(
            PrivateMedia.id.in_(retired_ids), PrivateMedia.owner_id == user_id
        ))).all())
        for item in retired:
            item.is_active = False
    reservation.status = ReservationStatus.cleanup_pending
    await db.commit()
    from app.domain.reservations import get_reservation
    return await get_reservation(db, reservation.id)
