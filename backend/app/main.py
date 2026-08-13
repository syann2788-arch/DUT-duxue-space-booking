from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.config import settings, validate_runtime_security
from app.database import SCHEMA_REVISION, async_session, current_schema_revision, database_ready, init_db
from app.models import Notification, NotificationStatus, SystemSetting, local_now
from app.observability import configure_logging, log_event, request_context_middleware, request_id_context
from app.routers import admin, auth, media, notifications, reservations, rooms


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    validate_runtime_security()
    await init_db()
    yield


app = FastAPI(title="笃学书院空间预约系统", version="2.0.0", lifespan=lifespan)
app.middleware("http")(request_context_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(media.router)
app.include_router(media.public_router)


def _error_payload(code: str, message: str, details=None) -> dict:
    return {
        "code": code,
        "message": message,
        "details": details,
        "request_id": request_id_context.get(),
        "detail": details if details is not None else message,
    }


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(_error_payload(f"HTTP_{exc.status_code}", message, exc.detail)),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(_error_payload("VALIDATION_ERROR", "请求参数校验失败", exc.errors())),
    )


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    log_event("unhandled_error", error_type=exc.__class__.__name__)
    return JSONResponse(
        status_code=500,
        content=_error_payload("INTERNAL_ERROR", "服务器内部错误"),
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": app.version}


@app.get("/api/ready")
async def readiness():
    db_ok, db_error = await database_ready()
    current_revision = await current_schema_revision() if db_ok else None
    schema_ok = not settings.is_production or current_revision == SCHEMA_REVISION
    worker_ok = True
    worker_heartbeat = None
    pending_outbox = None
    if db_ok:
        async with async_session() as db:
            heartbeat = await db.get(SystemSetting, "worker_last_success_at")
            worker_heartbeat = heartbeat.value if heartbeat else None
            pending_outbox = int(await db.scalar(select(func.count(Notification.id)).where(
                Notification.status == NotificationStatus.pending
            )) or 0)
    if settings.REQUIRE_WORKER_HEARTBEAT:
        try:
            heartbeat_at = datetime.fromisoformat(str(worker_heartbeat))
            worker_ok = (local_now() - heartbeat_at).total_seconds() <= settings.WORKER_HEARTBEAT_MAX_AGE_SECONDS
        except (TypeError, ValueError):
            worker_ok = False
    ready = db_ok and schema_ok and worker_ok
    body = {
        "status": "ready" if ready else "not_ready",
        "database": "ok" if db_ok else db_error,
        "schema": {"current": current_revision, "required": SCHEMA_REVISION, "ok": schema_ok},
        "worker": {"required": settings.REQUIRE_WORKER_HEARTBEAT, "last_success_at": worker_heartbeat, "ok": worker_ok},
        "outbox_pending": pending_outbox,
        "version": app.version,
    }
    return JSONResponse(status_code=200 if ready else 503, content=body)
