from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import files, measurements
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger, setup_logging
from app.db.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle setup and teardown."""
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")

    if settings.ENVIRONMENT != "testing":
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database schema initialized.")
        except Exception as e:
            logger.warning(f"Could not connect to database on startup: {e}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-quality Geospatial File Measurement API for Aereo. "
        "Processes KML and Shapefile files, detects/reprojects CRS, validates and repairs geometries, "
        "and computes planar metric measurements (Polygon Area in m², LineString Length in m)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Exception handlers
register_exception_handlers(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(files.router, prefix=settings.API_V1_PREFIX)
app.include_router(measurements.router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"], summary="System health check")
async def health_check() -> dict[str, str]:
    """Returns application liveness and status."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
