"""Durable WeChat subscription-message outbox.

Events are committed with the business transaction and sent asynchronously.  A
provider outage therefore never rolls back an approved reservation.
"""
import asyncio
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification, NotificationStatus, NotificationType, User, local_now


TEMPLATE_IDS = {
    NotificationType.submitted: settings.WECHAT_TEMPLATE_SUBMITTED,
    NotificationType.review_result: settings.WECHAT_TEMPLATE_REVIEW,
    NotificationType.starting_soon: settings.WECHAT_TEMPLATE_REMINDER,
    NotificationType.restriction: settings.WECHAT_TEMPLATE_RESTRICTION,
}
_token_cache: dict[str, object] = {"value": "", "expires_at": None}
_token_lock = asyncio.Lock()


def public_template_ids() -> list[str]:
    return [value for value in TEMPLATE_IDS.values() if value]


async def _access_token(client: httpx.AsyncClient) -> str:
    now = local_now()
    expires_at = _token_cache["expires_at"]
    if _token_cache["value"] and isinstance(expires_at, datetime) and expires_at > now:
        return str(_token_cache["value"])
    async with _token_lock:
        expires_at = _token_cache["expires_at"]
        if _token_cache["value"] and isinstance(expires_at, datetime) and expires_at > now:
            return str(_token_cache["value"])
        response = await client.get("https://api.weixin.qq.com/cgi-bin/token", params={
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
        })
        payload = response.json()
        if "access_token" not in payload:
            raise RuntimeError(payload.get("errmsg", "获取access_token失败"))
        ttl = max(int(payload.get("expires_in", 7200)) - 300, 60)
        _token_cache["value"] = payload["access_token"]
        _token_cache["expires_at"] = now + timedelta(seconds=ttl)
        return str(payload["access_token"])


def _template_data(notification: Notification) -> dict:
    payload = notification.payload
    # Keyword names must match the templates selected in the WeChat console.
    if notification.type == NotificationType.submitted:
        return {"thing1": {"value": payload.get("room", "预约已提交")[:20]}, "time2": {"value": f"{payload.get('date', '')} {payload.get('time', '')}"[:20]}}
    if notification.type == NotificationType.review_result:
        return {"phrase1": {"value": "已通过" if payload.get("result") == "approved" else "未通过"}, "thing2": {"value": (payload.get("reason") or "请进入小程序查看")[:20]}}
    if notification.type == NotificationType.starting_soon:
        return {"thing1": {"value": "预约即将开始"}, "time2": {"value": payload.get("date", "")}}
    return {"thing1": {"value": "预约资格变更"}, "thing2": {"value": (payload.get("reason") or "请进入小程序查看")[:20]}}


async def deliver_due_notifications(db: AsyncSession, limit: int = 100) -> int:
    result = await db.execute(select(Notification).where(
        Notification.status == NotificationStatus.pending,
        Notification.scheduled_at <= local_now(),
    ).order_by(Notification.scheduled_at).limit(limit).with_for_update(skip_locked=True))
    notifications = list(result.scalars())
    if not notifications:
        return 0
    deliverable: list[tuple[Notification, User, str]] = []
    for notification in notifications:
        user = await db.get(User, notification.user_id)
        template_id = TEMPLATE_IDS.get(notification.type)
        if not user or not user.wechat_openid:
            notification.attempts += 1
            notification.status = NotificationStatus.failed
            notification.error = "账号未绑定微信，通知不再重试"
        elif not template_id:
            notification.attempts += 1
            notification.status = NotificationStatus.failed
            notification.error = "通知模板未配置，通知不再重试"
        elif not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
            notification.attempts += 1
            notification.status = NotificationStatus.failed
            notification.error = "微信服务凭据未配置，通知不再重试"
        else:
            deliverable.append((notification, user, template_id))
    if not deliverable:
        await db.commit()
        return len(notifications)
    async with httpx.AsyncClient(timeout=10) as client:
        token = await _access_token(client)
        for notification, user, template_id in deliverable:
            notification.attempts += 1
            try:
                response = await client.post(
                    f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}",
                    json={"touser": user.wechat_openid, "template_id": template_id, "page": "pages/my/my", "data": _template_data(notification)},
                )
                payload = response.json()
                if payload.get("errcode", 0) != 0:
                    raise RuntimeError(payload.get("errmsg", "发送失败"))
                notification.status = NotificationStatus.sent
                notification.sent_at = local_now()
                notification.error = None
            except Exception as exc:  # provider errors are captured in the outbox
                notification.error = str(exc)[:500]
                if notification.attempts >= 5:
                    notification.status = NotificationStatus.failed
    await db.commit()
    return len(notifications)
