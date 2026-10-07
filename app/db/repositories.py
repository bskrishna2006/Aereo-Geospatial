import uuid
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FeatureRecord, FileRecord


class FileRepository:
    """Repository handling persistence operations for FileRecord."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs: Any) -> FileRecord:
        record = FileRecord(**kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_id(self, file_id: uuid.UUID) -> FileRecord | None:
        stmt = select(FileRecord).where(FileRecord.id == file_id)
        return self.db.scalars(stmt).first()

    def update(self, record: FileRecord, **kwargs: Any) -> FileRecord:
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_files(self, skip: int = 0, limit: int = 50) -> Sequence[FileRecord]:
        stmt = select(FileRecord).order_by(FileRecord.created_at.desc()).offset(skip).limit(limit)
        return self.db.scalars(stmt).all()


class FeatureRepository:
    """Repository handling persistence operations for FeatureRecord."""

    def __init__(self, db: Session):
        self.db = db

    def bulk_create(self, features_data: list[dict[str, Any]]) -> None:
        """High-performance bulk insertion of features."""
        if not features_data:
            return
        records = [FeatureRecord(**data) for data in features_data]
        self.db.bulk_save_objects(records)
        self.db.commit()

    def get_by_file_id(
        self,
        file_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> Sequence[FeatureRecord]:
        stmt = select(FeatureRecord).where(FeatureRecord.file_id == file_id)
        if status_filter:
            stmt = stmt.where(FeatureRecord.processing_status == status_filter)
        stmt = stmt.order_by(FeatureRecord.feature_index.asc()).offset(skip).limit(limit)
        return self.db.scalars(stmt).all()

    def count_by_file_id(self, file_id: uuid.UUID, status_filter: str | None = None) -> int:
        stmt = select(func.count(FeatureRecord.id)).where(FeatureRecord.file_id == file_id)
        if status_filter:
            stmt = stmt.where(FeatureRecord.processing_status == status_filter)
        return self.db.scalar(stmt) or 0
