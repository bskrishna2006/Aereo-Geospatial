import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status

from app.api.deps import get_file_service
from app.schemas.common import ErrorResponse
from app.schemas.file import FileInfoResponse, FileUploadResponse
from app.schemas.summary import FileSummaryResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process geospatial file",
    description=(
        "Accepts a .kml file or a .zip containing an ESRI Shapefile bundle (.shp, .shx, .dbf, .prj). "
        "Performs security checks (Zip Slip, zip bomb, extension and content signature validation), "
        "parses features, reprojects from geographic coordinates (EPSG:4326) into metric projected CRS (e.g. UTM), "
        "and computes area for Polygons and length for LineStrings."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid file, unsupported extension, or corrupted archive",
        },
        422: {
            "model": ErrorResponse,
            "description": "Unprocessable geospatial data or invalid geometry",
        },
    },
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.kml or .zip shapefile bundle)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    file_service: FileService = Depends(get_file_service),
) -> FileUploadResponse:
    """Uploads a geospatial file and initiates metric measurement processing."""
    return file_service.handle_upload(file=file, background_tasks=background_tasks)


@router.get(
    "/{id}/",
    response_model=FileInfoResponse,
    summary="Get file details and processing status",
    description="Retrieves metadata, status, detected CRS, and high-level execution timestamps for an uploaded file.",
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
async def get_file_info(
    id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
) -> FileInfoResponse:
    """Retrieves file details by file UUID."""
    return file_service.get_file_info(file_id=id)


@router.get(
    "/{id}/summary/",
    response_model=FileSummaryResponse,
    summary="Get processing health and quality report (Innovation #2)",
    description=(
        "Provides an in-depth data quality audit and processing summary including valid vs invalid "
        "feature counts, repair status, geometry breakdowns, and cumulative aggregate measurements."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
async def get_file_summary(
    id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
) -> FileSummaryResponse:
    """Retrieves data quality and processing summary metrics."""
    return file_service.get_file_summary(file_id=id)
