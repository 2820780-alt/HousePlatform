from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://platform:platform_secret@localhost:5432/buildplatform"
    DATABASE_URL_SYNC: str = "postgresql://platform:platform_secret@localhost:5432/buildplatform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

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
    ENABLE_MODULE3_DEMO_USERS: bool = False

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    TEMP_UPLOAD_DIR: str = "/tmp/uploads"

    # Module 01 Material Hub MVP collection region. Override in .env to add
    # regions without changing business logic.
    MATERIAL_HUB_ACTIVE_REGION_LABEL: str = "Краснодарский край"
    MATERIAL_HUB_ACTIVE_REGION_CODE: str = "RU-KDA"
    MATERIAL_HUB_SOURCE_REGION_ID: Optional[str] = None
    MATERIAL_HUB_SOURCE_CITY_ID: Optional[str] = None
    MATERIAL_HUB_DELIVERY_ZONE_ID: Optional[str] = None

    # Module 01 REF defaults to legacy. Decisions 034-038 additionally allow
    # validation, diagnostics and approved admin-only ref1_read/ref2_read/ref3_read modes.
    MODULE1_REF_RUNTIME_MODE: str = "legacy"
    MODULE1_REF_ARTIFACT_SET_ID: str = "ref-runtime-v1-122079b1c558fefc"
    MODULE1_REF_APPROVAL_ID: str = "ref1-read-v1-1a15fed6ebdd"
    MODULE1_REF2_APPROVAL_ID: str = "ref2-read-v1-1a15fed6ebdd"
    MODULE1_REF3_APPROVAL_ID: str = "ref3-read-v1-1a15fed6ebdd"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
