import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class FileRecord(Base):
    """Represents an uploaded geospatial file and its processing lifecycle."""

    __tablename__ = "file_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'kml', 'shapefile'
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UPLOADED",
        index=True,
    )  # UPLOADED, PROCESSING, COMPLETED, COMPLETED_WITH_ERRORS, FAILED
    feature_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_crs: Mapped[str | None] = mapped_column(String(100), nullable=True)
    measurement_crs: Mapped[str | None] = mapped_column(String(100), nullable=True)

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    features: Mapped[list["FeatureRecord"]] = relationship(
        "FeatureRecord",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureRecord.feature_index",
    )


class FeatureRecord(Base):
    """Represents a discrete geospatial feature extracted from an uploaded file."""

    __tablename__ = "feature_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("file_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    geometry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    properties: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    measurement_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'area', 'length', None
    measurement_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    measurement_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'm²', 'm'
    measurement_crs: Mapped[str | None] = mapped_column(String(100), nullable=True)
    calculation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # SUCCESS, NOT_REQUIRED, REPAIRED, UNSUPPORTED, FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    file: Mapped["FileRecord"] = relationship("FileRecord", back_populates="features")
