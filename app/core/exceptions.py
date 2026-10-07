from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base class for application exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class FileNotFoundAppException(AppException):
    """Raised when a requested resource or file is not found."""

    def __init__(
        self, message: str = "Requested file not found", details: dict[str, Any] | None = None
    ):
        super().__init__(
            message=message,
            code="FILE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnsupportedFileTypeException(AppException):
    """Raised when an uploaded file is not a supported format."""

    def __init__(
        self,
        message: str = "Only KML and Shapefile ZIP files are supported.",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code="UNSUPPORTED_FILE_TYPE",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FileValidationException(AppException):
    """Raised when file validation fails (e.g. invalid zip, malicious entries, oversized)."""

    def __init__(
        self,
        message: str,
        code: str = "FILE_VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ParsingException(AppException):
    """Raised when geospatial file parsing fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="PARSING_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class CRSError(AppException):
    """Raised when CRS detection, validation, or transformation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="CRS_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers standard JSON exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload.",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        # Prevent leaking raw unhandled python stack traces while logging
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the request.",
                    "details": {"error_type": exc.__class__.__name__},
                }
            },
        )
