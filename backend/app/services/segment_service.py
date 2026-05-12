"""
Service for segment operations including query execution.
"""
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, cast, Float, String, text

from ..models.segment import (
    Segment, SegmentMembership, SegmentStatus, SegmentSourceType, SEGMENT_FIELDS,
)
from ..models.customer import CustomerProfile, CustomerAttribute
from ..schemas.segment import (
    SegmentCreate, SegmentUpdate, FilterConfig, FilterCondition,
    SegmentPreviewResponse
)
from ..core.logging import get_logger
from . import cube_client

logger = get_logger(__name__)


class SegmentService:
    """Service for managing segments and executing segment queries."""

    def __init__(self, db: Session):
        self.db = db

    def create_segment(self, data: SegmentCreate) -> Segment:
        """Create a new segment (legacy filter-based or Cube-defined)."""
        segment = Segment(
            name=data.name,
            description=data.description,
            source_type=data.source_type,
            filter_config=data.filter_config.model_dump() if data.filter_config else {"filters": [], "logic": "AND"},
            cube_query=data.cube_query,
            tags=data.tags,
            ai_generated=data.ai_generated,
            ai_prompt=data.ai_prompt,
            status=SegmentStatus.DRAFT.value,
        )
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)

        # Calculate initial count
        self._update_segment_count(segment)

        logger.info("Created segment", segment_id=segment.id, name=segment.name, source_type=segment.source_type)
        return segment

    def get_segment(self, segment_id: int) -> Optional[Segment]:
        """Get a segment by ID."""
        return self.db.query(Segment).filter(Segment.id == segment_id).first()

    def list_segments(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Segment], int]:
        """List segments with pagination and filtering."""
        query = self.db.query(Segment)
        
        if status:
            query = query.filter(Segment.status == status)
        
        if search:
            query = query.filter(
                or_(
                    Segment.name.ilike(f"%{search}%"),
                    Segment.description.ilike(f"%{search}%"),
                )
            )
        
        total = query.count()
        
        segments = (
            query
            .order_by(Segment.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        return segments, total

    def update_segment(self, segment_id: int, data: SegmentUpdate) -> Optional[Segment]:
        """Update an existing segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return None
        
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(segment, field, value)

        self.db.commit()
        self.db.refresh(segment)

        # Recalculate count if the audience definition changed.
        if {"filter_config", "cube_query", "source_type"} & set(update_data.keys()):
            self._update_segment_count(segment)

        logger.info("Updated segment", segment_id=segment.id, source_type=segment.source_type)
        return segment

    def delete_segment(self, segment_id: int) -> bool:
        """Delete a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return False
        
        self.db.delete(segment)
        self.db.commit()
        
        logger.info("Deleted segment", segment_id=segment_id)
        return True

    def preview_segment(
        self,
        filter_config: Optional[FilterConfig] = None,
        cube_query: Optional[Dict[str, Any]] = None,
        source_type: str = SegmentSourceType.LEGACY.value,
        sample_size: int = 5,
    ) -> SegmentPreviewResponse:
        """Preview a segment query — returns count and sample customers.

        Dispatches on `source_type`:
          - legacy: filters CustomerProfile via SQLAlchemy.
          - cube:   runs the Cube query through cube_client.
        """
        start_time = time.time()

        if source_type == SegmentSourceType.CUBE.value:
            sample_customers = self._preview_via_cube(cube_query or {}, sample_size)
            count = self._count_via_cube(cube_query or {})
        else:
            cfg = filter_config or FilterConfig()
            query = self._build_segment_query(cfg)
            count = query.count()
            sample_customers = []
            if count > 0:
                for customer in query.limit(sample_size).all():
                    sample_customers.append(self._customer_to_dict(customer))

        query_time_ms = (time.time() - start_time) * 1000

        return SegmentPreviewResponse(
            count=count,
            sample_customers=sample_customers,
            query_time_ms=round(query_time_ms, 2),
            source_type=source_type,
        )

    def _preview_via_cube(self, cube_query: Dict[str, Any], sample_size: int) -> List[Dict[str, Any]]:
        """Run a Cube query (with limit overridden to sample_size) and return rows."""
        if not cube_query:
            return []
        # Override limit for the sample call; the underlying audience query
        # likely has a different limit set.
        sample_q = {**cube_query, "limit": sample_size}
        try:
            result = cube_client.cube_load(sample_q)
            return result.get("data", []) or []
        except (cube_client.CubeQueryError, cube_client.CubeUnavailableError) as e:
            logger.warning("cube preview failed", error=str(e))
            return []

    def _count_via_cube(self, cube_query: Dict[str, Any]) -> int:
        """Return total matching rows for a Cube-defined audience.

        Strategy:
        - If the query already has a single measure and no dimensions, the
          response is the aggregate count.
        - Otherwise, derive a count-only twin: same filters, no dimensions/
          order/limit, with the cube's `.count` measure. Avoids Cube's
          per-query row-limit silently capping the audience size.
        """
        if not cube_query:
            return 0
        try:
            count_q = self._derive_count_query(cube_query)
            if count_q is None:
                # Fallback: just count returned rows (capped by Cube limit).
                return cube_client.count_query(cube_query) or 0
            return cube_client.count_query(count_q) or 0
        except (cube_client.CubeQueryError, cube_client.CubeUnavailableError) as e:
            logger.warning("cube count failed", error=str(e))
            return 0

    @staticmethod
    def _derive_count_query(cube_query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build a count-only twin of a row-level Cube query.

        Picks the source cube/view from the first dimension or filter member,
        and uses `<cube>.count` as the measure. Returns None if the query is
        already aggregate-only (just measures).
        """
        dims = cube_query.get("dimensions") or []
        measures = cube_query.get("measures") or []

        # Aggregate-only query — let count_query handle it.
        if measures and not dims:
            return None

        # Determine the cube/view name from a dimension or filter.
        source = None
        if dims:
            source = dims[0].split(".", 1)[0]
        else:
            for f in cube_query.get("filters") or []:
                member = f.get("member") or ""
                if "." in member:
                    source = member.split(".", 1)[0]
                    break
        if not source:
            return None

        return {
            "measures": [f"{source}.count"],
            "filters": cube_query.get("filters", []),
        }

    def get_segment_customers(
        self,
        segment_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[CustomerProfile], int]:
        """Get customers matching a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return [], 0
        
        filter_config = FilterConfig(**segment.filter_config)
        query = self._build_segment_query(filter_config)
        
        total = query.count()
        customers = (
            query
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        return customers, total

    def _build_segment_query(self, filter_config: FilterConfig):
        """Build a SQLAlchemy query from filter configuration."""
        query = self.db.query(CustomerProfile)
        
        if not filter_config.filters:
            return query
        
        conditions = []
        
        for f in filter_config.filters:
            condition = self._build_filter_condition(f)
            if condition is not None:
                conditions.append(condition)
        
        if conditions:
            if filter_config.logic == "AND":
                query = query.filter(and_(*conditions))
            else:
                query = query.filter(or_(*conditions))
        
        return query

    def _build_filter_condition(self, filter_cond: FilterCondition):
        """Build a single filter condition."""
        field_name = filter_cond.field
        operator = filter_cond.operator
        value = filter_cond.value
        value2 = filter_cond.value2
        
        # Check if this is a core field or an attribute
        core_fields = ["email", "phone", "first_name", "last_name", "external_id",
                       "first_seen_at", "last_seen_at"]
        
        if field_name in core_fields:
            # Query on CustomerProfile directly
            return self._build_core_field_condition(field_name, operator, value, value2)
        else:
            # Query via CustomerAttribute
            return self._build_attribute_condition(field_name, operator, value, value2)

    def _build_core_field_condition(self, field_name: str, operator: str, value: Any, value2: Any):
        """Build condition for core CustomerProfile fields."""
        column = getattr(CustomerProfile, field_name, None)
        if column is None:
            return None
        
        return self._apply_operator(column, operator, value, value2)

    def _build_attribute_condition(self, field_name: str, operator: str, value: Any, value2: Any):
        """Build condition for CustomerAttribute fields using subquery."""
        # Create a subquery to find customers with matching attribute
        subquery = (
            self.db.query(CustomerAttribute.customer_id)
            .filter(CustomerAttribute.attribute_name == field_name)
        )
        
        # Determine field type for proper casting
        field_info = next((f for f in SEGMENT_FIELDS if f["name"] == field_name), None)
        field_type = field_info["type"] if field_info else "string"
        
        # Apply operator to attribute_value
        attr_value_col = CustomerAttribute.attribute_value
        
        if field_type == "number":
            # Cast to float for numeric comparisons
            casted_col = cast(CustomerAttribute.attribute_value, Float)
            condition = self._apply_operator(casted_col, operator, value, value2, is_numeric=True)
        else:
            condition = self._apply_operator(attr_value_col, operator, value, value2)
        
        if condition is not None:
            subquery = subquery.filter(condition)
        
        return CustomerProfile.id.in_(subquery)

    def _apply_operator(self, column, operator: str, value: Any, value2: Any, is_numeric: bool = False):
        """Apply an operator to a column."""
        try:
            # Handle empty value operators
            if operator == "is_empty":
                return or_(column == None, column == "")
            elif operator == "is_not_empty":
                return and_(column != None, column != "")
            
            # Boolean operators
            elif operator == "is_true":
                return column.in_(["true", "True", "1", "yes", "Yes"])
            elif operator == "is_false":
                return column.in_(["false", "False", "0", "no", "No"])
            
            # String/equality operators
            elif operator == "equals":
                if is_numeric:
                    return column == float(value)
                return column == str(value)
            elif operator == "not_equals":
                if is_numeric:
                    return column != float(value)
                return column != str(value)
            
            # String operators
            elif operator == "contains":
                return column.ilike(f"%{value}%")
            elif operator == "not_contains":
                return ~column.ilike(f"%{value}%")
            elif operator == "starts_with":
                return column.ilike(f"{value}%")
            elif operator == "ends_with":
                return column.ilike(f"%{value}")
            
            # List operators
            elif operator == "in_list":
                if isinstance(value, str):
                    value = [v.strip() for v in value.split(",")]
                return column.in_(value)
            elif operator == "not_in_list":
                if isinstance(value, str):
                    value = [v.strip() for v in value.split(",")]
                return ~column.in_(value)
            
            # Numeric operators
            elif operator == "greater_than":
                return column > float(value)
            elif operator == "greater_than_or_equals":
                return column >= float(value)
            elif operator == "less_than":
                return column < float(value)
            elif operator == "less_than_or_equals":
                return column <= float(value)
            elif operator == "between":
                return and_(column >= float(value), column <= float(value2))
            
            # Date operators
            elif operator == "before":
                return column < value
            elif operator == "after":
                return column > value
            elif operator == "last_n_days":
                days_ago = datetime.utcnow() - timedelta(days=int(value))
                return column >= days_ago
            elif operator == "next_n_days":
                days_ahead = datetime.utcnow() + timedelta(days=int(value))
                return column <= days_ahead
            
            return None
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Error applying operator {operator}: {e}")
            return None

    def _update_segment_count(self, segment: Segment):
        """Update the cached count for a segment (legacy or Cube)."""
        try:
            if segment.source_type == SegmentSourceType.CUBE.value:
                count = self._count_via_cube(segment.cube_query or {})
            else:
                filter_config = FilterConfig(**(segment.filter_config or {"filters": [], "logic": "AND"}))
                query = self._build_segment_query(filter_config)
                count = query.count()

            segment.estimated_count = count
            segment.last_count_at = datetime.utcnow()
            self.db.commit()

            logger.info("Updated segment count", segment_id=segment.id, count=count, source_type=segment.source_type)
        except Exception as e:
            logger.error(f"Failed to update segment count: {e}", segment_id=segment.id)

    def _customer_to_dict(self, customer: CustomerProfile) -> Dict[str, Any]:
        """Convert customer to dictionary with attributes."""
        result = {
            "id": customer.id,
            "email": customer.email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "full_name": customer.full_name,
            "external_id": customer.external_id,
        }
        
        # Add a few key attributes
        for attr in customer.attributes[:5]:  # Limit to first 5 attributes
            result[attr.attribute_name] = attr.attribute_value
        
        return result

    def activate_segment(self, segment_id: int) -> Optional[Segment]:
        """Activate a segment (make it available for syncs)."""
        segment = self.get_segment(segment_id)
        if not segment:
            return None
        
        segment.status = SegmentStatus.ACTIVE.value
        self.db.commit()
        self.db.refresh(segment)
        
        logger.info("Activated segment", segment_id=segment.id)
        return segment

    def archive_segment(self, segment_id: int) -> Optional[Segment]:
        """Archive a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return None
        
        segment.status = SegmentStatus.ARCHIVED.value
        self.db.commit()
        self.db.refresh(segment)
        
        logger.info("Archived segment", segment_id=segment.id)
        return segment

    def duplicate_segment(self, segment_id: int, new_name: Optional[str] = None) -> Optional[Segment]:
        """Create a copy of an existing segment."""
        original = self.get_segment(segment_id)
        if not original:
            return None
        
        new_segment = Segment(
            name=new_name or f"{original.name} (copy)",
            description=original.description,
            source_type=original.source_type,
            filter_config=original.filter_config,
            cube_query=original.cube_query,
            tags=original.tags,
            status=SegmentStatus.DRAFT.value,
        )
        
        self.db.add(new_segment)
        self.db.commit()
        self.db.refresh(new_segment)
        
        self._update_segment_count(new_segment)
        
        logger.info("Duplicated segment", original_id=segment_id, new_id=new_segment.id)
        return new_segment
