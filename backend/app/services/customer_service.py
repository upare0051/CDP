"""Customer 360 profile service."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc, inspect, text

from ..models.customer import CustomerProfile, CustomerAttribute, CustomerEvent, CustomerIdentity
from ..models.connection import SourceConnection
from ..schemas.customer import (
    CustomerProfileCreate, CustomerProfileUpdate, CustomerProfileSummary, CustomerProfileDetail,
    CustomerAttributeResponse, CustomerEventResponse, CustomerIdentityResponse,
    CustomerListResponse, CustomerStats, ProfileBuildResult,
)
from ..core.logging import get_logger

logger = get_logger(__name__)


class CustomerService:
    """Service for managing Customer 360 profiles."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============ Profile CRUD ============
    
    def get_customer(self, customer_id: int) -> Optional[CustomerProfile]:
        """Get customer profile by ID."""
        return self.db.query(CustomerProfile).filter(CustomerProfile.id == customer_id).first()
    
    def get_customer_by_external_id(self, external_id: str) -> Optional[CustomerProfile]:
        """Get customer profile by external ID."""
        return self.db.query(CustomerProfile).filter(CustomerProfile.external_id == external_id).first()
    
    def create_customer(self, data: CustomerProfileCreate) -> CustomerProfile:
        """Create a new customer profile."""
        customer = CustomerProfile(
            external_id=data.external_id,
            email=data.email,
            phone=data.phone,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        
        # Create initial event
        self._create_event(
            customer_id=customer.id,
            event_type="profile_created",
            title="Profile Created",
            description=f"Customer profile created with external_id: {data.external_id}",
        )
        
        logger.info("Created customer profile", customer_id=customer.id, external_id=data.external_id)
        return customer
    
    def update_customer(self, customer_id: int, data: CustomerProfileUpdate) -> Optional[CustomerProfile]:
        """Update a customer profile."""
        customer = self.get_customer(customer_id)
        if not customer:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)
        
        self.db.commit()
        self.db.refresh(customer)
        return customer
    
    # ============ Customer List & Search ============
    
    def list_customers(
        self,
        search: Optional[str] = None,
        source_id: Optional[int] = None,
        sort_by: str = "last_seen_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> CustomerListResponse:
        """List customers with search and pagination."""
        if source_id is None and self._has_table("mart_customer_360"):
            return self._list_customers_from_mart(
                search=search,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                page_size=page_size,
            )

        query = self.db.query(CustomerProfile)
        
        # Search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CustomerProfile.external_id.ilike(search_term),
                    CustomerProfile.email.ilike(search_term),
                    CustomerProfile.first_name.ilike(search_term),
                    CustomerProfile.last_name.ilike(search_term),
                    CustomerProfile.phone.ilike(search_term),
                )
            )
        
        # Source filter (via identities)
        if source_id:
            query = query.join(CustomerIdentity).filter(
                CustomerIdentity.source_connection_id == source_id
            ).distinct()
        
        # Get total count
        total = query.count()
        
        # Sorting
        sort_column = getattr(CustomerProfile, sort_by, CustomerProfile.last_seen_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Pagination
        offset = (page - 1) * page_size
        customers = query.offset(offset).limit(page_size).all()
        
        # Convert to summaries with key attributes
        summaries = [self._to_summary(c) for c in customers]
        
        return CustomerListResponse(
            customers=summaries,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )

    def _list_customers_from_mart(
        self,
        search: Optional[str],
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> CustomerListResponse:
        """List customers from dbt mart with pagination and search."""
        sortable_fields = {
            "id": "customer_id",
            "customer_id": "customer_id",
            "external_id": "external_id",
            "email": "email",
            "first_name": "first_name",
            "last_name": "last_name",
            "last_seen_at": "last_seen_at",
            "first_seen_at": "first_seen_at",
            "lifetime_value": "lifetime_value",
            "total_orders": "total_orders",
            "created_at": "created_at",
            "updated_at": "updated_at",
        }
        sort_column = sortable_fields.get(sort_by, "last_seen_at")
        sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        where_clause = ""
        params: Dict[str, Any] = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if search:
            where_clause = """
                WHERE external_id ILIKE :search
                   OR email ILIKE :search
                   OR first_name ILIKE :search
                   OR last_name ILIKE :search
                   OR phone ILIKE :search
                   OR full_name ILIKE :search
            """
            params["search"] = f"%{search}%"

        total_query = text(f"SELECT count(*) FROM mart_customer_360 {where_clause}")
        total = self.db.execute(total_query, params).scalar() or 0

        rows_query = text(
            f"""
            SELECT
                customer_id,
                external_id,
                email,
                phone,
                first_name,
                last_name,
                full_name,
                source_count,
                first_seen_at,
                last_seen_at,
                last_synced_at,
                lifetime_value,
                total_orders,
                city,
                country
            FROM mart_customer_360
            {where_clause}
            ORDER BY {sort_column} {sort_direction}
            LIMIT :limit OFFSET :offset
            """
        )
        rows = self.db.execute(rows_query, params).mappings().all()

        customers = [
            CustomerProfileSummary(
                id=int(r["customer_id"]),
                external_id=r["external_id"],
                email=r["email"],
                phone=r["phone"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                full_name=r["full_name"] or "Unknown",
                source_count=int(r["source_count"] or 1),
                first_seen_at=r["first_seen_at"],
                last_seen_at=r["last_seen_at"],
                last_synced_at=r["last_synced_at"],
                lifetime_value=float(r["lifetime_value"]) if r["lifetime_value"] is not None else None,
                total_orders=int(float(r["total_orders"])) if r["total_orders"] is not None else None,
                city=r["city"],
                country=r["country"],
            )
            for r in rows
        ]

        return CustomerListResponse(
            customers=customers,
            total=int(total),
            page=page,
            page_size=page_size,
            total_pages=(int(total) + page_size - 1) // page_size,
        )
    
    def _to_summary(self, customer: CustomerProfile) -> CustomerProfileSummary:
        """Convert customer to summary with key attributes."""
        # Get key attributes
        attrs = {a.attribute_name: a.attribute_value for a in customer.attributes}
        
        return CustomerProfileSummary(
            id=customer.id,
            external_id=customer.external_id,
            email=customer.email,
            phone=customer.phone,
            first_name=customer.first_name,
            last_name=customer.last_name,
            full_name=customer.full_name,
            source_count=customer.source_count,
            first_seen_at=customer.first_seen_at,
            last_seen_at=customer.last_seen_at,
            last_synced_at=customer.last_synced_at,
            lifetime_value=self._parse_float(attrs.get("lifetime_value") or attrs.get("ltv")),
            total_orders=self._parse_int(attrs.get("total_orders")),
            city=attrs.get("city") or attrs.get("home_city"),
            country=attrs.get("country"),
        )
    
    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Safely parse float from string, handling NaN."""
        if value is None:
            return None
        try:
            result = float(value)
            # Check for NaN or infinity
            if result != result or result == float('inf') or result == float('-inf'):
                return None
            return result
        except (ValueError, TypeError):
            return None
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Safely parse int from string."""
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    # ============ Customer Detail ============
    
    def get_customer_detail(self, customer_id: int) -> Optional[CustomerProfileDetail]:
        """Get full customer detail with attributes and events."""
        customer = self.get_customer(customer_id)
        if not customer:
            return None
        
        summary = self._to_summary(customer)
        
        # Get attributes with source names
        attributes = []
        for attr in customer.attributes:
            attr_response = CustomerAttributeResponse(
                id=attr.id,
                customer_id=attr.customer_id,
                attribute_name=attr.attribute_name,
                attribute_value=attr.attribute_value,
                attribute_type=attr.attribute_type,
                source_connection_id=attr.source_connection_id,
                source_field=attr.source_field,
                source_name=attr.source_connection.name if attr.source_connection else None,
                created_at=attr.created_at,
                updated_at=attr.updated_at,
            )
            attributes.append(attr_response)
        
        # Get recent events (last 50)
        recent_events = []
        for event in customer.events[:50]:
            event_response = CustomerEventResponse(
                id=event.id,
                customer_id=event.customer_id,
                event_type=event.event_type,
                event_category=event.event_category,
                title=event.title,
                description=event.description,
                event_data=event.event_data,
                source_connection_id=event.source_connection_id,
                destination_connection_id=event.destination_connection_id,
                sync_run_id=event.sync_run_id,
                occurred_at=event.occurred_at,
                source_name=event.source_connection.name if event.source_connection else None,
                destination_name=event.destination_connection.name if event.destination_connection else None,
            )
            recent_events.append(event_response)
        
        # Get identities
        identities = []
        for identity in customer.identities:
            identity_response = CustomerIdentityResponse(
                id=identity.id,
                identity_type=identity.identity_type,
                identity_value=identity.identity_value,
                source_connection_id=identity.source_connection_id,
                source_name=identity.source_connection.name if identity.source_connection else None,
                is_primary=bool(identity.is_primary),
                verified=bool(identity.verified),
                created_at=identity.created_at,
            )
            identities.append(identity_response)
        
        return CustomerProfileDetail(
            **summary.model_dump(),
            attributes=attributes,
            recent_events=recent_events,
            identities=identities,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
    
    # ============ Timeline ============
    
    def get_customer_timeline(
        self,
        customer_id: int,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[CustomerEventResponse]:
        """Get customer event timeline."""
        query = self.db.query(CustomerEvent).filter(CustomerEvent.customer_id == customer_id)
        
        if event_type:
            query = query.filter(CustomerEvent.event_type == event_type)
        
        events = query.order_by(desc(CustomerEvent.occurred_at)).limit(limit).all()
        
        return [
            CustomerEventResponse(
                id=e.id,
                customer_id=e.customer_id,
                event_type=e.event_type,
                event_category=e.event_category,
                title=e.title,
                description=e.description,
                event_data=e.event_data,
                source_connection_id=e.source_connection_id,
                destination_connection_id=e.destination_connection_id,
                sync_run_id=e.sync_run_id,
                occurred_at=e.occurred_at,
                source_name=e.source_connection.name if e.source_connection else None,
                destination_name=e.destination_connection.name if e.destination_connection else None,
            )
            for e in events
        ]
    
    # ============ Stats ============
    
    def get_stats(self) -> CustomerStats:
        """Get customer statistics for dashboard."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        if self._has_table("mart_customer_360"):
            total = self.db.execute(text("SELECT count(*) FROM mart_customer_360")).scalar() or 0
            added_today = self.db.execute(
                text("SELECT count(*) FROM mart_customer_360 WHERE created_at >= :today_start"),
                {"today_start": today_start},
            ).scalar() or 0
            added_this_week = self.db.execute(
                text("SELECT count(*) FROM mart_customer_360 WHERE created_at >= :week_start"),
                {"week_start": week_start},
            ).scalar() or 0
            synced_today = self.db.execute(
                text("SELECT count(*) FROM mart_customer_360 WHERE last_synced_at >= :today_start"),
                {"today_start": today_start},
            ).scalar() or 0
        else:
            total = self.db.query(CustomerProfile).count()
            added_today = self.db.query(CustomerProfile).filter(
                CustomerProfile.created_at >= today_start
            ).count()
            added_this_week = self.db.query(CustomerProfile).filter(
                CustomerProfile.created_at >= week_start
            ).count()
            synced_today = self.db.query(CustomerProfile).filter(
                CustomerProfile.last_synced_at >= today_start
            ).count()
        
        # Average attributes per customer
        attr_count = self.db.query(CustomerAttribute).count()
        avg_attrs = attr_count / total if total > 0 else 0
        
        # Top sources by customer count
        top_sources = self.db.query(
            SourceConnection.name,
            func.count(CustomerIdentity.id).label("customer_count")
        ).join(
            CustomerIdentity, CustomerIdentity.source_connection_id == SourceConnection.id
        ).group_by(
            SourceConnection.name
        ).order_by(
            desc("customer_count")
        ).limit(5).all()
        
        return CustomerStats(
            total_customers=total,
            customers_added_today=added_today,
            customers_added_this_week=added_this_week,
            customers_synced_today=synced_today,
            avg_attributes_per_customer=round(avg_attrs, 1),
            top_sources=[{"source_name": s[0], "customer_count": s[1]} for s in top_sources],
        )

    def _has_table(self, table_name: str) -> bool:
        """Check if a table/view exists in the current DB."""
        try:
            inspector = inspect(self.db.bind)
            return bool(inspector.has_table(table_name))
        except Exception:
            return False
    
    # ============ Profile Builder ============
    
    def build_profiles_from_sync(
        self,
        records: List[Dict[str, Any]],
        source_connection_id: int,
        sync_run_id: str,
        sync_key: str = "external_id",
    ) -> ProfileBuildResult:
        """
        Build/update customer profiles from synced records.
        This is called after each sync run completes.
        """
        profiles_created = 0
        profiles_updated = 0
        attributes_added = 0
        events_created = 0
        errors = []
        
        source = self.db.query(SourceConnection).filter(SourceConnection.id == source_connection_id).first()
        source_name = source.name if source else "Unknown"
        
        for record in records:
            try:
                # Get the sync key value
                external_id = record.get(sync_key)
                if not external_id:
                    errors.append(f"Record missing sync key '{sync_key}'")
                    continue
                
                external_id = str(external_id)
                
                # Find or create customer profile
                customer = self.get_customer_by_external_id(external_id)
                is_new = customer is None
                
                if is_new:
                    customer = CustomerProfile(
                        external_id=external_id,
                        email=record.get("email"),
                        phone=record.get("phone"),
                        first_name=record.get("first_name"),
                        last_name=record.get("last_name"),
                    )
                    self.db.add(customer)
                    self.db.flush()
                    profiles_created += 1
                else:
                    # Update core fields if provided
                    if record.get("email"):
                        customer.email = record["email"]
                    if record.get("phone"):
                        customer.phone = record["phone"]
                    if record.get("first_name"):
                        customer.first_name = record["first_name"]
                    if record.get("last_name"):
                        customer.last_name = record["last_name"]
                    profiles_updated += 1
                
                # Update last synced
                customer.last_synced_at = datetime.utcnow()
                customer.last_seen_at = datetime.utcnow()
                
                # Add/update attributes for all fields
                core_fields = {"external_id", "email", "phone", "first_name", "last_name", sync_key}
                for field_name, value in record.items():
                    if field_name in core_fields or value is None:
                        continue
                    
                    # Find existing attribute
                    existing_attr = self.db.query(CustomerAttribute).filter(
                        CustomerAttribute.customer_id == customer.id,
                        CustomerAttribute.attribute_name == field_name,
                    ).first()
                    
                    str_value = str(value) if value is not None else None
                    attr_type = self._infer_type(value)
                    
                    if existing_attr:
                        existing_attr.attribute_value = str_value
                        existing_attr.attribute_type = attr_type
                        existing_attr.updated_at = datetime.utcnow()
                    else:
                        new_attr = CustomerAttribute(
                            customer_id=customer.id,
                            attribute_name=field_name,
                            attribute_value=str_value,
                            attribute_type=attr_type,
                            source_connection_id=source_connection_id,
                            source_field=field_name,
                        )
                        self.db.add(new_attr)
                        attributes_added += 1
                
                # Add/update identity
                existing_identity = self.db.query(CustomerIdentity).filter(
                    CustomerIdentity.customer_id == customer.id,
                    CustomerIdentity.identity_type == "external_id",
                    CustomerIdentity.source_connection_id == source_connection_id,
                ).first()
                
                if not existing_identity:
                    identity = CustomerIdentity(
                        customer_id=customer.id,
                        identity_type="external_id",
                        identity_value=external_id,
                        source_connection_id=source_connection_id,
                        is_primary=1 if is_new else 0,
                    )
                    self.db.add(identity)
                
                # Create sync event
                event = CustomerEvent(
                    customer_id=customer.id,
                    event_type="synced_from_source",
                    event_category="sync",
                    title=f"Synced from {source_name}",
                    description=f"Profile {'created' if is_new else 'updated'} from sync",
                    event_data={"sync_run_id": sync_run_id, "source_id": source_connection_id},
                    source_connection_id=source_connection_id,
                    sync_run_id=sync_run_id,
                )
                self.db.add(event)
                events_created += 1
                
            except Exception as e:
                errors.append(f"Error processing record: {str(e)}")
                logger.error("Profile build error", error=str(e), record=record)
        
        # Update source counts
        self._update_source_counts()
        
        self.db.commit()
        
        logger.info(
            "Profile build completed",
            profiles_created=profiles_created,
            profiles_updated=profiles_updated,
            attributes_added=attributes_added,
        )
        
        return ProfileBuildResult(
            profiles_created=profiles_created,
            profiles_updated=profiles_updated,
            attributes_added=attributes_added,
            events_created=events_created,
            errors=errors,
        )
    
    def _infer_type(self, value: Any) -> str:
        """Infer attribute type from value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "number"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, dict) or isinstance(value, list):
            return "json"
        else:
            return "string"
    
    def _update_source_counts(self):
        """Update source_count for all customers."""
        # This could be optimized with a subquery, but keeping simple for now
        customers = self.db.query(CustomerProfile).all()
        for customer in customers:
            source_count = self.db.query(CustomerIdentity).filter(
                CustomerIdentity.customer_id == customer.id
            ).distinct(CustomerIdentity.source_connection_id).count()
            customer.source_count = max(source_count, 1)
    
    def _create_event(
        self,
        customer_id: int,
        event_type: str,
        title: str,
        description: Optional[str] = None,
        event_data: Optional[Dict] = None,
        source_connection_id: Optional[int] = None,
        destination_connection_id: Optional[int] = None,
        sync_run_id: Optional[str] = None,
    ) -> CustomerEvent:
        """Create a customer event."""
        event = CustomerEvent(
            customer_id=customer_id,
            event_type=event_type,
            title=title,
            description=description,
            event_data=event_data,
            source_connection_id=source_connection_id,
            destination_connection_id=destination_connection_id,
            sync_run_id=sync_run_id,
        )
        self.db.add(event)
        self.db.commit()
        return event
