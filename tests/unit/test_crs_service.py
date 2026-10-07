import pytest
from shapely.geometry import Polygon

from app.core.exceptions import CRSError
from app.services.crs_service import crs_service


def test_utm_zone_determination_northern_hemisphere():
    # Bangalore, India (approx lon 77.59, lat 12.97) -> Zone 43 North -> EPSG:32643
    utm = crs_service.determine_utm_crs(lon=77.59, lat=12.97)
    assert utm == "EPSG:32643"


def test_utm_zone_determination_southern_hemisphere():
    # Rio de Janeiro, Brazil (approx lon -43.2, lat -22.9) -> Zone 23 South -> EPSG:32723
    utm = crs_service.determine_utm_crs(lon=-43.2, lat=-22.9)
    assert utm == "EPSG:32723"


def test_utm_zone_boundary_values():
    # Lon -180 to 180 clamp check
    utm_west = crs_service.determine_utm_crs(lon=-180.0, lat=10.0)
    assert utm_west == "EPSG:32601"

    utm_east = crs_service.determine_utm_crs(lon=180.0, lat=10.0)
    assert utm_east == "EPSG:32660"


def test_missing_crs_raises_error():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    with pytest.raises(CRSError) as exc_info:
        crs_service.determine_measurement_crs(poly, source_crs_str=None)
    assert "missing" in str(exc_info.value.message).lower()


def test_already_projected_metric_crs_retained():
    poly = Polygon([(500000, 1400000), (501000, 1400000), (501000, 1401000), (500000, 1400000)])
    # Source CRS is already UTM 43N
    target_crs = crs_service.determine_measurement_crs(poly, source_crs_str="EPSG:32643")
    assert target_crs == "EPSG:32643"


def test_transform_geometry_from_geographic_to_utm():
    # 0.001 deg box in Bangalore
    poly = Polygon(
        [
            (77.585, 12.971),
            (77.587, 12.971),
            (77.587, 12.973),
            (77.585, 12.973),
            (77.585, 12.971),
        ]
    )
    # Unprojected area in degrees is tiny (~4e-6)
    deg_area = poly.area
    assert deg_area < 0.0001

    target_crs = crs_service.determine_measurement_crs(poly, "EPSG:4326")
    projected_geom = crs_service.transform_geometry(poly, "EPSG:4326", target_crs)

    # In UTM meters, area is approx 200m x 220m = ~44,000 m²
    metric_area = projected_geom.area
    assert 40000 < metric_area < 60000
