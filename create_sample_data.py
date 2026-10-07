"""Script to programmatically generate synthetic sample datasets for Aereo Geospatial API.
All data is synthetically generated and licensed under Apache-2.0 / Public Domain.
"""

import zipfile
from pathlib import Path

import shapefile

SAMPLE_DIR = Path(__file__).parent / "sample_data"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def generate_polygon_kml():
    """Generates sample_polygon.kml with 2 distinct polygon survey zones in Bangalore (approx UTM 43N)."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Agricultural Survey Zones</name>
    <description>Synthetic polygon survey zones in Bangalore, India</description>
    <Placemark>
      <name>Survey Zone Alpha</name>
      <description>Northern crop plot</description>
      <ExtendedData>
        <Data name="crop_type"><value>Wheat</value></Data>
        <Data name="surveyor"><value>Aereo Drone Team</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5850,12.9710,0
              77.5870,12.9710,0
              77.5870,12.9730,0
              77.5850,12.9730,0
              77.5850,12.9710,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Survey Zone Beta</name>
      <description>Southern orchard plot</description>
      <ExtendedData>
        <Data name="crop_type"><value>Mango</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9650,0
              77.5930,12.9650,0
              77.5930,12.9680,0
              77.5900,12.9680,0
              77.5900,12.9650,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
    (SAMPLE_DIR / "sample_polygon.kml").write_text(kml_content, encoding="utf-8")


def generate_lines_kml():
    """Generates sample_lines.kml with 2 flight paths / transmission lines."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Drone Flight Survey Trajectories</name>
    <Placemark>
      <name>Flight Corridor 101</name>
      <description>Transmission line inspection corridor</description>
      <ExtendedData>
        <Data name="voltage_kv"><value>220</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5800,12.9700,50
          77.5850,12.9750,50
          77.5900,12.9780,50
          77.5950,12.9800,50
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Boundary Patrol Path</name>
      <description>Perimeter inspection line</description>
      <LineString>
        <coordinates>
          77.6000,12.9500,30
          77.6050,12.9520,30
          77.6100,12.9550,30
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    (SAMPLE_DIR / "sample_lines.kml").write_text(kml_content, encoding="utf-8")


def generate_points_kml():
    """Generates sample_points.kml with inspection points / GCPs (Ground Control Points)."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Ground Control Points</name>
    <Placemark>
      <name>GCP-01</name>
      <description>Primary Base Benchmark</description>
      <ExtendedData>
        <Data name="elevation_m"><value>920.5</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5946,12.9716,920.5</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>GCP-02</name>
      <description>Secondary Rover Station</description>
      <ExtendedData>
        <Data name="elevation_m"><value>918.2</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5980,12.9750,918.2</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""
    (SAMPLE_DIR / "sample_points.kml").write_text(kml_content, encoding="utf-8")


def generate_mixed_kml():
    """Generates sample_mixed.kml containing Polygons, LineStrings, Points, and a self-intersecting polygon for repair."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Comprehensive Mixed Survey</name>
    <!-- Feature 0: Valid Polygon -->
    <Placemark>
      <name>Main Campus Zone</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5850,12.9710,0
              77.5870,12.9710,0
              77.5870,12.9730,0
              77.5850,12.9730,0
              77.5850,12.9710,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Feature 1: Valid LineString -->
    <Placemark>
      <name>Access Road Line</name>
      <LineString>
        <coordinates>
          77.5850,12.9710,0
          77.5860,12.9715,0
          77.5880,12.9720,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Feature 2: Valid Point (no measurement required) -->
    <Placemark>
      <name>Survey Mast Point</name>
      <Point>
        <coordinates>77.5865,12.9722,0</coordinates>
      </Point>
    </Placemark>

    <!-- Feature 3: Self-intersecting 'Bowtie' Polygon (tests repair logic) -->
    <Placemark>
      <name>Self-Intersecting Boundary</name>
      <description>Invalid figure-eight bowtie polygon to test automated geometry repair</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5800,12.9700,0
              77.5820,12.9720,0
              77.5800,12.9720,0
              77.5820,12.9700,0
              77.5800,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
    (SAMPLE_DIR / "sample_mixed.kml").write_text(kml_content, encoding="utf-8")


def generate_shapefile_zip():
    """Generates sample_shapefile.zip containing .shp, .shx, .dbf, and .prj files."""
    tmp_base = SAMPLE_DIR / "temp_shp_build"
    tmp_base.mkdir(exist_ok=True)

    shp_filename = tmp_base / "survey_zones.shp"

    w = shapefile.Writer(str(shp_filename), shapeType=shapefile.POLYGON)
    w.field("ZONE_ID", "C", size=10)
    w.field("ZONE_NAME", "C", size=50)
    w.field("CATEGORY", "C", size=30)

    # Polygon 1: Alpha
    poly1 = [
        [77.5850, 12.9710],
        [77.5870, 12.9710],
        [77.5870, 12.9730],
        [77.5850, 12.9730],
        [77.5850, 12.9710],
    ]
    w.poly([poly1])
    w.record("Z001", "Zone Alpha Industrial", "Commercial")

    # Polygon 2: Beta
    poly2 = [
        [77.5900, 12.9650],
        [77.5930, 12.9650],
        [77.5930, 12.9680],
        [77.5900, 12.9680],
        [77.5900, 12.9650],
    ]
    w.poly([poly2])
    w.record("Z002", "Zone Beta Agricultural", "Farmland")

    w.close()

    # Create WGS84 .prj file
    prj_wkt = (
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
    )
    (tmp_base / "survey_zones.prj").write_text(prj_wkt, encoding="utf-8")

    # Bundle into sample_shapefile.zip
    zip_target = SAMPLE_DIR / "sample_shapefile.zip"
    with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_pack = tmp_base / f"survey_zones{ext}"
            zf.write(file_to_pack, arcname=f"survey_zones{ext}")

    # Clean temporary raw files
    for item in tmp_base.iterdir():
        item.unlink()
    tmp_base.rmdir()


if __name__ == "__main__":
    generate_polygon_kml()
    generate_lines_kml()
    generate_points_kml()
    generate_mixed_kml()
    generate_shapefile_zip()
    print("All sample datasets successfully generated in sample_data/")
