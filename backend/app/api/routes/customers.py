"""Customer 360 API routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...services.customer_service import CustomerService
from ...services.redshift_customer_service import RedshiftCustomerService
from ...core.config import get_settings
from ...schemas.customer import (
    CustomerListResponse, CustomerProfileDetail, CustomerProfileSummary,
    CustomerEventResponse, CustomerStats, ProfileBuildRequest, ProfileBuildResult,
)

router = APIRouter(prefix="/customers", tags=["customers"])
settings = get_settings()


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: Optional[str] = Query(None, description="Search in email, name, external_id"),
    source_id: Optional[int] = Query(None, description="Filter by source connection ID"),
    sort_by: str = Query("last_seen_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
):
    """
    List all customers with search and pagination.
    
    Returns a paginated list of customer profiles with key attributes.
    """
    if settings.warehouse_mode == "redshift":
        service = RedshiftCustomerService()
        return service.list_customers(search=search, page=page, page_size=page_size)

    service = CustomerService(db)
    return service.list_customers(
        search=search,
        source_id=source_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=CustomerStats)
def get_customer_stats(db: Session = Depends(get_db)):
    """
    Get customer statistics for dashboard.
    
    Returns counts and metrics about the customer base.
    """
    if settings.warehouse_mode == "redshift":
        service = RedshiftCustomerService()
        return service.get_stats()

    service = CustomerService(db)
    return service.get_stats()


@router.get("/{customer_id}", response_model=CustomerProfileDetail)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """
    Get full customer profile by ID.
    
    Returns the customer profile with all attributes, events, and identities.
    """
    if settings.warehouse_mode == "redshift":
        service = RedshiftCustomerService()
        customer = service.get_customer_detail(customer_id)
    else:
        service = CustomerService(db)
        customer = service.get_customer_detail(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/{customer_id}/timeline", response_model=List[CustomerEventResponse])
def get_customer_timeline(
    customer_id: int,
    limit: int = Query(100, ge=1, le=500, description="Max events to return"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    db: Session = Depends(get_db),
):
    """
    Get customer activity timeline.
    
    Returns a chronological list of events for the customer.
    """
    if settings.warehouse_mode == "redshift":
        service = RedshiftCustomerService()
        # If the customer doesn't exist in marts, return 404 for parity.
        if not service.get_customer_detail(customer_id):
            raise HTTPException(status_code=404, detail="Customer not found")
        return service.get_customer_timeline(customer_id=customer_id, limit=limit, event_type=event_type)

    service = CustomerService(db)
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return service.get_customer_timeline(customer_id=customer_id, limit=limit, event_type=event_type)


@router.post("/build-profiles", response_model=ProfileBuildResult)
def build_profiles(request: ProfileBuildRequest, db: Session = Depends(get_db)):
    """
    Build/update customer profiles from sync data.
    
    This endpoint is called internally after sync runs complete.
    It creates or updates customer profiles based on the synced records.
    """
    service = CustomerService(db)
    return service.build_profiles_from_sync(
        records=request.records,
        source_connection_id=request.source_connection_id,
        sync_run_id=request.sync_run_id,
        sync_key="external_id",  # TODO: Get from sync job
    )


@router.get("/by-external-id/{external_id}", response_model=CustomerProfileDetail)
def get_customer_by_external_id(external_id: str, db: Session = Depends(get_db)):
    """
    Get customer profile by external ID.
    
    Looks up a customer using their canonical external identifier.
    """
    service = CustomerService(db)
    customer = service.get_customer_by_external_id(external_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return service.get_customer_detail(customer.id)
