import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logging import logger
from app.db.repositories import FeatureRepository, FileRepository
from app.parsers.base import GeoFileParser
from app.parsers.kml_parser import KMLParser
from app.parsers.shapefile_parser import ShapefileParser
from app.services.measurement_service import measurement_service
from app.utils.geometry_utils import geometry_to_geojson


def get_parser_for_type(file_type: str) -> GeoFileParser:
    """Factory function returning the appropriate parser for a given file type."""
    if file_type == "kml":
        return KMLParser()
    elif file_type == "shapefile":
        return ShapefileParser()
    else:
        raise AppException(
            message=f"No parser implemented for file type: {file_type}",
            code="UNSUPPORTED_PARSER",
        )


class ProcessingService:
    """Orchestrates parsing, geometry validation, CRS projection, measurement calculation,
    quality analysis, and persistence for geospatial files.
    """

    def process_file(
        self,
        db: Session,
        file_id: uuid.UUID,
        file_path: Path,
        file_type: str,
    ) -> None:
        """Processes an uploaded geospatial file synchronously or asynchronously."""
        file_repo = FileRepository(db)
        feature_repo = FeatureRepository(db)

        file_record = file_repo.get_by_id(file_id)
        if not file_record:
            logger.error(f"Cannot process non-existent file record {file_id}")
            return

        start_time = time.perf_counter()
        started_at = datetime.now(UTC)

        file_repo.update(
            file_record,
            status="PROCESSING",
            processing_started_at=started_at,
        )

        try:
            logger.info(f"Starting processing for file {file_id} ({file_record.filename})")
            parser = get_parser_for_type(file_type)
            parsed_dataset = parser.parse(file_path)

            source_crs = parsed_dataset.detected_crs
            detected_measurement_crs: str | None = None

            features_to_insert: list[dict[str, Any]] = []

            # Counters and accumulators for Innovation #1 & #2
            geom_breakdown: dict[str, int] = {}
            valid_count = 0
            repaired_count = 0
            invalid_count = 0
            unsupported_count = 0
            point_count = 0
            total_area_m2 = 0.0
            total_length_m = 0.0

            for parsed_feat in parsed_dataset.features:
                gtype = parsed_feat.geometry_type
                geom_breakdown[gtype] = geom_breakdown.get(gtype, 0) + 1

                res = measurement_service.process_feature(parsed_feat, source_crs)

                if res.measurement_crs and not detected_measurement_crs:
                    detected_measurement_crs = res.measurement_crs

                # Statistics updates
                if res.processing_status == "SUCCESS":
                    valid_count += 1
                elif res.processing_status == "REPAIRED":
                    valid_count += 1
                    repaired_count += 1
                elif res.processing_status == "NOT_REQUIRED":
                    point_count += 1
                elif res.processing_status == "UNSUPPORTED":
                    unsupported_count += 1
                elif res.processing_status == "FAILED":
                    invalid_count += 1

                if res.measurement_type == "area" and res.measurement_value is not None:
                    total_area_m2 += res.measurement_value
                elif res.measurement_type == "length" and res.measurement_value is not None:
                    total_length_m += res.measurement_value

                # GeoJSON serialization of geometry
                geom_geojson = geometry_to_geojson(res.validated_geometry or parsed_feat.geometry)

                feature_dict = {
                    "id": uuid.uuid4(),
                    "file_id": file_id,
                    "feature_index": parsed_feat.feature_index,
                    "geometry_type": res.geometry_type,
                    "properties": parsed_feat.properties,
                    "source_geometry": geom_geojson,
                    "measurement_type": res.measurement_type,
                    "measurement_value": res.measurement_value,
                    "measurement_unit": res.measurement_unit,
                    "measurement_crs": res.measurement_crs,
                    "calculation_metadata": res.calculation_metadata,
                    "processing_status": res.processing_status,
                    "error_message": res.error_message,
                }
                features_to_insert.append(feature_dict)

            # Bulk persist all features
            feature_repo.bulk_create(features_to_insert)

            # Elapsed time
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            completed_at = datetime.now(UTC)

            # Determine final file status
            if invalid_count > 0 or unsupported_count > 0:
                if valid_count == 0 and point_count == 0:
                    final_status = "FAILED"
                else:
                    final_status = "COMPLETED_WITH_ERRORS"
            else:
                final_status = "COMPLETED"

            # Structure processing and quality summary stats
            summary_stats = {
                "feature_count": len(parsed_dataset.features),
                "geometry_summary": geom_breakdown,
                "total_area_m2": round(total_area_m2, 4),
                "total_length_m": round(total_length_m, 4),
                "processing_time_ms": duration_ms,
                "quality": {
                    "total_features": len(parsed_dataset.features),
                    "valid_features": valid_count,
                    "repaired_features": repaired_count,
                    "invalid_features": invalid_count,
                    "unsupported_features": unsupported_count,
                    "point_features_not_required": point_count,
                },
            }

            file_repo.update(
                file_record,
                status=final_status,
                feature_count=len(parsed_dataset.features),
                source_crs=source_crs,
                measurement_crs=detected_measurement_crs,
                processing_completed_at=completed_at,
                processing_duration_ms=duration_ms,
                summary_stats=summary_stats,
            )
            logger.info(
                f"Completed processing file {file_id}: status={final_status}, "
                f"features={len(parsed_dataset.features)}, duration={duration_ms}ms"
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception(f"Fatal error processing file {file_id}: {e}")
            file_repo.update(
                file_record,
                status="FAILED",
                error_message=str(e),
                processing_completed_at=datetime.now(UTC),
                processing_duration_ms=duration_ms,
            )


processing_service = ProcessingService()
