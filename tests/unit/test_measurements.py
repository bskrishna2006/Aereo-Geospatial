from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.parsers.base import ParsedFeature
from app.services.measurement_service import measurement_service


def test_polygon_area_calculated_in_square_meters():
    # Polygon in Bangalore (approx 200m x 220m)
    poly = Polygon(
        [
            (77.585, 12.971),
            (77.587, 12.971),
            (77.587, 12.973),
            (77.585, 12.973),
            (77.585, 12.971),
        ]
    )
    feature = ParsedFeature(
        feature_index=0,
        geometry_type="Polygon",
        geometry=poly,
        source_crs="EPSG:4326",
    )

    result = measurement_service.process_feature(feature, dataset_crs="EPSG:4326")

    assert result.processing_status == "SUCCESS"
    assert result.measurement_type == "area"
    assert result.measurement_unit == "m²"
    assert result.measurement_value is not None
    # Verify realistic area in square meters (~48,000 m²)
    assert 40000 < result.measurement_value < 60000
    assert result.measurement_crs == "EPSG:32643"
    assert result.calculation_metadata is not None
    assert result.calculation_metadata["method"] == "projected_planar_area"


def test_linestring_length_calculated_in_meters():
    # LineString approx 500m length
    line = LineString(
        [
            (77.585, 12.971),
            (77.587, 12.973),
            (77.589, 12.975),
        ]
    )
    feature = ParsedFeature(
        feature_index=1,
        geometry_type="LineString",
        geometry=line,
        source_crs="EPSG:4326",
    )

    result = measurement_service.process_feature(feature, dataset_crs="EPSG:4326")

    assert result.processing_status == "SUCCESS"
    assert result.measurement_type == "length"
    assert result.measurement_unit == "m"
    assert result.measurement_value is not None
    assert 400 < result.measurement_value < 1000
    assert result.calculation_metadata["method"] == "projected_planar_length"


def test_point_measurement_not_required():
    pt = Point(77.585, 12.971)
    feature = ParsedFeature(
        feature_index=2,
        geometry_type="Point",
        geometry=pt,
        source_crs="EPSG:4326",
    )

    result = measurement_service.process_feature(feature, dataset_crs="EPSG:4326")

    assert result.processing_status == "NOT_REQUIRED"
    assert result.measurement_type is None
    assert result.measurement_value is None
    assert result.measurement_unit is None


def test_unsupported_geometry():
    gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    feature = ParsedFeature(
        feature_index=3,
        geometry_type="GeometryCollection",
        geometry=gc,
        source_crs="EPSG:4326",
    )

    result = measurement_service.process_feature(feature, dataset_crs="EPSG:4326")

    assert result.processing_status == "UNSUPPORTED"
    assert "not supported" in result.error_message.lower()


def test_empty_geometry_failed():
    poly_empty = Polygon()
    feature = ParsedFeature(
        feature_index=4,
        geometry_type="Polygon",
        geometry=poly_empty,
        source_crs="EPSG:4326",
    )

    result = measurement_service.process_feature(feature, dataset_crs="EPSG:4326")

    assert result.processing_status == "FAILED"
    assert "empty" in result.error_message.lower()


def test_self_intersecting_polygon_repair():
    # Bowtie polygon (self-intersecting)
    bowtie = Polygon(
        [
            (77.580, 12.970),
            (77.582, 12.972),
            (77.580, 12.972),
            (77.582, 12.970),
            (77.580, 12.970),
        ]
    )
    assert not bowtie.is_valid

    feature = ParsedFeature(
        feature_index=5,
        geometry_type="Polygon",
        geometry=bowtie,
        source_crs="EPSG:4326",
    )

    result = measurement_service.process_feature(feature, dataset_crs="EPSG:4326")

    assert result.processing_status == "REPAIRED"
    assert result.measurement_type == "area"
    assert result.measurement_value is not None
    assert result.measurement_value > 0
    assert result.calculation_metadata["repaired_geometry"] is True
