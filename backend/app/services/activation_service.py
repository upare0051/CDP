"""
Service for segment activation and export operations.
"""
import csv
import io
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, inspect, text

from ..models.activation import SegmentActivation, ActivationRun, SegmentExport, ActivationStatus
from ..models.segment import Segment
from ..models.customer import CustomerProfile, CustomerAttribute
from ..models.connection import DestinationConnection
from ..schemas.activation import (
    ActivationCreate, ActivationUpdate, ActivationResponse,
    ExportRequest, DashboardStats
)
from ..services.segment_service import SegmentService
from ..core.logging import get_logger

logger = get_logger(__name__)


class ActivationService:
    """Service for managing segment activations."""

    def __init__(self, db: Session):
        self.db = db

    def create_activation(self, data: ActivationCreate) -> SegmentActivation:
        """Create a new segment activation."""
        # Verify segment exists
        segment = self.db.query(Segment).filter(Segment.id == data.segment_id).first()
        if not segment:
            raise ValueError(f"Segment {data.segment_id} not found")
        
        # Verify destination exists
        destination = self.db.query(DestinationConnection).filter(
            DestinationConnection.id == data.destination_id
        ).first()
        if not destination:
            raise ValueError(f"Destination {data.destination_id} not found")
        
        activation = SegmentActivation(
            segment_id=data.segment_id,
            destination_id=data.destination_id,
            name=data.name or f"{segment.name} → {destination.name}",
            frequency=data.frequency,
            field_mappings=[m.model_dump() for m in data.field_mappings],
            status=ActivationStatus.PENDING.value,
        )
        
        self.db.add(activation)
        self.db.commit()
        self.db.refresh(activation)
        
        logger.info("Created activation", 
                   activation_id=activation.id, 
                   segment=segment.name,
                   destination=destination.name)
        return activation

    def get_activation(self, activation_id: int) -> Optional[SegmentActivation]:
        """Get an activation by ID."""
        return self.db.query(SegmentActivation).filter(
            SegmentActivation.id == activation_id
        ).first()

    def list_activations(
        self,
        segment_id: Optional[int] = None,
        destination_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[SegmentActivation], int]:
        """List activations with optional filtering."""
        query = self.db.query(SegmentActivation)
        
        if segment_id:
            query = query.filter(SegmentActivation.segment_id == segment_id)
        if destination_id:
            query = query.filter(SegmentActivation.destination_id == destination_id)
        if status:
            query = query.filter(SegmentActivation.status == status)
        
        total = query.count()
        activations = query.order_by(SegmentActivation.updated_at.desc()).all()
        
        return activations, total

    def update_activation(self, activation_id: int, data: ActivationUpdate) -> Optional[SegmentActivation]:
        """Update an activation."""
        activation = self.get_activation(activation_id)
        if not activation:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        if "field_mappings" in update_data and update_data["field_mappings"]:
            update_data["field_mappings"] = [m.model_dump() if hasattr(m, 'model_dump') else m 
                                              for m in update_data["field_mappings"]]
        
        for field, value in update_data.items():
            setattr(activation, field, value)
        
        self.db.commit()
        self.db.refresh(activation)
        
        logger.info("Updated activation", activation_id=activation_id)
        return activation

    def delete_activation(self, activation_id: int) -> bool:
        """Delete an activation."""
        activation = self.get_activation(activation_id)
        if not activation:
            return False
        # SQLite doesn't always enforce ON DELETE CASCADE unless foreign keys are
        # explicitly enabled for the connection. Remove dependent runs first to
        # avoid NOT NULL / FK errors during activation deletion.
        self.db.query(ActivationRun).filter(
            ActivationRun.activation_id == activation_id
        ).delete(synchronize_session=False)

        self.db.delete(activation)
        self.db.commit()
        
        logger.info("Deleted activation", activation_id=activation_id)
        return True

    def trigger_activation(self, activation_id: int) -> ActivationRun:
        """
        Trigger a sync run for an activation.
        This syncs the segment members to the destination.
        """
        activation = self.get_activation(activation_id)
        if not activation:
            raise ValueError(f"Activation {activation_id} not found")
        
        # Create run record
        run = ActivationRun(
            run_id=str(uuid.uuid4()),
            activation_id=activation_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        
        try:
            # Get segment customers
            segment_service = SegmentService(self.db)
            customers, total = segment_service.get_segment_customers(
                activation.segment_id, 
                page=1, 
                page_size=10000  # Batch size
            )
            
            run.total_customers = total
            
            # In a real implementation, we would:
            # 1. Get the destination adapter
            # 2. Transform customer data according to field_mappings
            # 3. Send data to destination in batches
            # 4. Track successes/failures
            
            # For now, simulate success
            run.synced_count = total
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
            
            # Update activation stats
            activation.last_sync_at = datetime.utcnow()
            activation.last_sync_count = total
            activation.total_synced += total
            activation.status = ActivationStatus.ACTIVE.value
            
            self.db.commit()
            
            logger.info("Activation run completed",
                       run_id=run.run_id,
                       synced=run.synced_count)
            
        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            self.db.commit()
            logger.error("Activation run failed", run_id=run.run_id, error=str(e))
        
        self.db.refresh(run)
        return run

    def get_activation_runs(
        self, 
        activation_id: int, 
        limit: int = 10
    ) -> List[ActivationRun]:
        """Get recent runs for an activation."""
        return (
            self.db.query(ActivationRun)
            .filter(ActivationRun.activation_id == activation_id)
            .order_by(ActivationRun.started_at.desc())
            .limit(limit)
            .all()
        )

    def to_response(self, activation: SegmentActivation) -> ActivationResponse:
        """Convert activation to response with related entity names."""
        return ActivationResponse(
            id=activation.id,
            segment_id=activation.segment_id,
            destination_id=activation.destination_id,
            name=activation.name,
            frequency=activation.frequency,
            status=activation.status,
            field_mappings=activation.field_mappings or [],
            last_sync_at=activation.last_sync_at,
            last_sync_count=activation.last_sync_count,
            total_synced=activation.total_synced,
            created_at=activation.created_at,
            updated_at=activation.updated_at,
            segment_name=activation.segment.name if activation.segment else None,
            destination_name=activation.destination.name if activation.destination else None,
            destination_type=activation.destination.destination_type if activation.destination else None,
        )


class ExportService:
    """Service for segment exports."""

    def __init__(self, db: Session):
        self.db = db

    def export_segment_to_csv(
        self, 
        segment_id: int, 
        request: ExportRequest
    ) -> Tuple[str, bytes, int]:
        """
        Export segment customers to CSV.
        Returns: (filename, csv_bytes, row_count)
        """
        # Get segment
        segment = self.db.query(Segment).filter(Segment.id == segment_id).first()
        if not segment:
            raise ValueError(f"Segment {segment_id} not found")
        
        # Get customers
        segment_service = SegmentService(self.db)
        customers, total = segment_service.get_segment_customers(segment_id, page=1, page_size=50000)
        
        # Determine fields to include
        core_fields = ["id", "email", "first_name", "last_name", "external_id", "phone"]
        if request.included_fields:
            fields = [f for f in request.included_fields if f in core_fields]
        else:
            fields = core_fields
        
        # Build CSV
        output = io.StringIO()
        
        # Collect all attribute names if including attributes
        attr_names = set()
        if request.include_attributes:
            for customer in customers:
                for attr in customer.attributes:
                    attr_names.add(attr.attribute_name)
        
        all_fields = fields + sorted(list(attr_names))
        
        writer = csv.DictWriter(output, fieldnames=all_fields)
        writer.writeheader()
        
        for customer in customers:
            row = {}
            for field in fields:
                row[field] = getattr(customer, field, "")
            
            if request.include_attributes:
                for attr in customer.attributes:
                    row[attr.attribute_name] = attr.attribute_value
            
            writer.writerow(row)
        
        csv_content = output.getvalue()
        csv_bytes = csv_content.encode('utf-8')
        
        # Create export record
        filename = f"{segment.name.lower().replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        
        export = SegmentExport(
            segment_id=segment_id,
            file_name=filename,
            file_size=len(csv_bytes),
            row_count=len(customers),
            included_fields=all_fields,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        self.db.add(export)
        self.db.commit()
        
        logger.info("Segment exported", 
                   segment_id=segment_id, 
                   rows=len(customers),
                   filename=filename)
        
        return filename, csv_bytes, len(customers)

    def get_segment_exports(self, segment_id: int, limit: int = 10) -> List[SegmentExport]:
        """Get recent exports for a segment."""
        return (
            self.db.query(SegmentExport)
            .filter(SegmentExport.segment_id == segment_id)
            .order_by(SegmentExport.created_at.desc())
            .limit(limit)
            .all()
        )


class DashboardService:
    """Service for dashboard metrics."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_stats(self) -> DashboardStats:
        """Get comprehensive dashboard statistics."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        use_customer_mart = self._has_table("mart_customer_360")
        use_segment_mart = self._has_table("mart_segment_base")
        use_activation_mart = self._has_table("mart_activation_performance")

        # Customer stats
        if use_customer_mart:
            total_customers = self.db.execute(text("SELECT count(*) FROM mart_customer_360")).scalar() or 0
            customers_today = self.db.execute(
                text("SELECT count(*) FROM mart_customer_360 WHERE created_at >= :today_start"),
                {"today_start": today_start},
            ).scalar() or 0
            customers_week = self.db.execute(
                text("SELECT count(*) FROM mart_customer_360 WHERE created_at >= :week_start"),
                {"week_start": week_start},
            ).scalar() or 0
        else:
            total_customers = self.db.query(func.count(CustomerProfile.id)).scalar() or 0
            customers_today = self.db.query(func.count(CustomerProfile.id)).filter(
                CustomerProfile.created_at >= today_start
            ).scalar() or 0
            customers_week = self.db.query(func.count(CustomerProfile.id)).filter(
                CustomerProfile.created_at >= week_start
            ).scalar() or 0

        # Segment stats
        if use_segment_mart:
            total_segments = self.db.execute(text("SELECT count(*) FROM mart_segment_base")).scalar() or 0
            active_segments = self.db.execute(
                text("SELECT count(*) FROM mart_segment_base WHERE segment_status = 'active'")
            ).scalar() or 0
            segments_week = self.db.execute(
                text("SELECT count(*) FROM mart_segment_base WHERE created_at >= :week_start"),
                {"week_start": week_start},
            ).scalar() or 0

            top_segments_rows = self.db.execute(
                text(
                    """
                    SELECT
                        segment_id,
                        segment_name,
                        computed_member_count,
                        segment_status,
                        ai_generated
                    FROM mart_segment_base
                    ORDER BY computed_member_count DESC
                    LIMIT 5
                    """
                )
            ).mappings().all()
            top_segments_data = [
                {
                    "id": int(r["segment_id"]),
                    "name": r["segment_name"],
                    "count": int(r["computed_member_count"] or 0),
                    "status": r["segment_status"],
                    "ai_generated": bool(r["ai_generated"]),
                }
                for r in top_segments_rows
            ]
        else:
            total_segments = self.db.query(func.count(Segment.id)).scalar() or 0
            active_segments = self.db.query(func.count(Segment.id)).filter(
                Segment.status == "active"
            ).scalar() or 0
            segments_week = self.db.query(func.count(Segment.id)).filter(
                Segment.created_at >= week_start
            ).scalar() or 0
            top_segments = (
                self.db.query(Segment)
                .filter(Segment.estimated_count.isnot(None))
                .order_by(Segment.estimated_count.desc())
                .limit(5)
                .all()
            )
            top_segments_data = [
                {
                    "id": s.id,
                    "name": s.name,
                    "count": s.estimated_count,
                    "status": s.status,
                    "ai_generated": s.ai_generated,
                }
                for s in top_segments
            ]

        # Activation stats + recent activations
        if use_activation_mart:
            total_activations = self.db.execute(
                text("SELECT count(*) FROM mart_activation_performance")
            ).scalar() or 0
            active_activations = self.db.execute(
                text("SELECT count(*) FROM mart_activation_performance WHERE activation_status = 'active'")
            ).scalar() or 0
            syncs_today = self.db.execute(
                text("SELECT count(*) FROM mart_activation_performance WHERE last_run_started_at >= :today_start"),
                {"today_start": today_start},
            ).scalar() or 0

            recent_rows = self.db.execute(
                text(
                    """
                    SELECT
                        activation_id,
                        activation_name,
                        destination_name,
                        last_sync_at,
                        last_sync_count,
                        activation_status
                    FROM mart_activation_performance
                    ORDER BY coalesce(last_sync_at, created_at) DESC
                    LIMIT 5
                    """
                )
            ).mappings().all()

            # Build lookup maps from base app tables (always present).
            segment_name_map = {
                int(s.id): s.name
                for s in self.db.query(Segment.id, Segment.name).all()
            }
            activation_segment_map = {
                int(a.id): int(a.segment_id)
                for a in self.db.query(SegmentActivation.id, SegmentActivation.segment_id).all()
            }

            recent_activations_data = [
                {
                    "id": int(r["activation_id"]),
                    "name": r["activation_name"],
                    "segment_name": segment_name_map.get(activation_segment_map.get(r["activation_id"])),
                    "destination_name": r["destination_name"],
                    "last_sync_at": r["last_sync_at"].isoformat() if r["last_sync_at"] else None,
                    "last_sync_count": int(r["last_sync_count"]) if r["last_sync_count"] is not None else None,
                    "status": r["activation_status"],
                }
                for r in recent_rows
            ]
        else:
            total_activations = self.db.query(func.count(SegmentActivation.id)).scalar() or 0
            active_activations = self.db.query(func.count(SegmentActivation.id)).filter(
                SegmentActivation.status == "active"
            ).scalar() or 0
            syncs_today = self.db.query(func.count(ActivationRun.id)).filter(
                ActivationRun.started_at >= today_start
            ).scalar() or 0
            recent_activations = (
                self.db.query(SegmentActivation)
                .order_by(SegmentActivation.last_sync_at.desc())
                .limit(5)
                .all()
            )
            recent_activations_data = [
                {
                    "id": a.id,
                    "name": a.name,
                    "segment_name": a.segment.name if a.segment else None,
                    "destination_name": a.destination.name if a.destination else None,
                    "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
                    "last_sync_count": a.last_sync_count,
                    "status": a.status,
                }
                for a in recent_activations
            ]
        
        return DashboardStats(
            total_customers=total_customers,
            total_segments=total_segments,
            active_segments=active_segments,
            total_activations=total_activations,
            active_activations=active_activations,
            customers_added_today=customers_today,
            customers_added_week=customers_week,
            segments_created_week=segments_week,
            syncs_today=syncs_today,
            top_segments=top_segments_data,
            recent_activations=recent_activations_data,
        )

    def _has_table(self, table_name: str) -> bool:
        """Check if a table/view exists in the current database."""
        try:
            inspector = inspect(self.db.bind)
            return bool(inspector.has_table(table_name))
        except Exception:
            return False
