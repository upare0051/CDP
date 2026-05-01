"""Health check endpoints - Cloud-agnostic service health."""

from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from ...db import get_db
from ...core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


def _duckdb_freshness() -> dict:
    """Return freshness metadata for dbt DuckDB file."""
    duckdb_path = Path(settings.dbt_duckdb_path)
    if not duckdb_path.exists():
        return {
            "path": str(duckdb_path),
            "exists": False,
            "last_modified_at": None,
            "last_modified_age_seconds": None,
            "file_size_bytes": None,
        }

    modified_at = datetime.fromtimestamp(duckdb_path.stat().st_mtime, tz=timezone.utc)
    age_seconds = int((datetime.now(timezone.utc) - modified_at).total_seconds())
    return {
        "path": str(duckdb_path),
        "exists": True,
        "last_modified_at": modified_at.isoformat(),
        "last_modified_age_seconds": age_seconds,
        "file_size_bytes": duckdb_path.stat().st_size,
    }


@router.get("")
def health_check():
    """
    Basic health check.
    
    Returns basic service info. Use /health/full for complete status.
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@router.get("/db")
def db_health_check(db: Session = Depends(get_db)):
    """Database health check."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@router.get("/redis")
def redis_health_check():
    """Redis cache health check."""
    try:
        from ...services.cache import get_cache
        cache = get_cache()
        if cache.ping():
            return {"status": "healthy", "redis": "connected"}
        return {"status": "unhealthy", "redis": "ping failed"}
    except Exception as e:
        return {"status": "unhealthy", "redis": "disconnected", "error": str(e)}


@router.get("/storage")
def storage_health_check():
    """S3-compatible storage health check."""
    try:
        from ...services.storage import get_storage_client
        storage = get_storage_client()
        if storage.ensure_bucket_exists():
            return {"status": "healthy", "storage": "connected", "bucket": settings.storage_bucket}
        return {"status": "unhealthy", "storage": "bucket check failed"}
    except Exception as e:
        return {"status": "unhealthy", "storage": "disconnected", "error": str(e)}


@router.get("/dbt")
def dbt_health_check(db: Session = Depends(get_db)):
    """
    dbt mart health check.

    Verifies whether key marts exist and reports row counts.
    """
    required_marts = [
        "mart_customer_360",
        "mart_segment_base",
        "mart_activation_performance",
    ]
    try:
        inspector = inspect(db.bind)
        mart_status = {}
        overall = "healthy"

        for mart in required_marts:
            exists = bool(inspector.has_table(mart))
            row_count = None
            if exists:
                row_count = db.execute(text(f"SELECT count(*) FROM {mart}")).scalar()
            else:
                overall = "degraded"

            mart_status[mart] = {
                "exists": exists,
                "row_count": int(row_count or 0) if exists else 0,
            }

        duckdb = _duckdb_freshness()
        if not duckdb["exists"]:
            overall = "degraded"

        return {
            "status": overall,
            "dbt": {
                "project": "activationos_transform",
                "required_marts": mart_status,
                "duckdb_file": duckdb,
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "dbt": {"error": str(e)},
        }


@router.get("/full")
def full_health_check(db: Session = Depends(get_db)):
    """
    Full health check for all services.
    
    Checks: Database, Redis, Storage
    """
    health = {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
        "checks": {}
    }
    
    # Database check
    try:
        db.execute(text("SELECT 1"))
        health["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    # Redis check
    try:
        from ...services.cache import get_cache
        cache = get_cache()
        if cache.ping():
            health["checks"]["redis"] = {"status": "healthy"}
        else:
            health["checks"]["redis"] = {"status": "unhealthy", "error": "ping failed"}
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        # Redis failure is not critical
        if health["status"] == "healthy":
            health["status"] = "degraded"
    
    # Storage check
    try:
        from ...services.storage import get_storage_client
        storage = get_storage_client()
        if storage.ensure_bucket_exists():
            health["checks"]["storage"] = {"status": "healthy", "bucket": settings.storage_bucket}
        else:
            health["checks"]["storage"] = {"status": "unhealthy", "error": "bucket check failed"}
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["storage"] = {"status": "unhealthy", "error": str(e)}
        # Storage failure is not critical
        if health["status"] == "healthy":
            health["status"] = "degraded"
    
    # Ask C360 / NL→SQL (Ollama host process)
    health["checks"]["ai"] = {
        "status": "configured",
        "provider": "ollama",
        "base_url": settings.ollama_base_url,
        "model": settings.ollama_model,
    }

    # dbt marts check (non-critical)
    try:
        inspector = inspect(db.bind)
        marts = ["mart_customer_360", "mart_segment_base", "mart_activation_performance"]
        missing = [m for m in marts if not inspector.has_table(m)]
        duckdb = _duckdb_freshness()
        health["checks"]["dbt"] = {
            "status": "healthy" if not missing else "degraded",
            "missing_marts": missing,
            "duckdb_file": duckdb,
        }
        if (missing or not duckdb["exists"]) and health["status"] == "healthy":
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["dbt"] = {"status": "unhealthy", "error": str(e)}
        if health["status"] == "healthy":
            health["status"] = "degraded"
    
    return health
