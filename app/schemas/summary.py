import uuid
from datetime import datetime

from pydantic import BaseModel


class FileSummaryMeta(BaseModel):
    id: uuid.UUID
    name: str
    crs: str | None = None
    measurement_crs: str | None = None
    file_type: str
    file_size_bytes: int


class ProcessingMeta(BaseModel):
    status: str
    duration_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class QualityReport(BaseModel):
    total_features: int
    valid_features: int
    repaired_features: int
    invalid_features: int
    unsupported_features: int
    point_features_not_required: int


class MeasurementsAggregate(BaseModel):
    total_area_m2: float
    total_length_m: float
    polygon_count: int
    linestring_count: int


class FileSummaryResponse(BaseModel):
    file: FileSummaryMeta
    processing: ProcessingMeta
    quality: QualityReport
    geometry_breakdown: dict[str, int]
    measurements: MeasurementsAggregate
