"""Source connection API routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas.connection import (
    SourceConnectionCreate, SourceConnectionUpdate, SourceConnectionResponse,
    SourceConnectionTestResult, TableInfo, TableSchema,
)
from ...services.connection_service import ConnectionService
from ...core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=List[SourceConnectionResponse])
def list_sources(
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all source connections."""
    service = ConnectionService(db)
    return service.list_source_connections(active_only=active_only)


@router.post("", response_model=SourceConnectionResponse, status_code=201)
def create_source(
    data: SourceConnectionCreate,
    db: Session = Depends(get_db),
):
    """Create a new source connection."""
    service = ConnectionService(db)
    
    # Check for duplicate name
    existing = service.get_source_connection_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Source connection '{data.name}' already exists")
    
    return service.create_source_connection(data)


@router.get("/{connection_id}", response_model=SourceConnectionResponse)
def get_source(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Get a source connection by ID."""
    service = ConnectionService(db)
    conn = service.get_source_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection not found")
    return conn


@router.put("/{connection_id}", response_model=SourceConnectionResponse)
def update_source(
    connection_id: int,
    data: SourceConnectionUpdate,
    db: Session = Depends(get_db),
):
    """Update a source connection."""
    service = ConnectionService(db)
    conn = service.update_source_connection(connection_id, data)
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection not found")
    return conn


@router.delete("/{connection_id}")
def delete_source(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Delete a source connection."""
    service = ConnectionService(db)
    if not service.delete_source_connection(connection_id):
        raise HTTPException(status_code=404, detail="Source connection not found")
    return {"message": "Source connection deleted"}


@router.post("/{connection_id}/test", response_model=SourceConnectionTestResult)
def test_source(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Test a source connection."""
    service = ConnectionService(db)
    return service.test_source_connection(connection_id)


@router.get("/{connection_id}/schemas", response_model=List[str])
def get_schemas(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Get available schemas from source."""
    service = ConnectionService(db)
    conn = service.get_source_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection not found")
    
    try:
        return service.get_source_schemas(connection_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schemas: {str(e)}")


@router.get("/{connection_id}/schemas/{schema}/tables", response_model=List[TableInfo])
def get_tables(
    connection_id: int,
    schema: str,
    db: Session = Depends(get_db),
):
    """Get tables in a schema."""
    service = ConnectionService(db)
    conn = service.get_source_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection not found")
    
    try:
        return service.get_source_tables(connection_id, schema)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tables: {str(e)}")


@router.get("/{connection_id}/schemas/{schema}/tables/{table}", response_model=TableSchema)
def get_table_schema(
    connection_id: int,
    schema: str,
    table: str,
    db: Session = Depends(get_db),
):
    """Get table schema."""
    service = ConnectionService(db)
    conn = service.get_source_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection not found")
    
    try:
        result = service.get_source_table_schema(connection_id, schema, table)
        if not result:
            raise HTTPException(status_code=404, detail="Table not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get table schema: {str(e)}")
