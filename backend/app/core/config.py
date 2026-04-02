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
    admin_email: str = ""  # Optional: auto-promote this email as admin (e.g. superadmin@gmail.com)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    google_scopes: list[str] = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar",
    ]
    encryption_key: str = "your-encryption-key-for-tokens"  # Fernet key

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

    # ── LLM provider ──────────────────────────────────────────────────────────
    # Set AI_PROVIDER to one of: gemini | gpt | claude | mistral
    ai_provider: str = "gpt"

    # Gemini / Vertex AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    use_vertex_ai: bool = False          # True → authenticate via ADC (no API key needed)
    vertex_project_id: str = ""          # GCP project ID for Vertex AI
    vertex_location: str = "us-central1" # Vertex AI region

    # OpenAI GPT
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Anthropic Claude
    claude_api_key: str = ""
    claude_model: str = "claude-opus-4-6"

    # Mistral
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"

    # Razorpay payment gateway
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Gmail Pub/Sub push notifications
    gmail_push_topic: str = ""  # e.g. "projects/my-project/topics/gmail-push"

    # Gmail pre-filter query — only fetch threads that look job-related
    gmail_search_query: str = (
        "subject:(application OR interview OR offer OR rejected OR shortlisted "
        "OR \"next steps\" OR \"moving forward\" OR assessment OR \"hiring team\" "
        "OR \"job offer\" OR \"thank you for applying\")"
    )

    # Scheduler defaults
    default_sync_days: int = 7   # Look-back window for scheduled incremental sync
    ghosted_days: int = 21       # Days of inactivity before marking as ghosted

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
