from pathlib import Path

import pytest

from app.core.exceptions import ParsingException
from app.parsers.kml_parser import KMLParser
from app.parsers.shapefile_parser import ShapefileParser
from app.utils.file_validation import safe_extract_zip

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"


def test_kml_parser_polygons():
    parser = KMLParser()
    dataset = parser.parse(SAMPLE_DIR / "sample_polygon.kml")

    assert dataset.file_type == "kml"
    assert dataset.detected_crs == "EPSG:4326"
    assert len(dataset.features) == 2

    feat1 = dataset.features[0]
    assert feat1.geometry_type == "Polygon"
    assert feat1.geometry is not None
    assert feat1.properties.get("name") == "Survey Zone Alpha"
    assert feat1.properties.get("crop_type") == "Wheat"


def test_kml_parser_lines():
    parser = KMLParser()
    dataset = parser.parse(SAMPLE_DIR / "sample_lines.kml")

    assert len(dataset.features) == 2
    assert all(f.geometry_type == "LineString" for f in dataset.features)
    assert dataset.features[0].properties.get("name") == "Flight Corridor 101"


def test_kml_parser_points():
    parser = KMLParser()
    dataset = parser.parse(SAMPLE_DIR / "sample_points.kml")

    assert len(dataset.features) == 2
    assert all(f.geometry_type == "Point" for f in dataset.features)
    assert dataset.features[0].properties.get("name") == "GCP-01"


def test_shapefile_parser(tmp_path):
    zip_path = SAMPLE_DIR / "sample_shapefile.zip"
    extracted_dir = tmp_path / "extracted_shp"
    extracted_dir.mkdir()

    shp_path = safe_extract_zip(zip_path, extracted_dir)
    parser = ShapefileParser()
    dataset = parser.parse(shp_path)

    assert dataset.file_type == "shapefile"
    assert dataset.detected_crs is not None
    assert "4326" in dataset.detected_crs or "WGS" in dataset.detected_crs
    assert len(dataset.features) == 2
    assert all(f.geometry_type == "Polygon" for f in dataset.features)
    assert dataset.features[0].properties.get("ZONE_NAME") == "Zone Alpha Industrial"


def test_kml_parser_nonexistent_file():
    parser = KMLParser()
    with pytest.raises(ParsingException):
        parser.parse(Path("non_existent_file.kml"))
