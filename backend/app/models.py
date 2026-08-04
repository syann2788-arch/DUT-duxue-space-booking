"""Database models for the space reservation domain.

All reservation decisions are persisted explicitly.  In particular, a reservation
stores the scene, allocation mode and review outcome that were effective when it
was created, so later configuration changes do not rewrite history.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


CHINA_TZ = ZoneInfo("Asia/Shanghai")


def local_now() -> datetime:
    """Naive Asia/Shanghai time, matching the Date + slot representation."""
    return datetime.now(CHINA_TZ).replace(tzinfo=None)


class UserRole(str, enum.Enum):
    student = "student"
    counselor = "counselor"
    admin = "admin"


class SceneType(str, enum.Enum):
    study = "study"
    meeting = "meeting"
    event = "event"
    music = "music"


class UsageMode(str, enum.Enum):
    shared = "shared"
    exclusive = "exclusive"


class ReservationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    in_use = "in_use"
    cleanup_pending = "cleanup_pending"
    cleanup_rejected = "cleanup_rejected"
    completed = "completed"
    missed = "missed"
    # Kept so old v1 rows can be read and migrated lazily.
    active = "active"
    checked_in = "checked_in"


class ReviewDecision(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"


class CleanupStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RestrictionLevel(str, enum.Enum):
    temporary = "temporary"
    timed = "timed"
    permanent = "permanent"


class NotificationType(str, enum.Enum):
    submitted = "submitted"
    review_result = "review_result"
    starting_soon = "starting_soon"
    restriction = "restriction"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class PublicStatus(str, enum.Enum):
    free = "free"
    busy = "busy"
    crowded = "crowded"


class ViolationType(str, enum.Enum):
    no_show = "no_show"
    cleanup_failed = "cleanup_failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(20))
    class_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.student)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user", foreign_keys="Reservation.user_id")
    restrictions: Mapped[list["BookingRestriction"]] = relationship(back_populates="user", foreign_keys="BookingRestriction.user_id")
    space_messages: Mapped[list["SpaceMessage"]] = relationship(back_populates="user")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    can_reserve: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    public_status: Mapped[PublicStatus | None] = mapped_column(SAEnum(PublicStatus), nullable=True)
    who_can_reserve: Mapped[str] = mapped_column(String(20), default="all")
    has_fridge: Mapped[bool] = mapped_column(Boolean, default=False)
    has_instruments: Mapped[bool] = mapped_column(Boolean, default=False)
    floor_plan_x: Mapped[float] = mapped_column(default=0.0)
    floor_plan_y: Mapped[float] = mapped_column(default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="room")
    scene_rules: Mapped[list["RoomSceneRule"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    messages: Mapped[list["SpaceMessage"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class RoomSceneRule(Base):
    """Admin-editable allocation rule for one scene/room pair."""
    __tablename__ = "room_scene_rules"
    __table_args__ = (UniqueConstraint("room_id", "scene", name="uq_room_scene"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    scene: Mapped[SceneType] = mapped_column(SAEnum(SceneType), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    capacity: Mapped[int] = mapped_column(Integer)
    usage_mode: Mapped[UsageMode] = mapped_column(SAEnum(UsageMode))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    room: Mapped[Room] = relationship(back_populates="scene_rules")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Slot 0 is opening time. End is exclusive; 0..28 means 08:00..22:00 by default.
    start_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Absolute minutes since midnight keep history stable if slot rules change.
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # v1 compatibility columns. New code writes both until all deployments migrate.
    start_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene: Mapped[SceneType | None] = mapped_column(SAEnum(SceneType), nullable=True)
    usage_mode: Mapped[UsageMode | None] = mapped_column(SAEnum(UsageMode), nullable=True)
    people_count: Mapped[int] = mapped_column(Integer, default=1)
    purpose: Mapped[str] = mapped_column(String(300), default="")
    campus_card_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReservationStatus] = mapped_column(SAEnum(ReservationStatus), default=ReservationStatus.pending, index=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="reservations", foreign_keys=[user_id])
    room: Mapped[Room] = relationship(back_populates="reservations")
    cleanup: Mapped["CleanupVerification | None"] = relationship(back_populates="reservation", uselist=False, cascade="all, delete-orphan")


class CleanupVerification(Base):
    __tablename__ = "cleanup_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"), unique=True, index=True)
    photo_urls: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[CleanupStatus] = mapped_column(SAEnum(CleanupStatus), default=CleanupStatus.pending, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reservation: Mapped[Reservation] = relationship(back_populates="cleanup")


class SpaceMessage(Base):
    __tablename__ = "space_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(String(500), default="")
    photo_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, index=True)

    room: Mapped[Room] = relationship(back_populates="messages")
    user: Mapped[User] = relationship(back_populates="space_messages")


class BookingRestriction(Base):
    __tablename__ = "booking_restrictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    level: Mapped[RestrictionLevel] = mapped_column(SAEnum(RestrictionLevel))
    reason: Mapped[str] = mapped_column(String(500))
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="restrictions", foreign_keys=[user_id])


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(String(300), default="")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, onupdate=local_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, index=True)
    status: Mapped[NotificationStatus] = mapped_column(SAEnum(NotificationStatus), default=NotificationStatus.pending, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (UniqueConstraint("reservation_id", "type", name="uq_violation_reservation_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    type: Mapped[ViolationType] = mapped_column(SAEnum(ViolationType), default=ViolationType.no_show)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now)
