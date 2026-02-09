"""
Application configuration settings
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    app_name: str = "JobSeeker"
    app_version: str = "1.0.0"
    database_url: str = "sqlite:///./jobseeker.db"
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    upload_dir: str = "uploads/resumes"
    openai_api_key: str = ""  # Set in .env for resume extraction
    
    class Config:
        env_file = ".env"


settings = Settings()
