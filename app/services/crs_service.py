import math

from pyproj import CRS, Transformer
from shapely.geometry import base
from shapely.ops import transform

from app.core.exceptions import CRSError
from app.core.logging import logger


class CRSService:
    """Service dedicated to CRS detection, classification, UTM zone determination,
    and safe geometric reprojection into metric projected coordinate systems.
    """

    @staticmethod
    def parse_crs(crs_input: str | None) -> CRS:
        """Parses a CRS string (EPSG code, WKT, PROJ string) into a PyProj CRS object.

        Raises CRSError if the CRS is missing or invalid.
        """
        if not crs_input or not crs_input.strip():
            raise CRSError("CRS is missing or unspecified in dataset.")
        try:
            return CRS.from_user_input(crs_input)
        except Exception as e:
            raise CRSError(f"Unable to parse CRS identifier '{crs_input}': {e}")

    @staticmethod
    def is_projected_metric(crs: CRS) -> bool:
        """Checks if the CRS is a projected coordinate reference system with metric units."""
        if not crs.is_projected:
            return False
        # Verify unit of measurement is meters
        axis_units = [
            axis.unit_name.lower() for axis in crs.axis_info if hasattr(axis, "unit_name")
        ]
        return any("metre" in u or "meter" in u for u in axis_units)

    @classmethod
    def determine_utm_crs(cls, lon: float, lat: float) -> str:
        """Determines the appropriate WGS 84 / UTM zone EPSG code for a given longitude and latitude.

        Formula:
          zone = floor((lon + 180) / 6) + 1  (clamped to 1-60)
          Northern Hemisphere (lat >= 0): EPSG:326{zone:02d}
          Southern Hemisphere (lat < 0): EPSG:327{zone:02d}
        """
        # Clamp lon to [-180, 180]
        clamped_lon = max(-180.0, min(180.0, lon))
        if clamped_lon == 180.0:
            clamped_lon = 179.999999

        zone = int(math.floor((clamped_lon + 180.0) / 6.0)) + 1
        zone = max(1, min(60, zone))

        if lat >= 0:
            epsg_code = 32600 + zone
        else:
            epsg_code = 32700 + zone

        return f"EPSG:{epsg_code}"

    @classmethod
    def determine_measurement_crs(
        cls,
        geom: base.BaseGeometry,
        source_crs_str: str | None,
    ) -> str:
        """Selects the appropriate projected CRS for accurate metric measurements.

        Strategy:
        1. Validate source CRS. If missing, raises CRSError.
        2. If source CRS is already projected and uses meters (e.g. UTM, State Plane in meters),
           retain it directly.
        3. If source CRS is geographic (degrees, e.g. EPSG:4326):
           Calculate geographic centroid/representative point and determine local UTM zone.
        4. If source CRS is another projected system not in meters, reproject via UTM.
        """
        source_crs = cls.parse_crs(source_crs_str)

        if cls.is_projected_metric(source_crs):
            # Already projected in meters
            epsg = source_crs.to_epsg()
            return f"EPSG:{epsg}" if epsg else source_crs.to_string()

        # Source CRS is geographic or non-metric.
        # Reproject centroid to WGS84 (EPSG:4326) to compute UTM zone safely
        wgs84 = CRS.from_epsg(4326)
        if source_crs != wgs84:
            transformer_to_wgs84 = Transformer.from_crs(source_crs, wgs84, always_xy=True)
            # Transform geom representative point to WGS84
            pt = geom.representative_point()
            lon, lat = transformer_to_wgs84.transform(pt.x, pt.y)
        else:
            pt = geom.representative_point()
            lon, lat = pt.x, pt.y

        # Determine UTM zone
        utm_crs = cls.determine_utm_crs(lon, lat)
        logger.debug(f"Determined measurement CRS {utm_crs} for location ({lon:.4f}, {lat:.4f})")
        return utm_crs

    @classmethod
    def transform_geometry(
        cls,
        geom: base.BaseGeometry,
        source_crs_str: str,
        target_crs_str: str,
    ) -> base.BaseGeometry:
        """Transforms a Shapely geometry from source_crs to target_crs using PyProj."""
        if source_crs_str == target_crs_str:
            return geom

        src = cls.parse_crs(source_crs_str)
        dst = cls.parse_crs(target_crs_str)

        transformer = Transformer.from_crs(src, dst, always_xy=True)
        transformed_geom = transform(transformer.transform, geom)
        return transformed_geom


crs_service = CRSService()
