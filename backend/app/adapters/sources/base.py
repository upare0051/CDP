"""Base source adapter interface."""

from abc import ABC, abstractmethod
from typing import Iterator, List, Dict, Any, Optional
from dataclasses import dataclass
import hashlib
import json

from ...schemas.connection import TableInfo, ColumnInfo, TableSchema


@dataclass
class SourceConfig:
    """Configuration for source connection."""
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    duckdb_path: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None


class SourceAdapter(ABC):
    """Abstract base class for source adapters (Redshift, DuckDB)."""
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self._connection = None
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the source."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        pass
    
    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test the connection. Returns (success, message)."""
        pass
    
    @abstractmethod
    def get_schemas(self) -> List[str]:
        """Get list of available schemas."""
        pass
    
    @abstractmethod
    def get_tables(self, schema: str) -> List[TableInfo]:
        """Get list of tables in a schema."""
        pass
    
    @abstractmethod
    def get_table_schema(self, schema: str, table: str) -> TableSchema:
        """Get schema information for a table."""
        pass
    
    @abstractmethod
    def get_row_count(self, schema: str, table: str) -> int:
        """Get row count for a table."""
        pass
    
    @abstractmethod
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        pass
    
    @abstractmethod
    def stream_query(
        self, 
        query: str, 
        batch_size: int = 1000
    ) -> Iterator[List[Dict[str, Any]]]:
        """Stream query results in batches."""
        pass
    
    def build_select_query(
        self,
        schema: str,
        table: str,
        columns: List[str],
        incremental_column: Optional[str] = None,
        checkpoint_value: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        """Build SELECT query with optional incremental filter."""
        columns_str = ", ".join([f'"{c}"' for c in columns])
        query = f'SELECT {columns_str} FROM "{schema}"."{table}"'
        
        if incremental_column and checkpoint_value:
            query += f' WHERE "{incremental_column}" > \'{checkpoint_value}\''
        
        if incremental_column:
            query += f' ORDER BY "{incremental_column}" ASC'
        
        if limit:
            query += f' LIMIT {limit}'
        
        return query
    
    def get_schema_hash(self, schema: str, table: str) -> str:
        """Generate hash of table schema for change detection."""
        table_schema = self.get_table_schema(schema, table)
        schema_data = {
            "columns": [
                {
                    "name": col.column_name,
                    "type": col.data_type,
                    "nullable": col.is_nullable,
                }
                for col in table_schema.columns
            ]
        }
        schema_json = json.dumps(schema_data, sort_keys=True)
        return hashlib.sha256(schema_json.encode()).hexdigest()
    
    def detect_schema_changes(
        self, 
        schema: str, 
        table: str, 
        previous_hash: Optional[str]
    ) -> tuple[bool, str, List[str], List[str], List[str]]:
        """
        Detect schema changes.
        Returns: (has_changes, current_hash, added_cols, removed_cols, modified_cols)
        """
        current_hash = self.get_schema_hash(schema, table)
        
        if not previous_hash:
            return False, current_hash, [], [], []
        
        if current_hash == previous_hash:
            return False, current_hash, [], [], []
        
        # For detailed diff, would need to store previous schema
        # Simplified: just detect if changed
        return True, current_hash, [], [], []
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class SourceAdapterFactory:
    """Factory for creating source adapters."""
    
    _adapters: Dict[str, type] = {}
    
    @classmethod
    def register(cls, source_type: str, adapter_class: type):
        """Register an adapter class for a source type."""
        cls._adapters[source_type] = adapter_class
    
    @classmethod
    def create(cls, source_type: str, config: SourceConfig) -> SourceAdapter:
        """Create an adapter instance."""
        if source_type not in cls._adapters:
            raise ValueError(f"Unknown source type: {source_type}")
        return cls._adapters[source_type](config)
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """Get list of registered source types."""
        return list(cls._adapters.keys())
