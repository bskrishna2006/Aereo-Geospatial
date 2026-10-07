import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_file_service
from app.schemas.common import ErrorResponse
from app.schemas.measurement import MeasurementsListResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Measurements"])


@router.get(
    "/{id}/measurements/",
    response_model=MeasurementsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get paginated feature measurements with calculation explanation",
    description=(
        "Retrieves metric measurements (area in m² for Polygons, length in m for LineStrings, null for Points) "
        "along with explainable calculation metadata (Innovation #3) and properties for each feature in the file."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
async def get_file_measurements(
    id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (max 500)"),
    status: str | None = Query(
        None,
        description="Filter by feature processing status: SUCCESS, NOT_REQUIRED, REPAIRED, UNSUPPORTED, FAILED",
    ),
    file_service: FileService = Depends(get_file_service),
) -> MeasurementsListResponse:
    """Retrieves paginated measurement results for features belonging to a file."""
    return file_service.get_measurements_paginated(
        file_id=id,
        page=page,
        page_size=page_size,
        status_filter=status,
    )
