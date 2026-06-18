from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://platform:platform_secret@db:5432/buildplatform"
    DATABASE_URL_SYNC: str = "postgresql://platform:platform_secret@db:5432/buildplatform"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-random-secret-key-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # App
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    # Admin seed
    ADMIN_EMAIL: str = "admin@buildplatform.ru"
    ADMIN_PASSWORD: str = "admin123"

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    TEMP_UPLOAD_DIR: str = "/tmp/uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
