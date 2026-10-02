"""Paginated operational worklists and controlled account recovery."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import require_admin
from app.database import get_db
from app.models import AdminAuditLog, Reservation, ReservationStatus, Violation, Room
from app.schemas import PasswordResetIssue, ReservationAdminPageOut
from app.domain.accounts import issue_reset
from app.domain.reservations import refresh_reservation_states

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.post("/users/{user_id}/password-reset")
async def issue_password_reset(user_id: int, data: PasswordResetIssue,
                               db: AsyncSession = Depends(get_db), admin: dict = Depends(require_admin)):
    return await issue_reset(db, user_id, int(admin["sub"]), data.admin_password, data.reason)


@router.get("/audit")
async def audit_logs(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                     db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    total = await db.scalar(select(func.count()).select_from(AdminAuditLog))
    rows = (await db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(limit).offset(offset))).all()
    return {"items": [{"id": r.id, "actor_id": r.actor_id, "action": r.action,
                       "target_type": r.target_type, "target_id": r.target_id,
                       "details": r.details, "created_at": r.created_at} for r in rows],
            "total": total, "limit": limit, "offset": offset, "has_more": offset + len(rows) < total}


@router.get("/worklist", response_model=ReservationAdminPageOut)
async def worklist(kind: str = Query("unuploaded", pattern="^(unuploaded|rejected|violations|unresolved)$"),
                   limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                   db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    await refresh_reservation_states(db)
    violation = select(Violation.id).where(Violation.reservation_id == Reservation.id).exists()
    predicate = {
        "unuploaded": (Reservation.status == ReservationStatus.cleanup_pending) & ~Reservation.cleanup.has(),
        "rejected": Reservation.status == ReservationStatus.cleanup_rejected,
        "violations": violation,
        "unresolved": violation & Reservation.status.in_((ReservationStatus.cleanup_pending, ReservationStatus.cleanup_rejected)),
    }[kind]
    total = int(await db.scalar(select(func.count()).select_from(Reservation).where(predicate)) or 0)
    items = (await db.scalars(select(Reservation).where(predicate).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules), joinedload(Reservation.user), joinedload(Reservation.cleanup)
    ).order_by(Reservation.date, Reservation.id).limit(limit).offset(offset))).unique().all()
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_more": offset + len(items) < total}
