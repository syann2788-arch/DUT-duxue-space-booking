from __future__ import annotations

import csv
import io
import json
import secrets
import string
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
import qrcode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth import hash_password, require_admin
from app.database import get_db
from app.models import BookingRestriction, CleanupStatus, CleanupVerification, Reservation, ReservationStatus, Room, RoomSceneRule, SceneType, User, Violation, local_now
from app.queries import get_all_users, list_admin_reservations, list_cleanup_queue
from app.schemas import (
    BanUserRequest,
    CleanupOut,
    CleanupReviewRequest,
    PublicStatusUpdate,
    ReservationAdminOut,
    ReservationAdminPageOut,
    ReservationReviewRequest,
    RestrictionCreate,
    RestrictionOut,
    RoomRuleUpdate,
    SettingsUpdate,
    UserOut,
    UserPageOut,
    ViolationOut,
)
from app.services import (
    add_restriction,
    create_counselor_user,
    get_counselors,
    get_runtime_config,
    review_cleanup,
    review_reservations,
    revoke_restriction,
    set_counselor,
    update_public_status,
    update_runtime_config,
)

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    today = local_now().date()
    total_users = await db.scalar(select(func.count()).select_from(User))
    pending = await db.scalar(select(func.count(Reservation.id)).where(Reservation.status == ReservationStatus.pending))
    cleanup_pending = await db.scalar(select(func.count(CleanupVerification.id)).where(CleanupVerification.status == CleanupStatus.pending))
    today_count = await db.scalar(select(func.count(Reservation.id)).where(Reservation.date == today))
    return {"total_users": total_users or 0, "pending": pending or 0, "cleanup_pending": cleanup_pending or 0, "today": today_count or 0}


@router.get("/reservations", response_model=ReservationAdminPageOut)
async def reservations(
    date_value: date | None = Query(default=None, alias="date"),
    status_filter: ReservationStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    scene: SceneType | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    items, total = await list_admin_reservations(
        db, date_value, status_filter, date_from, date_to, scene, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_more": offset + len(items) < total}


@router.post("/reservations/review")
async def reservation_review(
    data: ReservationReviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    return await review_reservations(db, data, int(admin["sub"]))


@router.get("/cleanup", response_model=ReservationAdminPageOut)
async def cleanup_queue(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    items, total = await list_cleanup_queue(db, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_more": offset + len(items) < total}


@router.post("/cleanup/{cleanup_id}/review", response_model=CleanupOut)
async def cleanup_review(
    cleanup_id: int,
    data: CleanupReviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    return await review_cleanup(db, cleanup_id, data, int(admin["sub"]))


@router.get("/users", response_model=UserPageOut)
async def users(
    search: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    items, total = await get_all_users(db, search, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_more": offset + len(items) < total}


@router.get("/users/{user_id}/violations", response_model=list[ViolationOut])
async def violations(user_id: int, db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    result = await db.execute(select(Violation).where(Violation.user_id == user_id).order_by(Violation.created_at.desc()))
    return list(result.scalars())


@router.get("/users/{user_id}/restrictions", response_model=list[RestrictionOut])
async def restrictions(user_id: int, db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    result = await db.execute(select(BookingRestriction).where(BookingRestriction.user_id == user_id).order_by(BookingRestriction.created_at.desc()))
    return list(result.scalars())


@router.post("/users/{user_id}/restrictions", response_model=RestrictionOut, status_code=201)
async def restrict_user(
    user_id: int,
    data: RestrictionCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    return await add_restriction(db, user_id, data, int(admin["sub"]))


@router.delete("/restrictions/{restriction_id}")
async def unrestrict(restriction_id: int, db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    if not await revoke_restriction(db, restriction_id):
        raise HTTPException(404, "限制记录不存在")
    return {"message": "已解除限制"}


# Backward-compatible endpoints used by the v1 admin page.
@router.post("/users/ban")
async def legacy_ban(data: BanUserRequest, db: AsyncSession = Depends(get_db), admin: dict = Depends(require_admin)):
    restriction = await add_restriction(db, data.user_id, RestrictionCreate(level="timed", days=data.days, reason="管理员设置"), int(admin["sub"]))
    return {"message": "禁约设置成功", "restriction_id": restriction.id}


@router.put("/rooms/{room_id}/public-status")
async def public_status(
    room_id: int,
    data: PublicStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    room = await update_public_status(db, room_id, data.public_status)
    if not room:
        raise HTTPException(404, "房间不存在或不是公开空间")
    return {"message": "状态已更新"}


@router.put("/room-rules/{rule_id}")
async def update_room_rule(
    rule_id: int,
    data: RoomRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    rule = await db.get(RoomSceneRule, rule_id)
    if not rule:
        raise HTTPException(404, "分房规则不存在")
    rule.priority, rule.capacity, rule.usage_mode, rule.is_enabled = data.priority, data.capacity, data.usage_mode, data.is_enabled
    await db.commit()
    return {"message": "分房规则已更新"}


@router.get("/settings")
async def settings(db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    return await get_runtime_config(db)


@router.put("/settings")
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    return await update_runtime_config(db, data.values, int(admin["sub"]))


@router.get("/export.xlsx")
async def export_xlsx(
    date_from: date | None = None,
    date_to: date | None = None,
    scene: SceneType | None = None,
    status_filter: ReservationStatus | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    records, _ = await list_admin_reservations(
        db, reservation_status=status_filter, date_from=date_from, date_to=date_to, scene=scene
    )
    reservation_ids = [item.id for item in records]
    violations = list((await db.scalars(select(Violation).where(Violation.reservation_id.in_(reservation_ids)))).all()) if reservation_ids else []
    violation_map: dict[int, list[str]] = {}
    for item in violations:
        violation_map.setdefault(item.reservation_id, []).append(item.type.value)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "预约记录"
    sheet.append(["预约号", "日期", "开始时间", "结束时间", "场景", "房间", "姓名", "学号", "联系方式", "人数", "申请理由", "玉兰卡媒体编号", "状态", "审核时间", "审核/驳回原因", "清扫结果", "清扫媒体编号", "违规标记", "创建时间"])
    for item in records:
        sheet.append([
            item.id, item.date.isoformat(), _minute_label(item.start_minute), _minute_label(item.end_minute),
            item.scene.value if item.scene else "", f"{item.room.room_code} {item.room.name}",
            item.user.name, item.user.student_id, item.user.phone, item.people_count, item.purpose,
            item.campus_card_media_id or "", item.status.value,
            item.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if item.reviewed_at else "", item.review_note or "",
            item.cleanup.status.value if item.cleanup else "未提交", ", ".join(item.cleanup.media_ids or []) if item.cleanup else "",
            ", ".join(violation_map.get(item.id, [])), item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    _format_sheet(sheet)

    restriction_sheet = workbook.create_sheet("预约限制记录")
    restriction_sheet.append(["记录号", "姓名", "学号", "联系方式", "限制级别", "开始时间", "结束时间", "限制原因", "当前有效", "创建时间", "解除时间"])
    restriction_records = list((await db.scalars(select(BookingRestriction).options(joinedload(BookingRestriction.user)).order_by(BookingRestriction.created_at.desc()))).all())
    for item in restriction_records:
        restriction_sheet.append([
            item.id, item.user.name, item.user.student_id, item.user.phone, item.level.value,
            item.starts_at.strftime("%Y-%m-%d %H:%M:%S"), item.ends_at.strftime("%Y-%m-%d %H:%M:%S") if item.ends_at else "永久",
            item.reason, "是" if item.is_active else "否", item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            item.revoked_at.strftime("%Y-%m-%d %H:%M:%S") if item.revoked_at else "",
        ])
    _format_sheet(restriction_sheet)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"reservations_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/rooms/{room_id}/checkin-qr")
async def room_checkin_qr(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    room = await db.get(Room, room_id)
    if not room or not room.is_active or not room.can_reserve:
        raise HTTPException(404, "可预约房间不存在")
    payload = json.dumps({"room_id": room.id}, ensure_ascii=False, separators=(",", ":"))
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(output, format="PNG")
    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="checkin-{room.room_code}.png"',
            "Cache-Control": "private, no-store",
        },
    )


def _minute_label(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value // 60:02d}:{value % 60:02d}"


def _format_sheet(sheet) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(max(len(str(cell.value or "")) for cell in column) + 2, 50)


@router.get("/counselors", response_model=list[UserOut])
async def counselors(db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    return await get_counselors(db)


@router.post("/counselors/import")
async def import_counselors(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), _: dict = Depends(require_admin)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "请上传CSV文件")
    try:
        rows = list(csv.reader(io.StringIO((await file.read()).decode("utf-8-sig"))))
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "CSV请保存为UTF-8编码") from exc
    if not rows:
        raise HTTPException(400, "CSV文件为空")
    headers = [item.strip() for item in rows[0]]
    if "姓名" not in headers:
        count = await set_counselor(db, [row[0].strip() for row in rows if row and row[0].strip().isdigit()])
        return {"imported_count": count, "accounts": []}
    index = {name: pos for pos, name in enumerate(headers)}
    accounts = []
    for row in rows[1:]:
        def value(name: str) -> str:
            pos = index.get(name)
            return row[pos].strip() if pos is not None and pos < len(row) else ""
        if value("职务") not in ("辅导员", "执行院长", "副院长") or not value("姓名"):
            continue
        phone = value("联系方式")
        login_id = phone if phone.isdigit() else f"staff_{value('姓名')}"
        password = phone or "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        await create_counselor_user(db, login_id, value("姓名"), phone, value("负责班级"), hash_password(password))
        accounts.append({"name": value("姓名"), "login_id": login_id, "password": password})
    return {"imported_count": len(accounts), "accounts": accounts}
