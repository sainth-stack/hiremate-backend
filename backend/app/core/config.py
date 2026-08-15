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
    frontend_url: str = "https://opsbrainai.com"

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
    google_redirect_uri: str = "https://opsbrainai.com/api/auth/google/callback"
    google_scopes: list[str] = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/gmail.modify",   # Required for Gmail Watch API (push notifications)
        "https://www.googleapis.com/auth/gmail.readonly", # Required for reading/searching emails
        "https://www.googleapis.com/auth/calendar",       # Required for calendar event creation
        # "https://mail.google.com/"                      # Only needed for Gmail MCP API (Developer Preview — disabled)
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

    # Gmail MCP server (Google's remote MCP endpoint for Gmail — Developer Preview)
    # Leave empty to use direct Gmail API calls (default / always works).
    # Set to the URL below to route chat agent tool calls through Google's MCP server:
    # GMAIL_MCP_SERVER_URL=https://gmailmcp.googleapis.com/mcp/v1
    gmail_mcp_server_url: str = ""

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

    # Background workers (Celery + optional in-process APScheduler fallback)
    enable_in_process_scheduler: bool = False  # True = APScheduler inside uvicorn (dev only)
    enable_job_scheduler: bool = True
    job_ingestion_interval_hours: int = 2
    celery_broker_url: str = ""  # Defaults to redis_url when empty
    celery_result_backend: str = ""

    # Job recommendations (corpus sort=recommended)
    recommended_sort_max_jobs: int = 500

    # Logging
    log_level: str = "INFO"

    # Job corpus ingestion (scheduler / internal)
    ingest_secret: str = ""  # Required for POST /api/v1/jobs/ingest/* when set; empty = disabled in dev only
    portals_config: str = ""  # Path to portals.yml (default: discover data/portals.example.yml upward)
    job_sources_config: str = ""  # Optional legacy JSON (e.g. job_sources.json); public_urls merged after YAML
    ingest_deep_enrich_enabled: bool = False  # Also set settings.deep_enrich_enabled in portals YAML
    ingest_redis_lock_enabled: bool = True  # Per-route lock when redis_url set; fail-open without Redis
    ingest_lock_ttl_sec: int = 1800  # Redis lock TTL (max hold if process dies before release)
    # Clear ingest:lock:* on process start so a crashed/killed server does not block until TTL.
    # Set false if you run multiple app instances that could ingest concurrently (same Redis).
    ingest_clear_locks_on_startup: bool = True

    # SMTP (optional — interview invitation emails; logs link if unset)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


# Job description scraper
FRAME_SEP: str = "<!--FRAME_SEP-->"
MAX_HTML_BYTES: int = 2_000_000

# PDF generator
PDF_DEFAULT_TITLE: str = "Resume"
PDF_LINE_HEIGHT: int = 14
PDF_FONT_SIZE_TITLE: int = 14
PDF_FONT_SIZE_BODY: int = 10
PDF_MAX_LINE_CHARS: int = 100
# AI Pricing (USD per 1M tokens)
AI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 5.00, "completion": 15.00},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-2.0-flash": {"prompt": 0.10, "completion": 0.40},
    "claude-3-5-sonnet-20240620": {"prompt": 3.00, "completion": 15.00},
    "claude-3-opus-20240229": {"prompt": 15.00, "completion": 75.00},
    "mistral-large-latest": {"prompt": 2.00, "completion": 6.00},
}
