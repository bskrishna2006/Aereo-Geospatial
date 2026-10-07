import io
import zipfile

import pytest

from app.core.exceptions import FileValidationException, UnsupportedFileTypeException
from app.utils.file_validation import (
    safe_extract_zip,
    validate_content_signature,
    validate_file_extension,
)


def test_validate_file_extension():
    assert validate_file_extension("survey.kml") == "kml"
    assert validate_file_extension("SURVEY.KML") == "kml"
    assert validate_file_extension("data.zip") == "shapefile"
    assert validate_file_extension("DATA.ZIP") == "shapefile"

    with pytest.raises(UnsupportedFileTypeException):
        validate_file_extension("data.geojson")

    with pytest.raises(UnsupportedFileTypeException):
        validate_file_extension("report.pdf")


def test_zip_slip_prevention(tmp_path):
    # Construct malicious zip with ../../../evil.txt
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0")
        zf.writestr("test.shp", "shp")
        zf.writestr("test.shx", "shx")
        zf.writestr("test.dbf", "dbf")

    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    with pytest.raises(FileValidationException) as exc_info:
        safe_extract_zip(malicious_zip, target_dir)
    assert "ZIP_SLIP_ATTEMPT" in exc_info.value.code


def test_incomplete_shapefile_missing_components(tmp_path):
    incomplete_zip = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(incomplete_zip, "w") as zf:
        zf.writestr("only_shape.shp", "dummy content")

    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    with pytest.raises(FileValidationException) as exc_info:
        safe_extract_zip(incomplete_zip, target_dir)
    assert "INCOMPLETE_SHAPEFILE" in exc_info.value.code


def test_validate_content_signature():
    valid_kml = io.BytesIO(b"<?xml version='1.0'?><kml></kml>")
    validate_content_signature(valid_kml, "kml")

    invalid_kml = io.BytesIO(b"Just plain text without xml")
    with pytest.raises(FileValidationException):
        validate_content_signature(invalid_kml, "kml")
