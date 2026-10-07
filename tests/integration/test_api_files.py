import uuid
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"


def test_upload_kml_file_success(client):
    file_path = SAMPLE_DIR / "sample_polygon.kml"
    with open(file_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_polygon.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_polygon.kml"
    assert data["file_type"] == "kml"
    assert data["status"] in ("COMPLETED", "PROCESSING")

    file_id = data["id"]

    # Verify GET /api/files/{id}/
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 2
    assert info_data["status"] == "COMPLETED"
    assert info_data["crs"] == "EPSG:4326"
    assert info_data["measurement_crs"] == "EPSG:32643"


def test_upload_shapefile_zip_success(client):
    file_path = SAMPLE_DIR / "sample_shapefile.zip"
    with open(file_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_shapefile.zip", f, "application/zip")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sample_shapefile.zip"
    assert data["file_type"] == "shapefile"
    assert data["status"] in ("COMPLETED", "PROCESSING")

    file_id = data["id"]
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["feature_count"] == 2
    assert info_data["status"] == "COMPLETED"


def test_upload_unsupported_file_type(client):
    response = client.post(
        "/api/files/",
        files={"file": ("test.geojson", b'{"type": "FeatureCollection"}', "application/json")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_get_nonexistent_file(client):
    random_id = uuid.uuid4()
    response = client.get(f"/api/files/{random_id}/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FILE_NOT_FOUND"
