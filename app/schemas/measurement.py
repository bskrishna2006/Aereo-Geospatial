import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class CalculationExplanation(BaseModel):
    """Metadata explaining how the measurement was computed (Innovation #3)."""

    method: str = Field(
        ..., description="Calculation method, e.g. projected_planar_area, projected_planar_length"
    )
    projected_crs: str | None = Field(
        None, description="The projected coordinate reference system utilized"
    )
    formula_description: str | None = Field(
        None, description="Detailed explanation of the geometric formula used"
    )
    repaired_geometry: bool = Field(
        False, description="Whether geometry repair was performed prior to calculation"
    )


class MeasurementItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_id: int = Field(
        ..., description="0-indexed identifier of the feature within the source file"
    )
    geometry_type: str = Field(
        ..., description="Geometry type (e.g. Polygon, LineString, Point, etc.)"
    )
    measurement_type: str | None = Field(
        None, description="'area', 'length', or null if not applicable"
    )
    value: float | None = Field(
        None, description="Numerical measurement value rounded to configured precision"
    )
    unit: str | None = Field(None, description="Unit of measurement ('m²', 'm', or null)")
    status: str = Field(
        ..., description="Processing status: SUCCESS, NOT_REQUIRED, REPAIRED, UNSUPPORTED, FAILED"
    )
    message: str | None = Field(None, description="Informative message or error description")
    source_crs: str | None = Field(None, description="Original CRS of the feature geometry")
    measurement_crs: str | None = Field(None, description="Projected CRS used for measurement")
    calculation: CalculationExplanation | None = Field(
        None, description="Explainable measurement calculation details"
    )
    properties: dict[str, Any] | None = Field(
        default_factory=dict, description="Feature attributes from file"
    )


class MeasurementsListResponse(BaseModel):
    file_id: uuid.UUID
    results: list[MeasurementItem]
    pagination: PaginationMeta
