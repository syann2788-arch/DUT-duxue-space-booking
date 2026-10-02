from __future__ import annotations

import asyncio
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import validate_runtime_security
from app.database import init_db
from app.observability import configure_logging, log_event
from app.tasks import minute_tick


async def run_worker() -> None:
    configure_logging()
    validate_runtime_security()
    await init_db()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:
            pass

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(minute_tick, "interval", minutes=1, id="reservation-minute-tick", max_instances=1, coalesce=True)
    scheduler.start()
    log_event("worker_started")
    try:
        await minute_tick()
        await stop.wait()
    finally:
        scheduler.shutdown(wait=False)
        log_event("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
