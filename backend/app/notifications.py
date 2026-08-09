"""Durable WeChat subscription-message outbox.

Events are committed with the business transaction and sent asynchronously.  A
provider outage therefore never rolls back an approved reservation.
"""
from datetime import datetime
from time import monotonic

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

_TOKEN_CACHE: dict[str, float | str] = {"value": "", "expires_at": 0.0}


def public_template_ids() -> list[str]:
    return [value for value in TEMPLATE_IDS.values() if value]


async def _access_token(client: httpx.AsyncClient) -> str:
    cached = str(_TOKEN_CACHE["value"])
    if cached and float(_TOKEN_CACHE["expires_at"]) > monotonic():
        return cached
    response = await client.get("https://api.weixin.qq.com/cgi-bin/token", params={
        "grant_type": "client_credential",
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
    })
    payload = response.json()
    if "access_token" not in payload:
        raise RuntimeError(payload.get("errmsg", "获取access_token失败"))
    token = str(payload["access_token"])
    # WeChat normally returns 7200 seconds. Refresh five minutes early and use
    # a small lower bound for deterministic tests and unusual provider replies.
    expires_in = max(int(payload.get("expires_in", 7200)) - 300, 1)
    _TOKEN_CACHE.update(value=token, expires_at=monotonic() + expires_in)
    return token


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
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        for notification in notifications:
            notification.attempts += 1
            notification.status = NotificationStatus.failed
            notification.error = "WeChat application credentials are not configured"
        await db.commit()
        return len(notifications)
    deliverable: list[tuple[Notification, User, str]] = []
    for notification in notifications:
        user = await db.get(User, notification.user_id)
        template_id = TEMPLATE_IDS.get(notification.type)
        if not user or not user.wechat_openid or not template_id:
            notification.attempts += 1
            notification.status = NotificationStatus.failed
            if not user:
                notification.error = "notification user no longer exists"
            elif not user.wechat_openid:
                notification.error = "user has no bound WeChat account"
            else:
                notification.error = "notification template is not configured"
            continue
        deliverable.append((notification, user, template_id))

    if deliverable:
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
