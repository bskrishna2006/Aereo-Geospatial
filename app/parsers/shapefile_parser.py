from pathlib import Path
from typing import Any

import shapefile
from pyproj import CRS
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.core.exceptions import ParsingException
from app.core.logging import logger
from app.parsers.base import GeoFileParser, ParsedDataset, ParsedFeature


class ShapefileParser(GeoFileParser):
    """Robust ESRI Shapefile parser using PyShp, PyProj, and Shapely."""

    def parse(self, file_path: Path) -> ParsedDataset:
        """Parses a Shapefile at the given .shp path."""
        if not file_path.exists():
            raise ParsingException(f"Shapefile not found: {file_path}")

        # Check for accompanying .prj file to detect CRS
        prj_path = file_path.with_suffix(".prj")
        # Try both lower and uppercase .PRJ
        if not prj_path.exists():
            prj_path = file_path.with_name(f"{file_path.stem}.PRJ")

        detected_crs: str | None = None
        if prj_path.exists():
            try:
                prj_wkt = prj_path.read_text(encoding="utf-8", errors="ignore").strip()
                if prj_wkt:
                    crs_obj = CRS.from_user_input(prj_wkt)
                    epsg = crs_obj.to_epsg()
                    detected_crs = f"EPSG:{epsg}" if epsg else crs_obj.to_string()
                    logger.info(f"Shapefile CRS detected from PRJ: {detected_crs}")
            except Exception as e:
                logger.warning(f"Could not parse .prj file {prj_path}: {e}")
                detected_crs = None
        else:
            logger.warning(f"No .prj file found for {file_path}. CRS is unspecified.")

        features: list[ParsedFeature] = []

        try:
            with shapefile.Reader(str(file_path), encoding="utf-8", encodingErrors="replace") as sf:
                fields = [field[0] for field in sf.fields[1:]]  # exclude DeletionFlag

                for idx, shape_rec in enumerate(sf.iterShapeRecords()):
                    geom: BaseGeometry | None = None
                    geom_type: str = "Unknown"
                    error_msg: str | None = None

                    try:
                        # Convert to shapely via __geo_interface__
                        geo_dict = shape_rec.shape.__geo_interface__
                        if geo_dict and geo_dict.get("coordinates"):
                            geom = shape(geo_dict)
                            geom_type = geom.geom_type
                        else:
                            geom_type = "Empty"
                            error_msg = "Shape record has no coordinate data"
                    except Exception as e:
                        geom_type = "Invalid"
                        error_msg = f"Failed to convert shape to geometry: {e}"

                    # Extract DBF attribute properties
                    props: dict[str, Any] = {}
                    try:
                        props = shape_rec.record.as_dict()
                    except Exception:
                        for f_idx, field_name in enumerate(fields):
                            if f_idx < len(shape_rec.record):
                                props[field_name] = shape_rec.record[f_idx]

                    # Sanitize properties (convert non-serializable objects like bytes or dates to strings)
                    clean_props = {}
                    for k, v in props.items():
                        if isinstance(v, (bytes, bytearray)):
                            clean_props[k] = v.decode("utf-8", errors="replace")
                        elif hasattr(v, "isoformat"):
                            clean_props[k] = v.isoformat()
                        else:
                            clean_props[k] = v

                    features.append(
                        ParsedFeature(
                            feature_index=idx,
                            geometry_type=geom_type,
                            geometry=geom,
                            properties=clean_props,
                            source_crs=detected_crs,
                            error_message=error_msg,
                        )
                    )

        except Exception as e:
            raise ParsingException(f"Failed to read Shapefile: {e}")

        logger.info(f"Shapefile parser extracted {len(features)} features from {file_path.name}")
        return ParsedDataset(
            detected_crs=detected_crs,
            features=features,
            file_type="shapefile",
            metadata={"source_file": file_path.name, "feature_count": len(features)},
        )
