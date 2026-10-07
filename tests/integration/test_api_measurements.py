from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"


def test_get_measurements_and_pagination(client):
    # Upload mixed survey containing Polygon, LineString, Point, and repaired Polygon
    file_path = SAMPLE_DIR / "sample_mixed.kml"
    with open(file_path, "rb") as f:
        upload_res = client.post(
            "/api/files/",
            files={"file": ("sample_mixed.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]

    # Retrieve all measurements (default page=1, page_size=50)
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    data = meas_res.json()
    assert data["file_id"] == file_id
    assert len(data["results"]) == 4

    # Verify pagination metadata
    pagination = data["pagination"]
    assert pagination["total_records"] == 4
    assert pagination["page"] == 1
    assert pagination["page_size"] == 50
    assert pagination["total_pages"] == 1
    assert not pagination["has_next"]

    # Verify Feature 0: Polygon
    feat0 = data["results"][0]
    assert feat0["geometry_type"] == "Polygon"
    assert feat0["measurement_type"] == "area"
    assert feat0["unit"] == "m²"
    assert feat0["status"] == "SUCCESS"
    assert feat0["value"] > 0
    assert feat0["calculation"] is not None
    assert feat0["calculation"]["method"] == "projected_planar_area"

    # Verify Feature 1: LineString
    feat1 = data["results"][1]
    assert feat1["geometry_type"] == "LineString"
    assert feat1["measurement_type"] == "length"
    assert feat1["unit"] == "m"
    assert feat1["status"] == "SUCCESS"
    assert feat1["value"] > 0

    # Verify Feature 2: Point (NOT_REQUIRED)
    feat2 = data["results"][2]
    assert feat2["geometry_type"] == "Point"
    assert feat2["measurement_type"] is None
    assert feat2["value"] is None
    assert feat2["status"] == "NOT_REQUIRED"

    # Verify Feature 3: Self-intersecting polygon (REPAIRED)
    feat3 = data["results"][3]
    assert feat3["geometry_type"] in ("Polygon", "MultiPolygon")
    assert feat3["status"] == "REPAIRED"
    assert feat3["calculation"]["repaired_geometry"] is True


def test_measurements_pagination_pages(client):
    file_path = SAMPLE_DIR / "sample_mixed.kml"
    with open(file_path, "rb") as f:
        upload_res = client.post(
            "/api/files/",
            files={"file": ("sample_mixed.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = upload_res.json()["id"]

    # Page 1 with page_size=2
    res_p1 = client.get(f"/api/files/{file_id}/measurements/?page=1&page_size=2")
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert len(p1_data["results"]) == 2
    assert p1_data["pagination"]["page"] == 1
    assert p1_data["pagination"]["total_pages"] == 2
    assert p1_data["pagination"]["has_next"] is True

    # Page 2 with page_size=2
    res_p2 = client.get(f"/api/files/{file_id}/measurements/?page=2&page_size=2")
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    assert len(p2_data["results"]) == 2
    assert p2_data["pagination"]["page"] == 2
    assert p2_data["pagination"]["has_next"] is False


def test_measurements_status_filtering(client):
    file_path = SAMPLE_DIR / "sample_mixed.kml"
    with open(file_path, "rb") as f:
        upload_res = client.post(
            "/api/files/",
            files={"file": ("sample_mixed.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = upload_res.json()["id"]

    # Filter for NOT_REQUIRED (Point)
    res = client.get(f"/api/files/{file_id}/measurements/?status=NOT_REQUIRED")
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["geometry_type"] == "Point"
