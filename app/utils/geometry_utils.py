from typing import Any, Tuple

import shapely
from shapely.geometry import base, mapping
from shapely.validation import explain_validity

from app.core.config import settings
from app.core.logging import logger


def validate_and_repair_geometry(
    geom: base.BaseGeometry | None,
) -> Tuple[base.BaseGeometry | None, bool, str | None]:
    """Validates geometry and attempts safe repair if invalid.

    Returns:
        (processed_geometry, was_repaired, error_or_reason)
    """
    if geom is None:
        return None, False, "Geometry is null"

    if geom.is_empty:
        return geom, False, "Geometry is empty"

    if geom.is_valid:
        return geom, False, None

    # Geometry is invalid
    validity_reason = explain_validity(geom)
    logger.debug(f"Geometry invalid ({geom.geom_type}): {validity_reason}")

    if not settings.ATTEMPT_GEOMETRY_REPAIR:
        return geom, False, f"Invalid geometry: {validity_reason}"

    # Attempt safe repair using shapely.make_valid
    try:
        repaired = shapely.make_valid(geom)
        if repaired.is_valid and not repaired.is_empty:
            logger.info(f"Successfully repaired invalid {geom.geom_type} ({validity_reason})")
            return repaired, True, None
    except Exception as e:
        logger.warning(f"make_valid failed for geometry: {e}")

    # Fallback repair: buffer(0) on Polygons
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        try:
            buffered = geom.buffer(0)
            if buffered.is_valid and not buffered.is_empty:
                logger.info(f"Successfully repaired invalid {geom.geom_type} using buffer(0)")
                return buffered, True, None
        except Exception as e:
            logger.warning(f"buffer(0) repair failed: {e}")

    return geom, False, f"Invalid geometry could not be safely repaired: {validity_reason}"


def geometry_to_geojson(geom: base.BaseGeometry | None) -> dict[str, Any] | None:
    """Converts a Shapely geometry into standard GeoJSON dictionary representation."""
    if geom is None or geom.is_empty:
        return None
    try:
        return mapping(geom)
    except Exception as e:
        logger.warning(f"Error converting geometry to GeoJSON: {e}")
        return None
