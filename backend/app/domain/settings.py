"""Runtime booking configuration ownership."""
from datetime import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_RUNTIME_CONFIG
from app.models import SystemSetting


async def get_runtime_config(db: AsyncSession) -> dict:
    result = await db.execute(select(SystemSetting))
    values = dict(DEFAULT_RUNTIME_CONFIG)
    values.update({item.key: item.value for item in result.scalars() if item.key in DEFAULT_RUNTIME_CONFIG})
    return values


async def update_runtime_config(db: AsyncSession, values: dict, admin_id: int) -> dict:
    unknown = set(values) - set(DEFAULT_RUNTIME_CONFIG)
    if unknown:
        raise HTTPException(400, f"未知配置项: {', '.join(sorted(unknown))}")
    merged = {**await get_runtime_config(db), **values}
    validate_runtime_config(merged)
    for key, value in values.items():
        setting = await db.get(SystemSetting, key)
        if setting:
            setting.value = value
            setting.updated_by = admin_id
        else:
            db.add(SystemSetting(key=key, value=value, updated_by=admin_id))
    await db.commit()
    return await get_runtime_config(db)


def validate_runtime_config(config: dict) -> None:
    integer_keys = set(DEFAULT_RUNTIME_CONFIG) - {"auto_approval_time"}
    invalid_integer = next((key for key in sorted(integer_keys) if isinstance(config.get(key), bool) or not isinstance(config.get(key), int)), None)
    if invalid_integer:
        raise HTTPException(400, f"配置项 {invalid_integer} 必须为整数")
    if config["open_hour"] < 0 or config["close_hour"] > 24 or config["open_hour"] >= config["close_hour"]:
        raise HTTPException(400, "开放时段配置无效")
    if config["slot_minutes"] not in (15, 30, 60) or 60 % config["slot_minutes"]:
        raise HTTPException(400, "预约粒度只能为15、30或60分钟且必须整除60分钟")
    if config["max_minutes_per_day"] < config["slot_minutes"] or config["max_minutes_per_day"] % config["slot_minutes"]:
        raise HTTPException(400, "单日时长上限必须是不小于一个时段的整数倍")
    if any(config[key] < 0 for key in ("advance_days", "cancel_deadline_minutes", "checkin_grace_minutes", "reminder_minutes")):
        raise HTTPException(400, "预约天数及时间窗口不能为负数")
    if any(config[key] < 1 for key in ("temporary_ban_days", "violation_threshold", "violation_ban_days")):
        raise HTTPException(400, "限制天数和违约阈值必须大于0")
    if not 0 <= config["music_a103_start_hour"] < config["music_a103_end_hour"] <= 24:
        raise HTTPException(400, "A103钢琴开放时段配置无效")
    try:
        time.fromisoformat(config["auto_approval_time"])
    except (TypeError, ValueError):
        raise HTTPException(400, "自动审批时间应为 HH:MM")
