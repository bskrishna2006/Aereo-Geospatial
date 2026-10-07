import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    message: str | None = None


class FileInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    feature_count: int
    crs: str | None = None
    source_crs: str | None = None
    measurement_crs: str | None = None
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    processing_duration_ms: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
