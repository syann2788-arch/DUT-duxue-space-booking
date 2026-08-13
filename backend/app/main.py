from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validate_runtime_security
from app.database import init_db
from app.routers import admin, auth, media, notifications, reservations, rooms
from app.tasks import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_security()
    await init_db()
    if settings.ENABLE_SCHEDULER:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="笃学书院空间预约系统", version="2.0.0", lifespan=lifespan)
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": app.version}
