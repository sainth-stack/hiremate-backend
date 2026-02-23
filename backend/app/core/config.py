"""
Application configuration settings.
Loads from .env file first (overrides shell env for local dev), then pydantic reads from environment.
Production: set env vars in the platform (Docker, K8s, etc.); .env is optional.
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

    app_name: str = "JobSeeker"
    app_version: str = "1.0.0"
    database_url: str = "sqlite:///./jobseeker.db"
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    upload_dir: str = "uploads/resumes"
    # AWS S3 for resume storage
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-southeast-1"
    aws_bucket_name: str = "recruitementfiles"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    port: int = 8001

    # Razorpay payment gateway
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
