"""
Application configuration settings.
Loads from .env file first (overrides shell env for local dev), then pydantic reads from environment.
Production: set env vars in the platform (Docker, K8s, etc.); .env is optional.

All backend-related configs and constants are centralized here.
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path: backend/.env (absolute path, works regardless of cwd)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = (_BASE_DIR / ".env").resolve()

# Load .env into environment BEFORE pydantic reads. override=True ensures .env
# values override any shell env (e.g. bad AWS_ACCESS_KEY_ID from elsewhere).
# When .env doesn't exist (prod), this is a no-op; platform env vars are used.
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    """Application settings. Source: env vars (after dotenv load)."""

    # App
    app_name: str = "JobSeeker"
    app_version: str = "1.0.0"
    port: int = 8001

    # Database
    database_url: str = "sqlite:///./jobseeker.db"

    # Auth
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Upload & storage
    upload_dir: str = "uploads/resumes"

    # Redis
    redis_url: str = ""

    # Cache TTLs (seconds)
    dashboard_summary_cache_ttl: int = 120
    autofill_context_cache_ttl: int = 300
    form_field_cache_ttl: int = 300
    form_field_cache_max_entries: int = 64
    tailor_context_ttl: int = 300
    analysis_cache_ttl: int = 1800
    analysis_cache_max_entries: int = 1000
    job_description_cache_ttl: int = 3600
    job_description_cache_max_entries: int = 500
    keyword_extraction_ttl: int = 1800
    keyword_extraction_max_entries: int = 500

    # Dashboard defaults
    dashboard_default_limit: int = 5
    dashboard_default_days: int = 7

    # HTTP / network
    http_request_timeout: int = 30

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-southeast-1"
    aws_bucket_name: str = "recruitementfiles"
    s3_presigned_url_expiration: int = 3600
    s3_key_prefix: str = "user-profiles"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Razorpay payment gateway
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


# --- Constants (non-env, business config) ---

# Payment: plan_id -> amount in paise (1 INR = 100 paise)
PLAN_AMOUNTS: dict[str, int] = {
    "daily": 9900,   # ₹99
    "weekly": 39900,  # ₹399
    "monthly": 99900, # ₹999
}

# Job description scraper
FRAME_SEP: str = "<!--FRAME_SEP-->"
MAX_HTML_BYTES: int = 2_000_000

# PDF generator
PDF_DEFAULT_TITLE: str = "Resume"
PDF_LINE_HEIGHT: int = 14
PDF_FONT_SIZE_TITLE: int = 14
PDF_FONT_SIZE_BODY: int = 10
PDF_MAX_LINE_CHARS: int = 120
