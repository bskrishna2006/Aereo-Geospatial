import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Aereo Geospatial Measurement API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # API
    API_V1_PREFIX: str = "/api"

    # Database
    DATABASE_URL: str = "sqlite:///./geomeasure_db.sqlite3"

    # File Upload & Storage
    # Default upload storage path outside the source tree
    UPLOAD_DIRECTORY: Path = Path(os.getenv("TEMP", "/tmp")) / "aereo_geospatial_uploads"
    MAX_UPLOAD_SIZE_MB: int = 50  # 50 MB
    MAX_UNCOMPRESSED_RATIO: int = 100  # Protect against zip bombs (uncompressed / compressed ratio)

    # Processing mode:
    # If True, POST /api/files/ processes synchronously and immediately returns COMPLETED status.
    # If False, uses FastAPI BackgroundTasks and returns PROCESSING status.
    SYNC_PROCESSING: bool = True

    # Geometry & CRS
    DEFAULT_DECIMAL_PRECISION: int = 4
    ATTEMPT_GEOMETRY_REPAIR: bool = True


settings = Settings()
