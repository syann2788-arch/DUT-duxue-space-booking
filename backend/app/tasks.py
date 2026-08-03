from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session
from app.models import SystemSetting, local_now
from app.notifications import deliver_due_notifications
from app.services import auto_approve_pending, get_runtime_config, refresh_reservation_states


scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def minute_tick() -> None:
    async with async_session() as db:
        await refresh_reservation_states(db)
        config = await get_runtime_config(db)
        now = local_now()
        last = await db.get(SystemSetting, "last_auto_approval_date")
        if now.strftime("%H:%M") == config["auto_approval_time"] and (not last or last.value != now.date().isoformat()):
            await auto_approve_pending(db)
            if last:
                last.value = now.date().isoformat()
            else:
                db.add(SystemSetting(key="last_auto_approval_date", value=now.date().isoformat(), description="内部任务游标"))
            await db.commit()
        await deliver_due_notifications(db)


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.add_job(minute_tick, "interval", minutes=1, id="reservation-minute-tick", max_instances=1, coalesce=True)
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
