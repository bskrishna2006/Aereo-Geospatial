from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry

from app.core.exceptions import ParsingException
from app.core.logging import logger
from app.parsers.base import GeoFileParser, ParsedDataset, ParsedFeature


def strip_tag(tag: str) -> str:
    """Strips XML namespace prefix from an element tag (e.g. '{http://...}Placemark' -> 'Placemark')."""
    return tag.split("}")[-1] if "}" in tag else tag


def parse_coordinates_text(coord_text: str | None) -> list[tuple[float, float]]:
    """Parses KML coordinate string ('lon,lat[,alt] lon,lat[,alt]') into list of (lon, lat) tuples."""
    if not coord_text:
        return []
    coords = []
    # Coordinates can be space-, tab-, or newline-delimited
    tokens = coord_text.strip().split()
    for token in tokens:
        parts = token.strip().split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                coords.append((lon, lat))
            except ValueError:
                continue
    return coords


class KMLParser(GeoFileParser):
    """Secure and robust parser for OGC KML 2.2 files using defusedxml."""

    def parse(self, file_path: Path) -> ParsedDataset:
        if not file_path.exists():
            raise ParsingException(f"KML file not found at path: {file_path}")

        try:
            tree = ET.parse(str(file_path))
            root = tree.getroot()
        except Exception as e:
            raise ParsingException(f"Failed to parse XML/KML structure: {e}")

        features: list[ParsedFeature] = []
        feature_index = 0

        # Traverse all elements finding Placemarks
        for elem in root.iter():
            if strip_tag(elem.tag) == "Placemark":
                feature = self._parse_placemark(elem, feature_index)
                if feature:
                    features.append(feature)
                    feature_index += 1

        logger.info(f"KML parser extracted {len(features)} features from {file_path.name}")
        return ParsedDataset(
            detected_crs="EPSG:4326",  # KML specification mandates WGS84
            features=features,
            file_type="kml",
            metadata={"source_file": file_path.name, "element_count": len(features)},
        )

    def _parse_placemark(self, placemark_elem: Any, index: int) -> ParsedFeature | None:
        properties: dict[str, Any] = {}
        geometry: BaseGeometry | None = None
        geometry_type: str = "Unknown"
        error_msg: str | None = None

        for child in placemark_elem:
            tag = strip_tag(child.tag)
            if tag == "name" and child.text:
                properties["name"] = child.text.strip()
            elif tag == "description" and child.text:
                properties["description"] = child.text.strip()
            elif tag == "ExtendedData":
                for data_elem in child:
                    dtag = strip_tag(data_elem.tag)
                    if dtag == "Data":
                        attr_name = data_elem.attrib.get("name")
                        val_elem = next((c for c in data_elem if strip_tag(c.tag) == "value"), None)
                        if attr_name and val_elem is not None and val_elem.text:
                            properties[attr_name] = val_elem.text.strip()
                    elif dtag == "SimpleData":
                        attr_name = data_elem.attrib.get("name")
                        if attr_name and data_elem.text:
                            properties[attr_name] = data_elem.text.strip()
            else:
                # Check for geometry elements
                parsed_geom = self._parse_geometry_element(child)
                if parsed_geom is not None:
                    geometry = parsed_geom

        if geometry is not None:
            geometry_type = geometry.geom_type
        else:
            geometry_type = "None"
            error_msg = "No valid geometry element found in Placemark"

        return ParsedFeature(
            feature_index=index,
            geometry_type=geometry_type,
            geometry=geometry,
            properties=properties,
            source_crs="EPSG:4326",
            error_message=error_msg,
        )

    def _parse_geometry_element(self, elem: Any) -> BaseGeometry | None:
        tag = strip_tag(elem.tag)

        if tag == "Point":
            for child in elem:
                if strip_tag(child.tag) == "coordinates":
                    coords = parse_coordinates_text(child.text)
                    if coords:
                        return Point(coords[0])
            return None

        elif tag == "LineString":
            for child in elem:
                if strip_tag(child.tag) == "coordinates":
                    coords = parse_coordinates_text(child.text)
                    if len(coords) >= 2:
                        return LineString(coords)
            return None

        elif tag == "Polygon":
            exterior_coords: list[tuple[float, float]] = []
            interiors: list[list[tuple[float, float]]] = []

            for child in elem:
                ctag = strip_tag(child.tag)
                if ctag == "outerBoundaryIs":
                    ring = next((c for c in child if strip_tag(c.tag) == "LinearRing"), None)
                    if ring is not None:
                        coords_elem = next(
                            (c for c in ring if strip_tag(c.tag) == "coordinates"), None
                        )
                        if coords_elem is not None and coords_elem.text:
                            exterior_coords = parse_coordinates_text(coords_elem.text)
                elif ctag == "innerBoundaryIs":
                    ring = next((c for c in child if strip_tag(c.tag) == "LinearRing"), None)
                    if ring is not None:
                        coords_elem = next(
                            (c for c in ring if strip_tag(c.tag) == "coordinates"), None
                        )
                        if coords_elem is not None and coords_elem.text:
                            int_coords = parse_coordinates_text(coords_elem.text)
                            if len(int_coords) >= 3:
                                interiors.append(int_coords)

            if len(exterior_coords) >= 3:
                return Polygon(exterior_coords, interiors)
            return None

        elif tag == "MultiGeometry":
            sub_geoms: list[BaseGeometry] = []
            for child in elem:
                sub_geom = self._parse_geometry_element(child)
                if sub_geom is not None:
                    sub_geoms.append(sub_geom)

            if not sub_geoms:
                return None

            # Determine composite type if homogeneous
            if all(isinstance(g, Polygon) for g in sub_geoms):
                return MultiPolygon(sub_geoms)  # type: ignore
            elif all(isinstance(g, LineString) for g in sub_geoms):
                return MultiLineString(sub_geoms)  # type: ignore
            elif all(isinstance(g, Point) for g in sub_geoms):
                return MultiPoint(sub_geoms)  # type: ignore
            return GeometryCollection(sub_geoms)

        return None
