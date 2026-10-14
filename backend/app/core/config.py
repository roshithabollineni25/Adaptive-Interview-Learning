from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Adaptive Interview Intelligence"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    FRONTEND_URL: Optional[str] = None

    @property
    def frontend_origin(self) -> str:
        if self.FRONTEND_URL and self.FRONTEND_URL.strip():
            return self.FRONTEND_URL.rstrip('/')
        # When running on Render or in production environment, use the deployed static site URL
        import os
        if os.getenv("RENDER") or self.ENVIRONMENT == "production":
            return "https://adaptive-interview-frontend-b2ol.onrender.com"
        return "http://127.0.0.1:5173"

    # Database configuration: defaults to SQLite for local portable dev if PostgreSQL not reachable
    # When PostgreSQL is active, set DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
    DATABASE_URL: str = "sqlite:///./adaptive_interview.db"

    # Security
    SECRET_KEY: str = "adaptive-interview-secret-key-development-minimum-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Email Service (SMTP)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "interviews@adaptiveinterview.io"
    SMTP_ENABLED: bool = False

    # LLM Settings
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Transactional Email — Brevo HTTPS API
    BREVO_API_KEY: str = ""
    BREVO_FROM_EMAIL: str = ""
    # Interview engine bounds (adaptive stopping policy: between MIN and MAX questions based on competency coverage)
    MIN_QUESTIONS_PER_SESSION: int = 4
    MAX_QUESTIONS_PER_SESSION: int = 8
    MAX_RECOVERY_ATTEMPTS: int = 2

    # Time window configuration: early access tolerance (minutes before schedule) and duration window (minutes after schedule)
    INTERVIEW_EARLY_ACCESS_MINUTES: int = 15
    INTERVIEW_WINDOW_MINUTES: int = 90

    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
