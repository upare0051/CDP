"""Sync job management service."""

from typing import List, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..models.sync import SyncJob, SyncRun, FieldMapping, SyncStatus, SyncMode
from ..models.connection import SourceConnection, DestinationConnection
from ..schemas.sync import (
    SyncJobCreate, SyncJobUpdate, SyncJobResponse, SyncJobSummary,
    SyncRunCreate, SyncRunResponse, FieldMappingCreate,
)
from ..core.logging import get_logger

logger = get_logger(__name__)


class SyncService:
    """Service for managing sync jobs and runs."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Sync Job Methods
    
    def create_sync_job(self, data: SyncJobCreate) -> SyncJob:
        """Create a new sync job with field mappings."""
        # Validate connections exist
        source = self.db.query(SourceConnection).filter(SourceConnection.id == data.source_connection_id).first()
        dest = self.db.query(DestinationConnection).filter(DestinationConnection.id == data.destination_connection_id).first()
        
        if not source:
            raise ValueError(f"Source connection {data.source_connection_id} not found")
        if not dest:
            raise ValueError(f"Destination connection {data.destination_connection_id} not found")
        
        # Create sync job
        job = SyncJob(
            name=data.name,
            description=data.description,
            source_connection_id=data.source_connection_id,
            destination_connection_id=data.destination_connection_id,
            source_schema=data.source_schema,
            source_table=data.source_table,
            source_query=data.source_query,
            sync_mode=data.sync_mode,
            sync_key=data.sync_key,
            incremental_column=data.incremental_column,
            schedule_type=data.schedule_type,
            cron_expression=data.cron_expression,
        )
        
        self.db.add(job)
        self.db.flush()  # Get job ID
        
        # Create field mappings
        for mapping_data in data.field_mappings:
            mapping = FieldMapping(
                sync_job_id=job.id,
                source_field=mapping_data.source_field,
                source_field_type=mapping_data.source_field_type,
                destination_field=mapping_data.destination_field,
                transformation=mapping_data.transformation,
                is_sync_key=mapping_data.is_sync_key,
                is_required=mapping_data.is_required,
            )
            self.db.add(mapping)
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info("Created sync job", name=data.name, id=job.id)
        return job
    
    def get_sync_job(self, job_id: int) -> Optional[SyncJob]:
        """Get sync job by ID."""
        return self.db.query(SyncJob).filter(SyncJob.id == job_id).first()
    
    def get_sync_job_by_name(self, name: str) -> Optional[SyncJob]:
        """Get sync job by name."""
        return self.db.query(SyncJob).filter(SyncJob.name == name).first()
    
    def list_sync_jobs(self, active_only: bool = False) -> List[SyncJob]:
        """List all sync jobs."""
        query = self.db.query(SyncJob)
        if active_only:
            query = query.filter(SyncJob.is_active == True)
        return query.order_by(SyncJob.created_at.desc()).all()
    
    def get_sync_job_summaries(self) -> List[SyncJobSummary]:
        """Get sync job summaries with stats."""
        jobs = self.list_sync_jobs()
        summaries = []
        
        for job in jobs:
            # Get last run
            last_run = self.get_latest_run(job.id)
            
            # Get total rows synced
            total_rows = self.db.query(SyncRun).filter(
                SyncRun.sync_job_id == job.id,
                SyncRun.status == SyncStatus.COMPLETED,
            ).with_entities(
                func.sum(SyncRun.rows_synced)
            ).scalar() or 0
            
            summaries.append(SyncJobSummary(
                id=job.id,
                name=job.name,
                source_connection_name=job.source_connection.name,
                destination_connection_name=job.destination_connection.name,
                sync_mode=job.sync_mode,
                schedule_type=job.schedule_type,
                is_active=job.is_active,
                is_paused=job.is_paused,
                last_run_status=last_run.status if last_run else None,
                last_run_at=last_run.started_at if last_run else None,
                total_rows_synced=total_rows,
            ))
        
        return summaries
    
    def update_sync_job(self, job_id: int, data: SyncJobUpdate) -> Optional[SyncJob]:
        """Update a sync job."""
        job = self.get_sync_job(job_id)
        if not job:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(job, key, value)
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info("Updated sync job", id=job_id)
        return job
    
    def delete_sync_job(self, job_id: int) -> bool:
        """Delete a sync job."""
        job = self.get_sync_job(job_id)
        if not job:
            return False
        
        self.db.delete(job)
        self.db.commit()
        
        logger.info("Deleted sync job", id=job_id)
        return True
    
    def update_field_mappings(self, job_id: int, mappings: List[FieldMappingCreate]) -> SyncJob:
        """Update field mappings for a sync job."""
        job = self.get_sync_job(job_id)
        if not job:
            raise ValueError(f"Sync job {job_id} not found")
        
        # Delete existing mappings
        self.db.query(FieldMapping).filter(FieldMapping.sync_job_id == job_id).delete()
        
        # Create new mappings
        for mapping_data in mappings:
            mapping = FieldMapping(
                sync_job_id=job_id,
                source_field=mapping_data.source_field,
                source_field_type=mapping_data.source_field_type,
                destination_field=mapping_data.destination_field,
                transformation=mapping_data.transformation,
                is_sync_key=mapping_data.is_sync_key,
                is_required=mapping_data.is_required,
            )
            self.db.add(mapping)
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info("Updated field mappings", job_id=job_id, count=len(mappings))
        return job
    
    # Sync Run Methods
    
    def create_sync_run(self, job_id: int, airflow_run_id: Optional[str] = None) -> SyncRun:
        """Create a new sync run."""
        run_id = str(uuid.uuid4())
        
        job = self.get_sync_job(job_id)
        if not job:
            raise ValueError(f"Sync job {job_id} not found")
        
        run = SyncRun(
            sync_job_id=job_id,
            run_id=run_id,
            airflow_run_id=airflow_run_id,
            status=SyncStatus.PENDING,
            checkpoint_value=job.last_checkpoint_value,  # Start from last checkpoint
        )
        
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        
        logger.info("Created sync run", job_id=job_id, run_id=run_id)
        return run
    
    def get_sync_run(self, run_id: str) -> Optional[SyncRun]:
        """Get sync run by run_id."""
        return self.db.query(SyncRun).filter(SyncRun.run_id == run_id).first()
    
    def get_sync_run_by_id(self, id: int) -> Optional[SyncRun]:
        """Get sync run by database ID."""
        return self.db.query(SyncRun).filter(SyncRun.id == id).first()
    
    def list_sync_runs(self, job_id: Optional[int] = None, limit: int = 50) -> List[SyncRun]:
        """List sync runs, optionally filtered by job."""
        query = self.db.query(SyncRun)
        if job_id:
            query = query.filter(SyncRun.sync_job_id == job_id)
        return query.order_by(desc(SyncRun.created_at)).limit(limit).all()
    
    def get_latest_run(self, job_id: int) -> Optional[SyncRun]:
        """Get the latest run for a job."""
        return self.db.query(SyncRun).filter(
            SyncRun.sync_job_id == job_id
        ).order_by(desc(SyncRun.created_at)).first()
    
    def start_run(self, run_id: str) -> SyncRun:
        """Mark a run as started."""
        run = self.get_sync_run(run_id)
        if not run:
            raise ValueError(f"Sync run {run_id} not found")
        
        run.status = SyncStatus.RUNNING
        run.started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(run)
        
        logger.info("Started sync run", run_id=run_id)
        return run
    
    def complete_run(
        self, 
        run_id: str, 
        rows_read: int,
        rows_synced: int,
        rows_failed: int,
        rows_skipped: int,
        new_checkpoint_value: Optional[str] = None,
        logs: Optional[str] = None,
    ) -> SyncRun:
        """Mark a run as completed successfully."""
        run = self.get_sync_run(run_id)
        if not run:
            raise ValueError(f"Sync run {run_id} not found")
        
        run.status = SyncStatus.COMPLETED
        run.completed_at = datetime.utcnow()
        run.rows_read = rows_read
        run.rows_synced = rows_synced
        run.rows_failed = rows_failed
        run.rows_skipped = rows_skipped
        run.logs = logs
        
        if run.started_at:
            run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
        
        # Update checkpoint on success
        if new_checkpoint_value:
            run.new_checkpoint_value = new_checkpoint_value
            # Also update the job's checkpoint
            job = run.sync_job
            job.last_checkpoint_value = new_checkpoint_value
        
        self.db.commit()
        self.db.refresh(run)
        
        logger.info("Completed sync run", run_id=run_id, rows_synced=rows_synced)
        return run
    
    def fail_run(
        self, 
        run_id: str, 
        error_message: str,
        error_details: Optional[dict] = None,
        rows_read: int = 0,
        rows_synced: int = 0,
        rows_failed: int = 0,
        logs: Optional[str] = None,
    ) -> SyncRun:
        """Mark a run as failed."""
        run = self.get_sync_run(run_id)
        if not run:
            raise ValueError(f"Sync run {run_id} not found")
        
        run.status = SyncStatus.FAILED
        run.completed_at = datetime.utcnow()
        run.error_message = error_message
        run.error_details = error_details
        run.rows_read = rows_read
        run.rows_synced = rows_synced
        run.rows_failed = rows_failed
        run.logs = logs
        
        if run.started_at:
            run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
        
        self.db.commit()
        self.db.refresh(run)
        
        logger.error("Failed sync run", run_id=run_id, error=error_message)
        return run
    
    def increment_retry_count(self, run_id: str) -> SyncRun:
        """Increment retry count for a run."""
        run = self.get_sync_run(run_id)
        if not run:
            raise ValueError(f"Sync run {run_id} not found")
        
        run.retry_count += 1
        run.status = SyncStatus.PENDING
        
        self.db.commit()
        self.db.refresh(run)
        
        logger.info("Incremented retry count", run_id=run_id, retry_count=run.retry_count)
        return run
    
    def get_pending_runs(self) -> List[SyncRun]:
        """Get all pending runs."""
        return self.db.query(SyncRun).filter(
            SyncRun.status == SyncStatus.PENDING
        ).order_by(SyncRun.created_at).all()
    
    def get_running_runs(self) -> List[SyncRun]:
        """Get all currently running runs."""
        return self.db.query(SyncRun).filter(
            SyncRun.status == SyncStatus.RUNNING
        ).all()
