from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shapely.geometry.base import BaseGeometry


@dataclass
class ParsedFeature:
    """Represents a feature parsed from a geospatial data file."""

    feature_index: int
    geometry_type: str
    geometry: BaseGeometry | None
    properties: dict[str, Any] = field(default_factory=dict)
    source_crs: str | None = None
    error_message: str | None = None


@dataclass
class ParsedDataset:
    """Represents the complete parsed contents of a geospatial data file."""

    detected_crs: str | None
    features: list[ParsedFeature]
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class GeoFileParser(ABC):
    """Abstract base class for all geospatial file parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDataset:
        """Parses a geospatial file and returns a structured ParsedDataset."""
        pass
