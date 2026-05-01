"""BridgeSync - FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.db import Base, engine
from app.services.demo_views_service import ensure_demo_views
from app.api.routes import (
    health_router,
    sources_router,
    destinations_router,
    syncs_router,
    runs_router,
    customers_router,
    segments_router,
    activations_router,
    explorer_router,
    c360_router,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting BridgeSync", env=settings.app_env)
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Ensure demo-safe SQL views are available for Explorer.
    try:
        if engine.dialect.name != "sqlite":
            ensure_demo_views()
            logger.info("Demo-safe views ensured")
    except Exception as e:
        logger.warning("Failed to ensure demo-safe views", error=str(e))
    
    # Initialize DuckDB with sample data for dev
    if settings.app_env == "development" and settings.warehouse_mode == "duckdb":
        try:
            from app.adapters.sources.duckdb_adapter import DuckDBAdapter
            from app.adapters.sources.base import SourceConfig
            
            config = SourceConfig(duckdb_path=settings.duckdb_path)
            adapter = DuckDBAdapter(config)
            adapter.connect()
            adapter.init_sample_data()
            adapter.disconnect()
            logger.info("Sample data initialized in DuckDB")
        except Exception as e:
            logger.warning("Failed to initialize sample data", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down BridgeSync")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Production Reverse ETL Platform - Sync data from warehouse to marketing tools",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(sources_router, prefix=settings.api_prefix)
app.include_router(destinations_router, prefix=settings.api_prefix)
app.include_router(syncs_router, prefix=settings.api_prefix)
app.include_router(runs_router, prefix=settings.api_prefix)
app.include_router(customers_router, prefix=settings.api_prefix)
app.include_router(segments_router, prefix=settings.api_prefix)
app.include_router(activations_router, prefix=settings.api_prefix)
app.include_router(explorer_router, prefix=settings.api_prefix)
app.include_router(c360_router, prefix=settings.api_prefix)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": f"{settings.api_prefix}/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
