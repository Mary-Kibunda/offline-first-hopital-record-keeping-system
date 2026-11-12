from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    #application settings for the offline-first hospital record keeping system
    PROJECT_NAME: str = "Health Chart"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    #security settings for the offline-first hospital record keeping system
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480, gt=0)

    #debug flag, surfaced from the environment file
    DEBUG: bool = False

    #database settings for the offline-first hospital record keeping system
    DATABASE_URL: str

    #email (SMTP) settings. When SMTP_HOST is empty nothing is sent: the message is
    #logged instead, which is what you want in local development and tests.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True        # STARTTLS on SMTP_PORT (587)
    SMTP_USE_SSL: bool = False       # implicit TLS (usually port 465); wins over SMTP_USE_TLS
    EMAIL_FROM: str = "no-reply@healthchart.local"
    EMAIL_FROM_NAME: str = "Health Chart"

    #password reset: the emailed link points at the frontend's reset form, with the
    #token appended as ?token=...
    FRONTEND_URL: str = "http://localhost:3000"
    PASSWORD_RESET_PATH: str = "/reset-password"
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    #where users sign in, quoted in the welcome email
    LOGIN_PATH: str = "/login"

    #CORS settings for the offline-first hospital record keeping system
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000", "http://localhost:8080"]

    class Config:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"

settings = Settings()
