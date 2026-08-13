from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./shuyuan.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"
    UPLOAD_DIR: str = "./uploads"
    PRIVATE_UPLOAD_DIR: str = "./private_uploads"
    MEDIA_RETENTION_DAYS: int = 90
    MAX_UPLOAD_MB: int = 8
    ENABLE_SCHEDULER: bool = True
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_TEMPLATE_SUBMITTED: str = ""
    WECHAT_TEMPLATE_REVIEW: str = ""
    WECHAT_TEMPLATE_REMINDER: str = ""
    WECHAT_TEMPLATE_RESTRICTION: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]


settings = Settings()


def validate_runtime_security(runtime: Settings = settings) -> None:
    """Refuse production-like startup with a known or weak JWT signing key."""
    environment = runtime.APP_ENV.strip().lower()
    local_sqlite = runtime.DATABASE_URL.startswith("sqlite")
    if environment in {"development", "test"} and local_sqlite:
        return
    secret = runtime.SECRET_KEY.strip()
    if secret == "change-me-in-production" or len(secret) < 32:
        raise RuntimeError("生产环境 SECRET_KEY 必须是至少32字符的强随机密钥")


DEFAULT_RUNTIME_CONFIG = {
    "open_hour": 8,
    "close_hour": 22,
    "slot_minutes": 30,
    "max_minutes_per_day": 240,
    "advance_days": 7,
    "cancel_deadline_minutes": 30,
    "checkin_grace_minutes": 15,
    "auto_approval_time": "23:00",
    "reminder_minutes": 30,
    "temporary_ban_days": 1,
    "violation_threshold": 3,
    "violation_ban_days": 30,
    "music_a103_start_hour": 15,
    "music_a103_end_hour": 21,
}
