"""Administrator reservation and cleanup review use cases."""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common import queue_notification, slot_datetime
from app.domain.reservations import refresh_reservation_states
from app.domain.restrictions import add_restriction, record_violation
from app.domain.settings import get_runtime_config
from app.models import (
    CleanupStatus, CleanupVerification, NotificationType, Reservation,
    ReservationStatus, ReviewDecision, ViolationType, local_now,
)
from app.schemas import CleanupReviewRequest, ReservationReviewRequest, RestrictionCreate


async def review_reservations(db: AsyncSession, request: ReservationReviewRequest, admin_id: int, auto: bool = False) -> dict:
    await refresh_reservation_states(db)
    reservations = list((await db.execute(select(Reservation).where(
        Reservation.id.in_(request.reservation_ids),
        Reservation.status == ReservationStatus.pending,
    ).with_for_update())).scalars())
    now = local_now()
    target = ReservationStatus.approved if request.decision == ReviewDecision.approved else ReservationStatus.rejected
    config = await get_runtime_config(db)
    for reservation in reservations:
        reservation.status = target
        reservation.review_note = request.note or ("系统23:00自动审批" if auto else "")
        reservation.reviewed_by = None if auto else admin_id
        reservation.reviewed_at = now
        reservation.auto_approved = auto
        queue_notification(db, reservation.user_id, reservation.id, NotificationType.review_result, {
            "result": target.value, "reason": reservation.review_note or "",
        })
        if target == ReservationStatus.approved and reservation.start_slot is not None:
            remind_at = slot_datetime(reservation.date, reservation.start_slot, config) - timedelta(minutes=config["reminder_minutes"])
            queue_notification(db, reservation.user_id, reservation.id, NotificationType.starting_soon, {
                "date": reservation.date.isoformat(),
            }, remind_at)
    await db.commit()
    return {"processed": len(reservations), "requested": len(request.reservation_ids), "status": target.value}


async def auto_approve_pending(db: AsyncSession) -> int:
    ids = list((await db.scalars(select(Reservation.id).where(Reservation.status == ReservationStatus.pending))).all())
    if not ids:
        return 0
    result = await review_reservations(db, ReservationReviewRequest(
        reservation_ids=ids, decision=ReviewDecision.approved, note="系统23:00自动审批",
    ), admin_id=0, auto=True)
    return result["processed"]


async def review_cleanup(db: AsyncSession, cleanup_id: int, request: CleanupReviewRequest, admin_id: int) -> CleanupVerification:
    cleanup = await db.get(CleanupVerification, cleanup_id, with_for_update=True)
    if not cleanup or cleanup.status != CleanupStatus.pending:
        raise HTTPException(404, "待复核记录不存在")
    reservation = await db.get(Reservation, cleanup.reservation_id)
    approved = request.decision.value == "approved"
    cleanup.status = CleanupStatus.approved if approved else CleanupStatus.rejected
    cleanup.reviewed_by, cleanup.reviewed_at, cleanup.review_note = admin_id, local_now(), request.note
    reservation.status = ReservationStatus.completed if approved else ReservationStatus.cleanup_rejected
    if not approved:
        queue_notification(db, reservation.user_id, reservation.id, NotificationType.restriction, {
            "change": "cleanup_rejected", "reason": request.note or "清扫照片核验不合格，请重新上传",
        })
        await record_violation(
            db, reservation.user_id, reservation.id, ViolationType.cleanup_failed,
            local_now(), await get_runtime_config(db),
        )
    if not approved and request.restrict_user:
        await add_restriction(db, reservation.user_id, RestrictionCreate(
            level=request.restriction_level,
            reason=request.note or "现场清扫核验未通过",
            days=request.restriction_days,
        ), admin_id, commit=False)
    await db.commit()
    await db.refresh(cleanup)
    return cleanup
