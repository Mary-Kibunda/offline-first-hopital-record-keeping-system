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

    #CORS settings for the offline-first hospital record keeping system
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"

settings = Settings()
