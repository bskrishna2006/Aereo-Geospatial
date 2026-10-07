# Aereo Geospatial File Measurement API

A production-grade geospatial measurement backend API built with **Python 3.12+**, **FastAPI**, **SQLAlchemy 2.x**, **Shapely**, **PyProj**, and **PostgreSQL**.

The API ingests geospatial datasets (**KML** and ESRI **Shapefile ZIP** archives), detects and validates Coordinate Reference Systems (CRS), safely repairs degenerated geometries, projects geographic coordinates into local metric coordinate systems (UTM), computes planar measurements (Polygon Area in $\text{m}^2$, LineString Length in $\text{m}$), and produces explainable data quality audits.

---

## Table of Contents

- [1. Problem Statement \& Highlights](#1-problem-statement--highlights)
- [2. System Architecture](#2-system-architecture)
- [3. Key Innovations](#3-key-innovations)
- [4. Technology Stack \& Rationale](#4-technology-stack--rationale)
- [5. Coordinate Reference System (CRS) Strategy](#5-coordinate-reference-system-crs-strategy)
- [6. Security \& Safe Ingestion](#6-security--safe-ingestion)
- [7. Local Quickstart](#7-local-quickstart)
- [8. Docker \& Containerization](#8-docker--containerization)
- [9. API Documentation \& Examples](#9-api-documentation--examples)
- [10. Testing \& Quality Assurance](#10-testing--quality-assurance)
- [11. Architecture Decisions (ADR)](#11-architecture-decisions-adr)
- [12. Limitations \& Future Scope](#12-limitations--future-scope)

---

## 1. Problem Statement & Highlights

Geospatial files captured from drone surveys, satellite imagery, and GIS applications often arrive in diverse coordinate systems and file formats. Calculating measurements directly on geographic coordinates (degrees, e.g. `EPSG:4326`) produces distorted, mathematically invalid results because degrees are angular units on an ellipsoid, not linear meters. Furthermore, real-world datasets frequently contain corrupt, self-intersecting, or unsupported features that must not crash an entire ingestion batch.

### Core Capabilities:
- **Strict Format Support**: Accepts `.kml` and `.zip` archives containing ESRI Shapefile bundles (`.shp`, `.shx`, `.dbf`, `.prj`).
- **CRS Intelligence**: Automatically transforms geographic coordinates into local transverse Mercator (UTM) metric projected systems (`EPSG:326xx` North / `EPSG:327xx` South).
- **Geometric Precision**:
  - `Polygon` & `MultiPolygon` $\rightarrow$ Area in square meters ($\text{m}^2$).
  - `LineString` & `MultiLineString` $\rightarrow$ Length in meters ($\text{m}$).
  - `Point` & `MultiPoint` $\rightarrow$ Handled gracefully as `NOT_REQUIRED` ($\text{measurement} = \text{null}$).
  - `Unsupported` (e.g. `GeometryCollection`) $\rightarrow$ Handled gracefully as `UNSUPPORTED`.
- **Fault-Tolerant Geometry Pipeline**: Attempts automated topological repair for self-intersecting polygons (`buffer(0)` and `make_valid`). An invalid feature never halts processing of the remaining valid features.
- **Explainable Measurements**: Every computed measurement exposes the projection algorithm, EPSG code, and repair status.
- **Enterprise Security**: Immune to Zip Slip path traversal attacks, zip bombs, XXE XML entity expansion, and unvalidated file types.

---

## 2. System Architecture

The application adopts a **Layered Clean Architecture** where each layer maintains isolated responsibilities:

```text
                            Client (HTTP / REST)
                                     │
                                     ▼
                      ┌──────────────────────────────┐
                      │    FastAPI Presentation      │
                      │  (app/api/routes/*.py)       │
                      └──────────────┬───────────────┘
                                     │
                                     ▼
                      ┌──────────────────────────────┐
                      │      File Service Layer      │
                      │  - Validation & Ingestion    │
                      │  - Archive Safety & Storage  │
                      └──────────────┬───────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
         ┌─────────────────────┐           ┌─────────────────────┐
         │     File Parsers    │           │ Processing Pipeline │
         │  - KMLParser        │           │ (Feature Processing)│
         │  - ShapefileParser  │           └──────────┬──────────┘
         └─────────────────────┘                      │
                                     ┌────────────────┴────────────────┐
                                     ▼                                 ▼
                          ┌─────────────────────┐           ┌─────────────────────┐
                          │     CRS Service     │           │ Measurement Service │
                          │  - Projection Logic │           │  - Polygon Area     │
                          │  - UTM Detection    │           │  - Line Length      │
                          └─────────────────────┘           │  - Topology Repair  │
                                                            └──────────┬──────────┘
                                                                       │
                                     ┌─────────────────────────────────┘
                                     ▼
                      ┌──────────────────────────────┐
                      │     Data Access Layer        │
                      │  - FileRepository            │
                      │  - FeatureRepository         │
                      └──────────────┬───────────────┘
                                     │
                                     ▼
                      ┌──────────────────────────────┐
                      │    PostgreSQL Database       │
                      │  - file_records              │
                      │  - feature_records           │
                      └──────────────────────────────┘
```

### End-to-End Processing Flow:

```text
1. Client POST /api/files/ (multipart/form-data)
   │
2. Validate extension (.kml / .zip) and file size (< 50MB)
   │
3. Content signature sniffing (verify PK header for ZIP / XML header for KML)
   │
4. Isolated Disk Storage outside source code directory
   │
5. Safe Archive Extraction (Zip Slip detection, decompression bomb ratio validation)
   │
6. Shapefile bundle verification (checks for .shp, .shx, and .dbf)
   │
7. Ingestion Parser extracts raw features, attributes, and source CRS
   │
8. Geometric Validation & Repair (checks emptiness, self-intersections, repairs via buffer(0))
   │
9. Coordinate Reprojection (Geographic WGS84 -> Local UTM Zone via PyProj)
   │
10. Metric Measurement (Planar Area in m² / Length in m)
   │
11. Persistence via High-Performance Bulk Ingestion to PostgreSQL
   │
12. Compute Innovation #1 Statistics and Innovation #2 Quality Audit
   │
13. Client retrieves file metadata, paginated measurements, and quality health reports
```

---

## 3. Key Innovations

### Innovation #1: Processing Statistics & Metrics
Every processed file computes an aggregate summary of execution duration and geometric coverage:
- Total features count
- Count per geometry type (`Polygon`, `LineString`, `Point`, `Unsupported`)
- Total cumulative polygon area in $\text{m}^2$
- Total cumulative line length in $\text{m}$
- Processing duration in milliseconds

### Innovation #2: Processing Health & Data Quality Report
Exposed via `GET /api/files/{id}/summary/`, this endpoint functions as an **automated data quality auditor** rather than a mere CRUD view:
- Categorizes features into `valid_features`, `repaired_features`, `invalid_features`, `unsupported_features`, and `point_features_not_required`.
- Identifies features that required topological surgery vs features that succeeded natively.
- Enables GIS analysts to immediately evaluate survey hygiene and flight accuracy.

### Innovation #3: Explainable Measurement Metadata
Geospatial calculations must not be a "black box". Every individual measurement item includes a `calculation` object:
```json
{
  "feature_id": 0,
  "geometry_type": "Polygon",
  "measurement_type": "area",
  "value": 49202.4831,
  "unit": "m²",
  "source_crs": "EPSG:4326",
  "measurement_crs": "EPSG:32643",
  "calculation": {
    "method": "projected_planar_area",
    "projected_crs": "EPSG:32643",
    "formula_description": "Projected from EPSG:4326 to EPSG:32643. Planar area computed via surveyor formula / Green's theorem.",
    "repaired_geometry": false
  }
}
```

---

## 4. Technology Stack & Rationale

| Layer | Technology | Rationale |
|---|---|---|
| **API Framework** | **FastAPI** | High-performance, native ASGI async, automatic OpenAPI documentation, declarative Pydantic schemas, and robust dependency injection. |
| **Data Validation** | **Pydantic v2** | Rust-backed validation core providing microsecond schema validation and serialization. |
| **ORM / Database** | **SQLAlchemy 2.x** | Modern type-safe queries, connection pooling, and bulk ingestion performance (`bulk_save_objects`). |
| **Migrations** | **Alembic** | Version-controlled, reproducible schema migrations across development and production environments. |
| **Relational Store** | **PostgreSQL 16** | Robust, ACID-compliant relational engine for files, features, and metadata. |
| **Geometry Engine**| **Shapely 2.x** | GEOS C-library bindings providing vector geometry primitives, topological validity checks, and repairs. |
| **Cartography & CRS**| **PyProj 3.x** | High-performance PROJ cartographic projection engine for geodetic coordinate transformations. |
| **Shapefile Parser** | **PyShp (shapefile)** | Pure-Python ESRI Shapefile reader/writer. Bypasses bulky C-extension compile errors across host operating systems. |
| **Secure XML Parsing**| **defusedxml** | Protects XML and KML parsing against Billion Laughs, quadratic blowup, and XML External Entity (XXE) vulnerabilities. |
| **Linter & Formatter**| **Ruff** | Lightning-fast static analysis, enforcing PEP 8 and clean architecture standards. |
| **Testing** | **pytest + HTTPX** | Isolated unit and integration test execution with in-memory SQLite fixtures. |

---

## 5. Coordinate Reference System (CRS) Strategy

### Why Geographic Coordinates Cannot Be Measured Directly
Geographic coordinates (`EPSG:4326` / WGS 84) represent points using angles (latitude and longitude in decimal degrees). Because the Earth is roughly an oblate spheroid:
1. One degree of longitude at the equator is $\approx 111.32\text{ km}$, but converges toward $0\text{ km}$ at the poles.
2. Calculating $\text{d}x \times \text{d}y$ on degrees yields meaningless "square degrees" rather than square meters.

### The Algorithm:
1. **Source CRS Verification**:
   - The parser inspects the Shapefile `.prj` WKT or uses KML's standard `EPSG:4326`.
   - If the CRS is absent, the system flags it as missing rather than guessing.
2. **Projected System Detection**:
   - If the source CRS is already a projected metric system (e.g. State Plane or an existing UTM zone with meter units), the system preserves it directly to avoid unnecessary transformation distortion.
3. **Automated UTM Zone Determination**:
   - If the source CRS is geographic (degrees), the geometry's representative centroid is extracted in WGS84:
     $$\text{Zone} = \left\lfloor \frac{\text{longitude} + 180^\circ}{6^\circ} \right\rfloor + 1 \quad (\text{clamped between } 1 \text{ and } 60)$$
   - **Northern Hemisphere** ($\text{latitude} \ge 0^\circ$): $\text{EPSG:32600} + \text{Zone}$
   - **Southern Hemisphere** ($\text{latitude} < 0^\circ$): $\text{EPSG:32700} + \text{Zone}$
4. **Coordinate Reprojection**:
   - `pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)` reprojects geometries into planar coordinates in meters.
   - Planar Green's Theorem area and Euclidean line length calculations are executed on the projected geometry.

---

## 6. Security & Safe Ingestion

1. **Zip Slip Prevention**:
   Archive entries are examined before extraction. Any entry containing directory traversal elements (`..`), absolute paths, or escaping paths outside the target destination triggers immediate rejection with `ZIP_SLIP_ATTEMPT`.
2. **Decompression Bomb Defense**:
   Uncompressed file sizes are summed before extraction. If the uncompressed-to-compressed ratio exceeds `MAX_UNCOMPRESSED_RATIO` (default: 100), the file is rejected with `ZIP_BOMB_DETECTED`.
3. **Shapefile Integrity Check**:
   A Shapefile is a multi-file collection. The archive must contain matching `.shp`, `.shx`, and `.dbf` components. Missing files yield descriptive errors with `INCOMPLETE_SHAPEFILE`.
4. **XXE Protection**:
   All KML parsing is executed through `defusedxml.ElementTree` to prevent external entity injection or XML expansion attacks.
5. **Storage Isolation**:
   Uploaded files are stored outside the code repository in an isolated temporary storage directory (`UPLOAD_DIRECTORY`).

---

## 7. Local Quickstart

### Prerequisites
- Python 3.12+
- Git
- PostgreSQL (or use Docker Compose for the database)

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd Aereo
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   *(Update `DATABASE_URL` in `.env` if using a custom local PostgreSQL instance)*

5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Generate synthetic sample datasets**:
   ```bash
   python create_sample_data.py
   ```

7. **Start the API server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Verify the server is running**:
   - Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Alternative ReDoc UI: [http://localhost:8000/redoc](http://localhost:8000/redoc)
   - Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 8. Docker & Containerization

A multi-container setup with **PostgreSQL 16** and the **FastAPI Application** is pre-configured.

### Run with Docker Compose

```bash
docker compose up --build
```

This single command will:
1. Launch an isolated PostgreSQL container with a persistent volume.
2. Execute a healthcheck verifying PostgreSQL readiness (`pg_isready`).
3. Build the Python 3.12 application container as an unprivileged user (`appuser`).
4. Apply Alembic migrations (`alembic upgrade head`).
5. Launch the Uvicorn ASGI server on port `8000`.

To stop the containers:
```bash
docker compose down
```

---

## 9. API Documentation & Examples

### 1. Upload Geospatial File
- **Method**: `POST`
- **Path**: `/api/files/`
- **Content-Type**: `multipart/form-data`

#### Example cURL:
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -F "file=@sample_data/sample_polygon.kml"
```

#### Example Response:
```json
{
  "id": "e2f0714b-7fc9-4fa2-bf6d-97813a48e77a",
  "filename": "sample_polygon.kml",
  "file_type": "kml",
  "file_size": 1500,
  "status": "COMPLETED",
  "message": "File uploaded and processed successfully."
}
```

---

### 2. Retrieve File Details
- **Method**: `GET`
- **Path**: `/api/files/{id}/`

#### Example cURL:
```bash
curl -X GET "http://localhost:8000/api/files/e2f0714b-7fc9-4fa2-bf6d-97813a48e77a/"
```

#### Example Response:
```json
{
  "id": "e2f0714b-7fc9-4fa2-bf6d-97813a48e77a",
  "filename": "sample_polygon.kml",
  "file_type": "kml",
  "file_size": 1500,
  "status": "COMPLETED",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "source_crs": "EPSG:4326",
  "measurement_crs": "EPSG:32643",
  "processing_started_at": "2026-10-07T08:50:00Z",
  "processing_completed_at": "2026-10-07T08:50:00.012Z",
  "processing_duration_ms": 12,
  "error_message": null,
  "created_at": "2026-10-07T08:50:00Z",
  "updated_at": "2026-10-07T08:50:00.012Z"
}
```

---

### 3. Retrieve Paginated Measurements
- **Method**: `GET`
- **Path**: `/api/files/{id}/measurements/?page=1&page_size=50&status=SUCCESS`

#### Example cURL:
```bash
curl -X GET "http://localhost:8000/api/files/e2f0714b-7fc9-4fa2-bf6d-97813a48e77a/measurements/?page=1&page_size=10"
```

#### Example Response:
```json
{
  "file_id": "e2f0714b-7fc9-4fa2-bf6d-97813a48e77a",
  "results": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "measurement_type": "area",
      "value": 48320.1254,
      "unit": "m²",
      "status": "SUCCESS",
      "message": null,
      "source_crs": "EPSG:4326",
      "measurement_crs": "EPSG:32643",
      "calculation": {
        "method": "projected_planar_area",
        "projected_crs": "EPSG:32643",
        "formula_description": "Projected from EPSG:4326 to EPSG:32643. Planar area computed via surveyor formula / Green's theorem.",
        "repaired_geometry": false
      },
      "properties": {
        "name": "Survey Zone Alpha",
        "crop_type": "Wheat",
        "surveyor": "Aereo Drone Team"
      }
    },
    {
      "feature_id": 1,
      "geometry_type": "Polygon",
      "measurement_type": "area",
      "value": 108719.5123,
      "unit": "m²",
      "status": "SUCCESS",
      "message": null,
      "source_crs": "EPSG:4326",
      "measurement_crs": "EPSG:32643",
      "calculation": {
        "method": "projected_planar_area",
        "projected_crs": "EPSG:32643",
        "formula_description": "Projected from EPSG:4326 to EPSG:32643. Planar area computed via surveyor formula / Green's theorem.",
        "repaired_geometry": false
      },
      "properties": {
        "name": "Survey Zone Beta",
        "crop_type": "Mango"
      }
    }
  ],
  "pagination": {
    "total_records": 2,
    "page": 1,
    "page_size": 10,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 4. Data Quality & Health Audit Report (Innovation #2)
- **Method**: `GET`
- **Path**: `/api/files/{id}/summary/`

#### Example cURL:
```bash
curl -X GET "http://localhost:8000/api/files/e2f0714b-7fc9-4fa2-bf6d-97813a48e77a/summary/"
```

#### Example Response:
```json
{
  "file": {
    "id": "e2f0714b-7fc9-4fa2-bf6d-97813a48e77a",
    "name": "sample_mixed.kml",
    "crs": "EPSG:4326",
    "measurement_crs": "EPSG:32643",
    "file_type": "kml",
    "file_size": 1778
  },
  "processing": {
    "status": "COMPLETED",
    "duration_ms": 14,
    "started_at": "2026-10-07T08:50:10Z",
    "completed_at": "2026-10-07T08:50:10.014Z",
    "error_message": null
  },
  "quality": {
    "total_features": 4,
    "valid_features": 3,
    "repaired_features": 1,
    "invalid_features": 0,
    "unsupported_features": 0,
    "point_features_not_required": 1
  },
  "geometry_breakdown": {
    "Polygon": 2,
    "LineString": 1,
    "Point": 1
  },
  "measurements": {
    "total_area_m2": 62410.85,
    "total_length_m": 412.35,
    "polygon_count": 2,
    "linestring_count": 1
  }
}
```

---

## 10. Testing & Quality Assurance

The codebase features comprehensive unit, integration, and security tests.

### Running Tests
Execute the pytest suite:
```bash
pytest -v
```

### Test Suite Structure
```text
tests/
├── conftest.py                   # In-memory SQLite fixtures & TestClient configuration
├── unit/
│   ├── test_crs_service.py       # UTM calculation (N/S hemisphere), reprojection accuracy
│   ├── test_parsers.py           # KML and Shapefile parsing, attribute extraction
│   ├── test_measurements.py      # Area/length calculations, Points, and safe repairs
│   └── test_validation.py        # Zip Slip prevention, bomb ratios, and missing shapefiles
└── integration/
    ├── test_api_files.py         # File upload lifecycle and validation error handling
    ├── test_api_measurements.py  # Pagination, filtering, and calculation metadata
    └── test_api_summary.py       # Quality audit reports and aggregate metrics
```

### Code Formatting & Static Analysis
Check compliance with Ruff:
```bash
ruff check .
ruff format --check .
```

---

## 11. Architecture Decisions (ADR)

### ADR-01: Why FastAPI?
FastAPI was selected for its native ASGI async architecture, automatic OpenAPI document generation, and first-class integration with Pydantic v2. This provides strict input validation without writing repetitive parsing code.

### ADR-02: Why PostgreSQL + SQLAlchemy 2.x?
PostgreSQL provides ACID transactions, relational integrity with cascading foreign keys (`file_records` $\rightarrow$ `feature_records`), and rich JSON column support for flexible feature properties. SQLAlchemy 2.x provides type-checked mapping and high-throughput bulk insertion via `bulk_save_objects`.

### ADR-03: Storage Strategy (GeoJSON vs PostGIS)
- **Decision**: Store geometries as standard GeoJSON in JSON columns rather than forcing PostGIS C-extensions.
- **Rationale**: For an ingestion and measurement API, planar measurements are computed in memory during ingestion and persisted alongside the metadata. Storing geometries in standard GeoJSON avoids requiring complex OS-level GDAL/PostGIS binary packages during deployment and local developer setup, while keeping geometries fully serializable to client mapping libraries (e.g. Leaflet / Mapbox / Cesium).

### ADR-04: Why PyShp + Shapely + PyProj?
Many geospatial backends fail to build on developer machines due to complex native GDAL/GEOS C-library mismatches. By combining `PyShp` (pure-Python shapefile parsing) with `Shapely 2.x` and `PyProj 3.x` (precompiled C-wheels), the service guarantees 100% cross-platform reliability on Windows, macOS, and Linux containers.

### ADR-05: Synchronous vs Background Worker Processing
The service is architected to balance instant response times for interactive file uploads with clean background worker separation:
- `SYNC_PROCESSING=true` (default): Immediately processes the file and returns `COMPLETED` status. Ideal for interactive UI surveys, local development, and end-to-end testing.
- `SYNC_PROCESSING=false`: Submits the file to FastAPI `BackgroundTasks` and returns `PROCESSING` status immediately.
- The pipeline is isolated in `ProcessingService`, allowing drop-in transition to Celery/ARQ workers without altering business logic.

---

## 12. Limitations & Future Scope

### Current Limitations:
1. **Very Large Files (> 1GB)**: Extremely large Shapefiles with hundreds of thousands of geometries can consume significant server memory.
2. **Single UTM Zone Approximations**: For continental-scale surveys crossing multiple UTM zones, UTM introduces slight scale distortion along zone boundaries.

### Production Roadmap:
- **Distributed Worker Queue**: Migrate background jobs to Celery / ARQ backed by Redis for worker autoscale.
- **Object Storage**: Offload raw uploaded files to Amazon S3, Google Cloud Storage, or MinIO.
- **PostGIS Geodetic Indexing**: Enable PostGIS spatial indexes (`GIST`) for spatial querying (e.g. bounding-box intersections, point-in-polygon queries).
- **Format Expansion**: Add parsers for GeoJSON, GeoPackage (`.gpkg`), and Cloud-Optimized GeoTIFFs (COG).
- **Geodesic Calculations**: Support geodesic ellipsoidal calculations via `pyproj.Geod` alongside planar projections.
