from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./shuyuan.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 8
    ENABLE_SCHEDULER: bool = True
    ALLOW_OPEN_REGISTRATION: bool = True
    BOOTSTRAP_ADMIN_STUDENT_ID: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}


def validate_runtime_settings(current: Settings | None = None) -> None:
    """Reject configurations that would make a non-demo deployment unsafe."""
    current = current or settings
    using_sqlite = current.DATABASE_URL.startswith("sqlite")
    if not using_sqlite and not current.is_production and current.SECRET_KEY == "change-me-in-production":
        raise RuntimeError("非 SQLite 环境禁止使用默认 SECRET_KEY")
    if current.is_production:
        errors: list[str] = []
        if using_sqlite:
            errors.append("生产环境必须使用 PostgreSQL")
        if current.SECRET_KEY == "change-me-in-production" or len(current.SECRET_KEY) < 32:
            errors.append("生产 SECRET_KEY 至少需要 32 个字符")
        if current.ALLOW_OPEN_REGISTRATION:
            errors.append("生产环境必须关闭开放注册并使用校内身份或预导入名册")
        if any(
            origin == "*" or "localhost" in origin or "127.0.0.1" in origin or "example." in origin
            for origin in current.cors_origins
        ):
            errors.append("生产 CORS_ORIGINS 不得包含通配符、本地地址或占位域名")
        if errors:
            raise RuntimeError("；".join(errors))


settings = Settings()


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
