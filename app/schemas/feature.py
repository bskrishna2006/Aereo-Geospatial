import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.measurement import CalculationExplanation


class FeatureDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_id: uuid.UUID
    feature_index: int
    geometry_type: str
    properties: dict[str, Any] | None = None
    source_geometry: dict[str, Any] | None = None
    measurement_type: str | None = None
    measurement_value: float | None = None
    measurement_unit: str | None = None
    measurement_crs: str | None = None
    calculation_metadata: CalculationExplanation | None = None
    processing_status: str
    error_message: str | None = None
