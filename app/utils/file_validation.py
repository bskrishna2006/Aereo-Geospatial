import os
import zipfile
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileValidationException, UnsupportedFileTypeException

SUPPORTED_EXTENSIONS = {".kml", ".zip"}
REQUIRED_SHP_EXTENSIONS = {".shp", ".shx", ".dbf"}


def validate_file_extension(filename: str) -> str:
    """Validates the uploaded file extension and returns the normalized format ('kml' or 'shapefile')."""
    ext = Path(filename).suffix.lower()
    if ext == ".kml":
        return "kml"
    elif ext == ".zip":
        return "shapefile"
    else:
        raise UnsupportedFileTypeException(
            message=f"Unsupported file format '{ext}'. Only .kml and .zip (containing Shapefile) are supported.",
            details={
                "supported_extensions": list(SUPPORTED_EXTENSIONS),
                "provided_filename": filename,
            },
        )


def validate_file_size(file: UploadFile) -> int:
    """Validates that the uploaded file does not exceed MAX_UPLOAD_SIZE_MB."""
    # Seek to end to determine size
    file.file.seek(0, os.SEEK_END)
    size_bytes = file.file.tell()
    file.file.seek(0)

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileValidationException(
            message=f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            code="FILE_TOO_LARGE",
            details={"file_size_bytes": size_bytes, "max_allowed_bytes": max_bytes},
        )
    if size_bytes == 0:
        raise FileValidationException(
            message="Uploaded file is empty (0 bytes).",
            code="EMPTY_FILE",
        )
    return size_bytes


def validate_content_signature(file_stream: BinaryIO, file_type: str) -> None:
    """Performs magic byte / signature check on the uploaded file stream."""
    file_stream.seek(0)
    header = file_stream.read(1024)
    file_stream.seek(0)

    if file_type == "shapefile":
        # ZIP magic signature: 'PK\x03\x04' or 'PK\x05\x06' (empty zip) or 'PK\x07\x08' (spanned)
        if not (header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06")):
            raise FileValidationException(
                message="File has .zip extension but does not contain a valid ZIP archive signature.",
                code="INVALID_ZIP_SIGNATURE",
            )
    elif file_type == "kml":
        # KML is XML; check for XML declaration or <kml tag (ascii / utf-8 / utf-16)
        lower_header = header.lower()
        if not (b"<?xml" in lower_header or b"<kml" in lower_header):
            raise FileValidationException(
                message="File has .kml extension but does not contain valid XML/KML content.",
                code="INVALID_KML_SIGNATURE",
            )


def safe_extract_zip(zip_path: Path, target_dir: Path) -> Path:
    """Safely extracts a ZIP archive preventing Zip Slip, zip bombs, and validating Shapefile components.

    Returns the path to the primary .shp file.
    """
    if not zipfile.is_zipfile(zip_path):
        raise FileValidationException(
            message="Uploaded file is not a valid ZIP archive.",
            code="CORRUPTED_ZIP",
        )

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Check zip bomb (compression ratio)
        compressed_size = os.path.getsize(zip_path)
        total_uncompressed = 0

        for member in zf.infolist():
            total_uncompressed += member.file_size
            # Path traversal / Zip Slip prevention
            # Resolve destination path
            member_path = Path(member.filename)
            # Disallow absolute paths or paths containing '..'
            if member_path.is_absolute() or ".." in member_path.parts:
                raise FileValidationException(
                    message=f"Potentially malicious ZIP entry detected: '{member.filename}'. Path traversal attempt blocked.",
                    code="ZIP_SLIP_ATTEMPT",
                )

        if compressed_size > 0:
            ratio = total_uncompressed / compressed_size
            if ratio > settings.MAX_UNCOMPRESSED_RATIO:
                raise FileValidationException(
                    message="ZIP file rejected: possible zip bomb (excessive uncompressed-to-compressed ratio).",
                    code="ZIP_BOMB_DETECTED",
                    details={"ratio": ratio, "max_ratio": settings.MAX_UNCOMPRESSED_RATIO},
                )

        # Extract safely into target directory
        resolved_target = target_dir.resolve()
        for member in zf.infolist():
            dest = (target_dir / member.filename).resolve()
            # Ensure dest is within target_dir
            try:
                dest.relative_to(resolved_target)
            except ValueError:
                raise FileValidationException(
                    message=f"Potentially malicious path in ZIP entry: '{member.filename}'.",
                    code="ZIP_SLIP_ATTEMPT",
                )
            zf.extract(member, target_dir)

    # Search for shapefile components in the extracted files
    extracted_files = list(target_dir.rglob("*"))
    shapefile_bases: dict[str, set[str]] = {}

    for f in extracted_files:
        if f.is_file():
            ext = f.suffix.lower()
            base = f.stem.lower()
            if base not in shapefile_bases:
                shapefile_bases[base] = set()
            shapefile_bases[base].add(ext)

    # Find a base that has all required shapefile components (.shp, .shx, .dbf)
    valid_shp_path: Path | None = None
    for f in extracted_files:
        if f.is_file() and f.suffix.lower() == ".shp":
            base = f.stem.lower()
            present_exts = shapefile_bases.get(base, set())
            missing = REQUIRED_SHP_EXTENSIONS - present_exts
            if not missing:
                valid_shp_path = f
                break

    if not valid_shp_path:
        # Check what was found to provide helpful diagnostic error
        all_exts = {f.suffix.lower() for f in extracted_files if f.is_file()}
        missing = REQUIRED_SHP_EXTENSIONS - all_exts
        raise FileValidationException(
            message=f"ZIP does not contain a complete Shapefile bundle. Missing required files: {sorted(missing)}.",
            code="INCOMPLETE_SHAPEFILE",
            details={
                "required_components": list(REQUIRED_SHP_EXTENSIONS),
                "missing_components": list(missing),
            },
        )

    return valid_shp_path
