import math
import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import FileNotFoundAppException
from app.core.logging import logger
from app.db.repositories import FeatureRepository, FileRepository
from app.schemas.common import PaginationMeta
from app.schemas.file import FileInfoResponse, FileUploadResponse
from app.schemas.measurement import (
    CalculationExplanation,
    MeasurementItem,
    MeasurementsListResponse,
)
from app.schemas.summary import (
    FileSummaryMeta,
    FileSummaryResponse,
    MeasurementsAggregate,
    ProcessingMeta,
    QualityReport,
)
from app.services.processing_service import processing_service
from app.utils.file_validation import (
    safe_extract_zip,
    validate_content_signature,
    validate_file_extension,
    validate_file_size,
)


class FileService:
    """Service managing uploaded geospatial files, coordinating extraction, storage, and retrieval."""

    def __init__(self, db: Session):
        self.db = db
        self.file_repo = FileRepository(db)
        self.feature_repo = FeatureRepository(db)

    def handle_upload(
        self,
        file: UploadFile,
        background_tasks: BackgroundTasks | None = None,
    ) -> FileUploadResponse:
        """Validates, stores, extracts, and initiates processing for an uploaded file."""
        filename = file.filename or "unknown"
        file_type = validate_file_extension(filename)
        file_size = validate_file_size(file)
        validate_content_signature(file.file, file_type)

        # Ensure base upload storage directory exists outside source tree
        settings.UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

        file_id = uuid.uuid4()
        storage_subdir = settings.UPLOAD_DIRECTORY / str(file_id)
        storage_subdir.mkdir(parents=True, exist_ok=True)

        stored_file_path = storage_subdir / filename
        with open(stored_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Saved uploaded file {filename} ({file_size} bytes) to {stored_file_path}")

        # If shapefile zip, extract safely
        target_path_to_process = stored_file_path
        if file_type == "shapefile":
            extraction_dir = storage_subdir / "extracted"
            extraction_dir.mkdir(parents=True, exist_ok=True)
            shp_path = safe_extract_zip(stored_file_path, extraction_dir)
            target_path_to_process = shp_path

        # Create FileRecord in DB
        self.file_repo.create(
            id=file_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            status="UPLOADED",
        )

        # Trigger processing: synchronous vs background
        if settings.SYNC_PROCESSING or background_tasks is None:
            processing_service.process_file(
                db=self.db,
                file_id=file_id,
                file_path=target_path_to_process,
                file_type=file_type,
            )
            # Reload to return up-to-date status
            refreshed = self.file_repo.get_by_id(file_id)
            return FileUploadResponse(
                id=file_id,
                filename=filename,
                file_type=file_type,
                file_size=file_size,
                status=refreshed.status if refreshed else "COMPLETED",
                message="File uploaded and processed successfully.",
            )
        else:
            # Process in background task
            background_tasks.add_task(
                self._background_process,
                file_id=file_id,
                file_path=target_path_to_process,
                file_type=file_type,
            )
            return FileUploadResponse(
                id=file_id,
                filename=filename,
                file_type=file_type,
                file_size=file_size,
                status="PROCESSING",
                message="File uploaded successfully. Processing in background.",
            )

    def _background_process(self, file_id: uuid.UUID, file_path: Path, file_type: str) -> None:
        """Helper to invoke processing service within a clean session in background."""
        from app.db.database import SessionLocal

        with SessionLocal() as session:
            processing_service.process_file(
                db=session,
                file_id=file_id,
                file_path=file_path,
                file_type=file_type,
            )

    def get_file_info(self, file_id: uuid.UUID) -> FileInfoResponse:
        """Retrieves metadata and status for a given file ID."""
        record = self.file_repo.get_by_id(file_id)
        if not record:
            raise FileNotFoundAppException(f"File with ID '{file_id}' was not found.")

        return FileInfoResponse(
            id=record.id,
            filename=record.filename,
            file_type=record.file_type,
            file_size=record.file_size,
            status=record.status,
            feature_count=record.feature_count,
            crs=record.source_crs,
            source_crs=record.source_crs,
            measurement_crs=record.measurement_crs,
            processing_started_at=record.processing_started_at,
            processing_completed_at=record.processing_completed_at,
            processing_duration_ms=record.processing_duration_ms,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def get_measurements_paginated(
        self,
        file_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        status_filter: str | None = None,
    ) -> MeasurementsListResponse:
        """Retrieves paginated measurement results for features belonging to a file."""
        record = self.file_repo.get_by_id(file_id)
        if not record:
            raise FileNotFoundAppException(f"File with ID '{file_id}' was not found.")

        total_records = self.feature_repo.count_by_file_id(file_id, status_filter=status_filter)
        total_pages = max(1, math.ceil(total_records / page_size)) if total_records > 0 else 1
        skip = (page - 1) * page_size

        feature_records = self.feature_repo.get_by_file_id(
            file_id=file_id,
            skip=skip,
            limit=page_size,
            status_filter=status_filter,
        )

        results: list[MeasurementItem] = []
        for feat in feature_records:
            calc_meta = None
            if feat.calculation_metadata:
                calc_meta = CalculationExplanation(
                    method=feat.calculation_metadata.get("method", "unknown"),
                    projected_crs=feat.calculation_metadata.get("projected_crs"),
                    formula_description=feat.calculation_metadata.get("formula_description"),
                    repaired_geometry=feat.calculation_metadata.get("repaired_geometry", False),
                )

            results.append(
                MeasurementItem(
                    feature_id=feat.feature_index,
                    geometry_type=feat.geometry_type,
                    measurement_type=feat.measurement_type,
                    value=feat.measurement_value,
                    unit=feat.measurement_unit,
                    status=feat.processing_status,
                    message=feat.error_message,
                    source_crs=record.source_crs,
                    measurement_crs=feat.measurement_crs,
                    calculation=calc_meta,
                    properties=feat.properties or {},
                )
            )

        pagination = PaginationMeta(
            total_records=total_records,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

        return MeasurementsListResponse(
            file_id=file_id,
            results=results,
            pagination=pagination,
        )

    def get_file_summary(self, file_id: uuid.UUID) -> FileSummaryResponse:
        """Generates the Innovation #2 Data Quality and Processing Health Report."""
        record = self.file_repo.get_by_id(file_id)
        if not record:
            raise FileNotFoundAppException(f"File with ID '{file_id}' was not found.")

        stats = record.summary_stats or {}
        quality_data = stats.get("quality", {})
        geometry_summary = stats.get("geometry_summary", {})

        file_meta = FileSummaryMeta(
            id=record.id,
            name=record.filename,
            crs=record.source_crs,
            measurement_crs=record.measurement_crs,
            file_type=record.file_type,
            file_size_bytes=record.file_size,
        )

        proc_meta = ProcessingMeta(
            status=record.status,
            duration_ms=record.processing_duration_ms,
            started_at=record.processing_started_at,
            completed_at=record.processing_completed_at,
            error_message=record.error_message,
        )

        qual_report = QualityReport(
            total_features=quality_data.get("total_features", record.feature_count),
            valid_features=quality_data.get("valid_features", 0),
            repaired_features=quality_data.get("repaired_features", 0),
            invalid_features=quality_data.get("invalid_features", 0),
            unsupported_features=quality_data.get("unsupported_features", 0),
            point_features_not_required=quality_data.get("point_features_not_required", 0),
        )

        meas_aggregate = MeasurementsAggregate(
            total_area_m2=stats.get("total_area_m2", 0.0),
            total_length_m=stats.get("total_length_m", 0.0),
            polygon_count=geometry_summary.get("Polygon", 0)
            + geometry_summary.get("MultiPolygon", 0),
            linestring_count=geometry_summary.get("LineString", 0)
            + geometry_summary.get("MultiLineString", 0),
        )

        return FileSummaryResponse(
            file=file_meta,
            processing=proc_meta,
            quality=qual_report,
            geometry_breakdown=geometry_summary,
            measurements=meas_aggregate,
        )
