from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import admin, auth, notifications, reservations, rooms
from app.tasks import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
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

upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(admin.router)
app.include_router(notifications.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": app.version}
