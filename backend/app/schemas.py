from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import (
    CleanupStatus,
    PublicStatus,
    ReservationStatus,
    RestrictionLevel,
    ReviewDecision,
    SceneType,
    UsageMode,
    UserRole,
    ViolationType,
)


class UserRegister(BaseModel):
    student_id: str = Field(min_length=4, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    phone: str
    class_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=72)

    @field_validator("student_id")
    @classmethod
    def student_id_must_be_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("学号必须为数字")
        return value

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value: str) -> str:
        if not re.fullmatch(r"1[3-9]\d{9}", value):
            raise ValueError("手机号格式不正确")
        return value

    @field_validator("class_name")
    @classmethod
    def class_name_must_be_four_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value):
            raise ValueError("班级必须为4位数字")
        return value

    @field_validator("password")
    @classmethod
    def password_must_contain_letters_and_numbers(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("密码必须同时包含字母和数字")
        return value


class UserLogin(BaseModel):
    student_id: str
    password: str


class WechatBindRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)


class WechatLoginRequest(WechatBindRequest):
    pass


class UserOut(BaseModel):
    id: int
    student_id: str
    name: str
    phone: str
    class_name: str
    role: UserRole
    is_active: bool
    banned_until: datetime | None = None
    model_config = {"from_attributes": True}


class UserProfileOut(UserOut):
    booking_restricted: bool = False
    restriction_level: RestrictionLevel | None = None
    restriction_reason: str | None = None
    restriction_ends_at: datetime | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RoomSceneRuleOut(BaseModel):
    id: int
    room_id: int
    scene: SceneType
    priority: int
    capacity: int
    usage_mode: UsageMode
    is_enabled: bool

    model_config = {"from_attributes": True}


class RoomOut(BaseModel):
    id: int
    room_code: str
    name: str
    description: str | None
    category: str
    capacity: int
    can_reserve: bool
    is_public: bool
    public_status: PublicStatus | None
    who_can_reserve: str
    has_fridge: bool
    has_instruments: bool
    floor_plan_x: float
    floor_plan_y: float
    is_active: bool
    scene_rules: list[RoomSceneRuleOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PublicStatusUpdate(BaseModel):
    public_status: PublicStatus


class SpaceMessageCreate(BaseModel):
    content: str = Field(default="", max_length=500)
    photo_urls: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_message(self):
        self.content = self.content.strip()
        if not self.content and not self.photo_urls:
            raise ValueError("留言文字和照片至少填写一项")
        if any(not value.startswith("/uploads/message_") for value in self.photo_urls):
            raise ValueError("留言照片地址无效")
        return self


class SpaceMessageOut(BaseModel):
    id: int
    room_id: int
    content: str
    photo_urls: list[str]
    author_name: str
    created_at: datetime


class ReservationCreate(BaseModel):
    scene: SceneType
    date: date
    start_slot: int = Field(ge=0)
    end_slot: int = Field(gt=0)
    people_count: int = Field(ge=1, le=500)
    purpose: str = Field(default="", max_length=300)
    campus_card_media_id: str = Field(min_length=36, max_length=36)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_slot <= self.start_slot:
            raise ValueError("结束时间必须晚于开始时间")
        if self.scene == SceneType.study:
            if self.people_count != 1:
                raise ValueError("自习实行一人一约，预约人数必须为1")
            self.purpose = self.purpose.strip() or "个人自习"
        elif len(self.purpose.strip()) < 10:
            raise ValueError("申请理由至少填写10个字")
        return self


class CleanupOut(BaseModel):
    id: int
    reservation_id: int
    status: CleanupStatus
    submitted_at: datetime
    reviewed_at: datetime | None
    review_note: str | None

    model_config = {"from_attributes": True}


class CleanupAdminOut(CleanupOut):
    media_ids: list[str] = Field(default_factory=list)


class ReservationOut(BaseModel):
    id: int
    user_id: int
    room_id: int
    date: date
    start_slot: int | None
    end_slot: int | None
    start_minute: int | None
    end_minute: int | None
    scene: SceneType | None
    usage_mode: UsageMode | None
    people_count: int
    purpose: str
    status: ReservationStatus
    review_note: str | None
    auto_approved: bool
    created_at: datetime
    cancelled_at: datetime | None
    checked_in_at: datetime | None
    room: RoomOut | None = None
    cleanup: CleanupOut | None = None

    model_config = {"from_attributes": True}


class ReservationAdminOut(ReservationOut):
    campus_card_media_id: str | None = None
    user: UserOut | None = None
    cleanup: CleanupAdminOut | None = None


class CheckinRequest(BaseModel):
    reservation_id: int


class CleanupSubmit(BaseModel):
    media_ids: list[str] = Field(min_length=1, max_length=6)

    @field_validator("media_ids")
    @classmethod
    def validate_media_ids(cls, values: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[0-9a-fA-F-]{36}", value) for value in values):
            raise ValueError("照片凭证无效")
        if len(set(values)) != len(values):
            raise ValueError("照片凭证不能重复")
        return values


class ReservationReviewRequest(BaseModel):
    reservation_ids: list[int] = Field(min_length=1, max_length=200)
    decision: ReviewDecision
    note: str = Field(default="", max_length=500)


class CleanupReviewRequest(BaseModel):
    decision: ReviewDecision
    note: str = Field(default="", max_length=500)
    restrict_user: bool = False
    restriction_level: RestrictionLevel | None = None
    restriction_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def validate_restriction(self):
        if self.restrict_user and not self.restriction_level:
            raise ValueError("限制预约时必须选择限制等级")
        return self


class RestrictionCreate(BaseModel):
    level: RestrictionLevel
    reason: str = Field(min_length=2, max_length=500)
    days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def validate_days(self):
        if self.level in {RestrictionLevel.temporary, RestrictionLevel.timed} and not self.days:
            raise ValueError("临时/限时封禁必须填写天数")
        return self


class ViolationOut(BaseModel):
    id: int
    user_id: int
    reservation_id: int | None
    type: ViolationType
    created_at: datetime

    model_config = {"from_attributes": True}


class RestrictionOut(BaseModel):
    id: int
    user_id: int
    level: RestrictionLevel
    reason: str
    starts_at: datetime
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class RoomRuleUpdate(BaseModel):
    priority: int = Field(ge=1, le=999)
    capacity: int = Field(ge=1, le=500)
    usage_mode: UsageMode
    is_enabled: bool = True


class CounselorImport(BaseModel):
    student_ids: list[str]


class BanUserRequest(BaseModel):
    user_id: int
    days: int = Field(default=7, ge=1, le=3650)
