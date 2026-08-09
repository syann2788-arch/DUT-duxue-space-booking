from contextlib import asynccontextmanager
import logging
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, validate_runtime_settings
from app.database import get_db, init_db
from app.routers import admin, auth, notifications, reservations, rooms
from app.tasks import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_settings()
    await init_db()
    if settings.ENABLE_SCHEDULER:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="笃学书院空间预约系统", version="2.0.0", lifespan=lifespan)


logger = logging.getLogger("app.requests")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started) * 1000,
        request_id,
    )
    return response
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(admin.router)
app.include_router(notifications.router)


@app.get("/api/health")
@app.get("/api/health/live")
async def health_live():
    return {"status": "ok", "version": app.version}


@app.get("/api/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "version": app.version, "database": "ok"}
