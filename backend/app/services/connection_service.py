"""Connection management service."""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.connection import SourceConnection, DestinationConnection, SourceType, DestinationType
from ..schemas.connection import (
    SourceConnectionCreate, SourceConnectionUpdate, SourceConnectionTestResult,
    DestinationConnectionCreate, DestinationConnectionUpdate, DestinationConnectionTestResult,
    TableInfo, TableSchema,
)
from ..core.security import encrypt_credential, decrypt_credential, mask_credential
from ..adapters.sources import SourceAdapterFactory, SourceConfig
from ..adapters.destinations import DestinationAdapterFactory, DestinationConfig
from ..core.logging import get_logger

logger = get_logger(__name__)


class ConnectionService:
    """Service for managing source and destination connections."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Source Connection Methods
    
    def create_source_connection(self, data: SourceConnectionCreate) -> SourceConnection:
        """Create a new source connection."""
        conn = SourceConnection(
            name=data.name,
            source_type=data.source_type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password_encrypted=encrypt_credential(data.password) if data.password else None,
            duckdb_path=data.duckdb_path,
            extra_config=data.extra_config or {},
        )
        
        self.db.add(conn)
        self.db.commit()
        self.db.refresh(conn)
        
        logger.info("Created source connection", name=data.name, type=data.source_type)
        return conn
    
    def get_source_connection(self, connection_id: int) -> Optional[SourceConnection]:
        """Get source connection by ID."""
        return self.db.query(SourceConnection).filter(SourceConnection.id == connection_id).first()
    
    def get_source_connection_by_name(self, name: str) -> Optional[SourceConnection]:
        """Get source connection by name."""
        return self.db.query(SourceConnection).filter(SourceConnection.name == name).first()
    
    def list_source_connections(self, active_only: bool = False) -> List[SourceConnection]:
        """List all source connections."""
        query = self.db.query(SourceConnection)
        if active_only:
            query = query.filter(SourceConnection.is_active == True)
        return query.order_by(SourceConnection.created_at.desc()).all()
    
    def update_source_connection(self, connection_id: int, data: SourceConnectionUpdate) -> Optional[SourceConnection]:
        """Update a source connection."""
        conn = self.get_source_connection(connection_id)
        if not conn:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        # Handle password separately
        if "password" in update_data:
            password = update_data.pop("password")
            if password:
                conn.password_encrypted = encrypt_credential(password)
        
        for key, value in update_data.items():
            setattr(conn, key, value)
        
        self.db.commit()
        self.db.refresh(conn)
        
        logger.info("Updated source connection", id=connection_id)
        return conn
    
    def delete_source_connection(self, connection_id: int) -> bool:
        """Delete a source connection."""
        conn = self.get_source_connection(connection_id)
        if not conn:
            return False
        
        self.db.delete(conn)
        self.db.commit()
        
        logger.info("Deleted source connection", id=connection_id)
        return True
    
    def test_source_connection(self, connection_id: int) -> SourceConnectionTestResult:
        """Test a source connection."""
        conn = self.get_source_connection(connection_id)
        if not conn:
            return SourceConnectionTestResult(success=False, message="Connection not found")
        
        try:
            adapter = self._get_source_adapter(conn)
            with adapter:
                success, message = adapter.test_connection()
                
                # Count tables if successful
                tables_found = None
                if success:
                    schemas = adapter.get_schemas()
                    tables_found = sum(len(adapter.get_tables(s)) for s in schemas)
                
                # Update connection status
                conn.last_tested_at = datetime.utcnow()
                conn.last_test_success = success
                self.db.commit()
                
                return SourceConnectionTestResult(
                    success=success,
                    message=message,
                    tables_found=tables_found,
                )
        except Exception as e:
            conn.last_tested_at = datetime.utcnow()
            conn.last_test_success = False
            self.db.commit()
            
            return SourceConnectionTestResult(
                success=False,
                message="Connection test failed",
                error=str(e),
            )
    
    def get_source_schemas(self, connection_id: int) -> List[str]:
        """Get schemas from a source connection."""
        conn = self.get_source_connection(connection_id)
        if not conn:
            return []
        
        adapter = self._get_source_adapter(conn)
        with adapter:
            return adapter.get_schemas()
    
    def get_source_tables(self, connection_id: int, schema: str) -> List[TableInfo]:
        """Get tables from a source connection schema."""
        conn = self.get_source_connection(connection_id)
        if not conn:
            return []
        
        adapter = self._get_source_adapter(conn)
        with adapter:
            return adapter.get_tables(schema)
    
    def get_source_table_schema(self, connection_id: int, schema: str, table: str) -> Optional[TableSchema]:
        """Get table schema from source connection."""
        conn = self.get_source_connection(connection_id)
        if not conn:
            return None
        
        adapter = self._get_source_adapter(conn)
        with adapter:
            return adapter.get_table_schema(schema, table)
    
    def _get_source_adapter(self, conn: SourceConnection):
        """Create source adapter from connection."""
        config = SourceConfig(
            host=conn.host,
            port=conn.port,
            database=conn.database,
            username=conn.username,
            password=decrypt_credential(conn.password_encrypted) if conn.password_encrypted else None,
            duckdb_path=conn.duckdb_path,
            extra_config=conn.extra_config,
        )
        return SourceAdapterFactory.create(conn.source_type.value, config)
    
    # Destination Connection Methods
    
    def create_destination_connection(self, data: DestinationConnectionCreate) -> DestinationConnection:
        """Create a new destination connection."""
        conn = DestinationConnection(
            name=data.name,
            destination_type=data.destination_type,
            api_key_encrypted=encrypt_credential(data.api_key),
            api_endpoint=data.api_endpoint,
            braze_app_id=data.braze_app_id,
            attentive_api_url=data.attentive_api_url,
            rate_limit_per_second=data.rate_limit_per_second,
            batch_size=data.batch_size,
            extra_config=data.extra_config or {},
        )
        
        self.db.add(conn)
        self.db.commit()
        self.db.refresh(conn)
        
        logger.info("Created destination connection", name=data.name, type=data.destination_type)
        return conn
    
    def get_destination_connection(self, connection_id: int) -> Optional[DestinationConnection]:
        """Get destination connection by ID."""
        return self.db.query(DestinationConnection).filter(DestinationConnection.id == connection_id).first()
    
    def list_destination_connections(self, active_only: bool = False) -> List[DestinationConnection]:
        """List all destination connections."""
        query = self.db.query(DestinationConnection)
        if active_only:
            query = query.filter(DestinationConnection.is_active == True)
        return query.order_by(DestinationConnection.created_at.desc()).all()
    
    def update_destination_connection(self, connection_id: int, data: DestinationConnectionUpdate) -> Optional[DestinationConnection]:
        """Update a destination connection."""
        conn = self.get_destination_connection(connection_id)
        if not conn:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        # Handle API key separately
        if "api_key" in update_data:
            api_key = update_data.pop("api_key")
            if api_key:
                conn.api_key_encrypted = encrypt_credential(api_key)
        
        for key, value in update_data.items():
            setattr(conn, key, value)
        
        self.db.commit()
        self.db.refresh(conn)
        
        logger.info("Updated destination connection", id=connection_id)
        return conn
    
    def delete_destination_connection(self, connection_id: int) -> bool:
        """Delete a destination connection."""
        conn = self.get_destination_connection(connection_id)
        if not conn:
            return False
        
        self.db.delete(conn)
        self.db.commit()
        
        logger.info("Deleted destination connection", id=connection_id)
        return True
    
    def test_destination_connection(self, connection_id: int) -> DestinationConnectionTestResult:
        """Test a destination connection."""
        conn = self.get_destination_connection(connection_id)
        if not conn:
            return DestinationConnectionTestResult(success=False, message="Connection not found")
        
        try:
            adapter = self._get_destination_adapter(conn)
            success, message = adapter.test_connection()
            
            # Update connection status
            conn.last_tested_at = datetime.utcnow()
            conn.last_test_success = success
            self.db.commit()
            
            return DestinationConnectionTestResult(success=success, message=message)
        except Exception as e:
            conn.last_tested_at = datetime.utcnow()
            conn.last_test_success = False
            self.db.commit()
            
            return DestinationConnectionTestResult(
                success=False,
                message="Connection test failed",
                error=str(e),
            )
    
    def _get_destination_adapter(self, conn: DestinationConnection):
        """Create destination adapter from connection."""
        config = DestinationConfig(
            api_key=decrypt_credential(conn.api_key_encrypted),
            api_endpoint=conn.api_endpoint or conn.attentive_api_url,
            batch_size=conn.batch_size or 75,
            rate_limit_per_second=conn.rate_limit_per_second or 100,
            extra_config=conn.extra_config,
        )
        return DestinationAdapterFactory.create(conn.destination_type.value, config)
    
    def get_masked_api_key(self, connection_id: int) -> Optional[str]:
        """Get masked API key for display."""
        conn = self.get_destination_connection(connection_id)
        if not conn or not conn.api_key_encrypted:
            return None
        
        api_key = decrypt_credential(conn.api_key_encrypted)
        return mask_credential(api_key)
