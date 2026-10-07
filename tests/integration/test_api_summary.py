from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"


def test_file_summary_and_quality_report(client):
    file_path = SAMPLE_DIR / "sample_mixed.kml"
    with open(file_path, "rb") as f:
        upload_res = client.post(
            "/api/files/",
            files={"file": ("sample_mixed.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    file_id = upload_res.json()["id"]

    # Request summary report
    summary_res = client.get(f"/api/files/{file_id}/summary/")
    assert summary_res.status_code == 200
    data = summary_res.json()

    # 1. File metadata
    assert data["file"]["id"] == file_id
    assert data["file"]["name"] == "sample_mixed.kml"
    assert data["file"]["crs"] == "EPSG:4326"
    assert data["file"]["measurement_crs"] == "EPSG:32643"

    # 2. Processing metadata
    assert data["processing"]["status"] in ("COMPLETED", "COMPLETED_WITH_ERRORS")
    assert data["processing"]["duration_ms"] is not None
    assert data["processing"]["duration_ms"] >= 0

    # 3. Quality breakdown
    quality = data["quality"]
    assert quality["total_features"] == 4
    # Valid = 1 original valid polygon + 1 valid line + 1 repaired polygon = 3
    assert quality["valid_features"] == 3
    assert quality["repaired_features"] == 1
    assert quality["invalid_features"] == 0
    assert quality["point_features_not_required"] == 1

    # 4. Geometry breakdown
    geo_breakdown = data["geometry_breakdown"]
    assert geo_breakdown.get("Polygon") == 2
    assert geo_breakdown.get("LineString") == 1
    assert geo_breakdown.get("Point") == 1

    # 5. Measurements aggregates
    measurements = data["measurements"]
    assert measurements["total_area_m2"] > 0
    assert measurements["total_length_m"] > 0
    assert measurements["polygon_count"] == 2
    assert measurements["linestring_count"] == 1
