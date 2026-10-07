from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.file_service import FileService


def get_file_service(db: Session = Depends(get_db)) -> FileService:
    """Dependency provider for FileService."""
    return FileService(db)
