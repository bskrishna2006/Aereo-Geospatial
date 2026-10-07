from dataclasses import dataclass
from typing import Any

from shapely.geometry.base import BaseGeometry

from app.core.config import settings
from app.core.logging import logger
from app.parsers.base import ParsedFeature
from app.services.crs_service import crs_service
from app.utils.geometry_utils import validate_and_repair_geometry


@dataclass
class MeasurementResult:
    feature_index: int
    geometry_type: str
    measurement_type: str | None
    measurement_value: float | None
    measurement_unit: str | None
    measurement_crs: str | None
    processing_status: str  # SUCCESS, NOT_REQUIRED, REPAIRED, UNSUPPORTED, FAILED
    error_message: str | None
    calculation_metadata: dict[str, Any] | None
    validated_geometry: BaseGeometry | None


class MeasurementService:
    """Service responsible for calculating geometric measurements (Area, Length)
    with strict metric CRS projection and validation.
    """

    def process_feature(
        self,
        feature: ParsedFeature,
        dataset_crs: str | None,
    ) -> MeasurementResult:
        """Processes a single feature, validates geometry, selects projected CRS,
        and computes accurate metric measurements.
        """
        source_crs = feature.source_crs or dataset_crs
        geom = feature.geometry

        # Check for missing geometry or parser errors
        if geom is None:
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="FAILED",
                error_message=feature.error_message or "Feature contains no geometry",
                calculation_metadata=None,
                validated_geometry=None,
            )

        # Validate and attempt repair if invalid
        valid_geom, was_repaired, repair_err = validate_and_repair_geometry(geom)

        if valid_geom is None or valid_geom.is_empty:
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom.geom_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="FAILED",
                error_message=repair_err or "Geometry is empty or null",
                calculation_metadata=None,
                validated_geometry=None,
            )

        if not valid_geom.is_valid:
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=valid_geom.geom_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="FAILED",
                error_message=repair_err or "Invalid geometry could not be safely repaired",
                calculation_metadata=None,
                validated_geometry=None,
            )

        geom_type = valid_geom.geom_type

        # Check 1: Point / MultiPoint
        if geom_type in ("Point", "MultiPoint"):
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="NOT_REQUIRED",
                error_message="Point geometries have 0 dimensions; no area or length measurement is required.",
                calculation_metadata=None,
                validated_geometry=valid_geom,
            )

        # Check 2: Missing CRS
        if not source_crs:
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="FAILED",
                error_message="Source CRS is missing; cannot project geometry to calculate metric measurements.",
                calculation_metadata=None,
                validated_geometry=valid_geom,
            )

        # Check 3: Unsupported Geometries (e.g. GeometryCollection)
        if geom_type not in ("Polygon", "MultiPolygon", "LineString", "MultiLineString"):
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="UNSUPPORTED",
                error_message=f"Measurement is not supported for geometry type {geom_type}.",
                calculation_metadata=None,
                validated_geometry=valid_geom,
            )

        # Determine metric projected CRS and reproject geometry
        try:
            target_crs = crs_service.determine_measurement_crs(valid_geom, source_crs)
            projected_geom = crs_service.transform_geometry(valid_geom, source_crs, target_crs)
        except Exception as e:
            logger.error(f"CRS reprojection failed for feature {feature.feature_index}: {e}")
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom_type,
                measurement_type=None,
                measurement_value=None,
                measurement_unit=None,
                measurement_crs=None,
                processing_status="FAILED",
                error_message=f"Reprojection error: {e}",
                calculation_metadata=None,
                validated_geometry=valid_geom,
            )

        # Calculate measurements
        precision = settings.DEFAULT_DECIMAL_PRECISION

        if geom_type in ("Polygon", "MultiPolygon"):
            val = round(float(projected_geom.area), precision)
            status = "REPAIRED" if was_repaired else "SUCCESS"
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom_type,
                measurement_type="area",
                measurement_value=val,
                measurement_unit="m²",
                measurement_crs=target_crs,
                processing_status=status,
                error_message=None,
                calculation_metadata={
                    "method": "projected_planar_area",
                    "projected_crs": target_crs,
                    "formula_description": (
                        f"Projected from {source_crs} to {target_crs}. "
                        "Planar area computed via surveyor formula / Green's theorem."
                    ),
                    "repaired_geometry": was_repaired,
                },
                validated_geometry=valid_geom,
            )

        elif geom_type in ("LineString", "MultiLineString"):
            val = round(float(projected_geom.length), precision)
            status = "REPAIRED" if was_repaired else "SUCCESS"
            return MeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=geom_type,
                measurement_type="length",
                measurement_value=val,
                measurement_unit="m",
                measurement_crs=target_crs,
                processing_status=status,
                error_message=None,
                calculation_metadata={
                    "method": "projected_planar_length",
                    "projected_crs": target_crs,
                    "formula_description": (
                        f"Projected from {source_crs} to {target_crs}. "
                        "Planar Euclidean line length computed on projected coordinates."
                    ),
                    "repaired_geometry": was_repaired,
                },
                validated_geometry=valid_geom,
            )

        # Fallback (should not be reached)
        return MeasurementResult(
            feature_index=feature.feature_index,
            geometry_type=geom_type,
            measurement_type=None,
            measurement_value=None,
            measurement_unit=None,
            measurement_crs=None,
            processing_status="UNSUPPORTED",
            error_message=f"Measurement not supported for {geom_type}",
            calculation_metadata=None,
            validated_geometry=valid_geom,
        )


measurement_service = MeasurementService()
