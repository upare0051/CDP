"""Destination connection API routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas.connection import (
    DestinationConnectionCreate, DestinationConnectionUpdate, DestinationConnectionResponse,
    DestinationConnectionTestResult,
)
from ...services.connection_service import ConnectionService
from ...core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("", response_model=List[DestinationConnectionResponse])
def list_destinations(
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all destination connections."""
    service = ConnectionService(db)
    connections = service.list_destination_connections(active_only=active_only)
    
    # Add masked API keys
    results = []
    for conn in connections:
        response = DestinationConnectionResponse.model_validate(conn)
        response.api_key_masked = service.get_masked_api_key(conn.id)
        results.append(response)
    
    return results


@router.post("", response_model=DestinationConnectionResponse, status_code=201)
def create_destination(
    data: DestinationConnectionCreate,
    db: Session = Depends(get_db),
):
    """Create a new destination connection."""
    service = ConnectionService(db)
    return service.create_destination_connection(data)


@router.get("/{connection_id}", response_model=DestinationConnectionResponse)
def get_destination(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Get a destination connection by ID."""
    service = ConnectionService(db)
    conn = service.get_destination_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Destination connection not found")
    
    response = DestinationConnectionResponse.model_validate(conn)
    response.api_key_masked = service.get_masked_api_key(connection_id)
    return response


@router.put("/{connection_id}", response_model=DestinationConnectionResponse)
def update_destination(
    connection_id: int,
    data: DestinationConnectionUpdate,
    db: Session = Depends(get_db),
):
    """Update a destination connection."""
    service = ConnectionService(db)
    conn = service.update_destination_connection(connection_id, data)
    if not conn:
        raise HTTPException(status_code=404, detail="Destination connection not found")
    return conn


@router.delete("/{connection_id}")
def delete_destination(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Delete a destination connection."""
    service = ConnectionService(db)
    if not service.delete_destination_connection(connection_id):
        raise HTTPException(status_code=404, detail="Destination connection not found")
    return {"message": "Destination connection deleted"}


@router.post("/{connection_id}/test", response_model=DestinationConnectionTestResult)
def test_destination(
    connection_id: int,
    db: Session = Depends(get_db),
):
    """Test a destination connection."""
    service = ConnectionService(db)
    return service.test_destination_connection(connection_id)


@router.get("/types/available")
def get_available_types():
    """Get available destination types."""
    return {
        "types": [
            {
                "id": "braze",
                "name": "Braze",
                "description": "Customer engagement platform",
                "required_fields": ["api_key", "api_endpoint"],
                "optional_fields": ["braze_app_id"],
            },
            {
                "id": "attentive",
                "name": "Attentive",
                "description": "SMS marketing platform",
                "required_fields": ["api_key"],
                "optional_fields": ["attentive_api_url"],
            },
        ]
    }
