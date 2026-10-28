from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("APP_ENV", "development")
    database_path: Path = Path(os.getenv("DATABASE_PATH", ROOT_DIR / "data" / "converter.db"))
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", ROOT_DIR / "storage"))
    log_dir: Path = Path(os.getenv("LOG_DIR", ROOT_DIR / "logs"))
    max_file_bytes: int = int(os.getenv("MAX_FILE_BYTES", 250 * 1024 * 1024))
    max_files_per_task: int = int(os.getenv("MAX_FILES_PER_TASK", 2))
    max_active_users: int = int(os.getenv("MAX_ACTIVE_USERS", 10))
    active_window_minutes: int = int(os.getenv("ACTIVE_WINDOW_MINUTES", 15))
    otp_minutes: int = int(os.getenv("OTP_MINUTES", 10))
    otp_max_attempts: int = int(os.getenv("OTP_MAX_ATTEMPTS", 5))
    otp_request_window_minutes: int = int(os.getenv("OTP_REQUEST_WINDOW_MINUTES", 15))
    otp_requests_per_window: int = int(os.getenv("OTP_REQUESTS_PER_WINDOW", 5))
    session_days: int = int(os.getenv("SESSION_DAYS", 30))
    retention_minutes: int = int(os.getenv("RETENTION_MINUTES", 60))
    conversion_timeout_seconds: int = int(os.getenv("CONVERSION_TIMEOUT_SECONDS", 600))
    conversion_cpu_seconds: int = int(os.getenv("CONVERSION_CPU_SECONDS", 540))
    converter_memory_mb: int = int(os.getenv("CONVERTER_MEMORY_MB", 512))
    max_conversions: int = int(os.getenv("MAX_CONVERSIONS", 2))
    secret_key: str = os.getenv("SECRET_KEY", "change-this-development-secret-before-production")
    cookie_secure: bool = _bool("COOKIE_SECURE", False)
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", 587))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_starttls: bool = _bool("SMTP_STARTTLS", True)
    ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin: str = os.getenv("FFPROBE_BIN", "ffprobe")
    admin_emails: tuple[str, ...] = tuple(
        item.strip().lower() for item in os.getenv("ADMIN_EMAILS", "").split(",") if item.strip()
    )

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


settings = Settings()
