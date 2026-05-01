"""Data Explorer API routes."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.explorer_service import ExplorerService

router = APIRouter(prefix="/explorer", tags=["explorer"])


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    limit: int = Field(default=500, ge=1, le=5000)


@router.get("/schema")
def get_schema_tree():
    service = ExplorerService()
    return service.get_schema_tree()


@router.get("/erd")
def get_erd_hints():
    service = ExplorerService()
    return service.get_erd_hints()


@router.get("/team-views")
def get_team_views():
    service = ExplorerService()
    return service.get_team_views()


@router.post("/query")
def run_query(request: QueryRequest):
    service = ExplorerService()
    try:
        result = service.execute_read_query(request.sql, request.limit)
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
