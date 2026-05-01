"""Redshift source adapter for production."""

from typing import Iterator, List, Dict, Any, Optional

try:
    import redshift_connector
    REDSHIFT_AVAILABLE = True
except ImportError:
    redshift_connector = None
    REDSHIFT_AVAILABLE = False

from .base import SourceAdapter, SourceConfig, SourceAdapterFactory
from ...schemas.connection import TableInfo, ColumnInfo, TableSchema
from ...core.logging import get_logger

logger = get_logger(__name__)


class RedshiftAdapter(SourceAdapter):
    """Redshift adapter for production data warehouse."""
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._conn = None
        self._cursor = None
    
    def connect(self) -> bool:
        """Connect to Redshift."""
        if not REDSHIFT_AVAILABLE:
            raise ImportError("redshift_connector not installed. Install with: pip install redshift-connector")
        
        try:
            self._conn = redshift_connector.connect(
                host=self.config.host,
                port=self.config.port or 5439,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                timeout=30,
            )
            self._cursor = self._conn.cursor()
            logger.info("Connected to Redshift", host=self.config.host, database=self.config.database)
            return True
        except Exception as e:
            logger.error("Failed to connect to Redshift", error=str(e))
            raise
    
    def disconnect(self) -> None:
        """Close Redshift connection."""
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Disconnected from Redshift")
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Redshift connection."""
        try:
            if not self._conn:
                self.connect()
            
            self._cursor.execute("SELECT 1")
            self._cursor.fetchone()
            
            self._cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """)
            tables = self._cursor.fetchone()
            
            return True, f"Connected successfully. Found {tables[0]} tables."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def get_schemas(self) -> List[str]:
        """Get available schemas."""
        if not self._conn:
            self.connect()
        
        self._cursor.execute("""
            SELECT DISTINCT table_schema 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_internal')
            ORDER BY table_schema
        """)
        
        return [row[0] for row in self._cursor.fetchall()]
    
    def get_tables(self, schema: str) -> List[TableInfo]:
        """Get tables in a schema."""
        if not self._conn:
            self.connect()
        
        self._cursor.execute(f"""
            SELECT table_schema, table_name
            FROM information_schema.tables 
            WHERE table_schema = %s
            ORDER BY table_name
        """, (schema,))
        
        tables = []
        for row in self._cursor.fetchall():
            tables.append(TableInfo(
                schema_name=row[0],
                table_name=row[1],
            ))
        
        return tables
    
    def get_table_schema(self, schema: str, table: str) -> TableSchema:
        """Get table schema information."""
        if not self._conn:
            self.connect()
        
        self._cursor.execute(f"""
            SELECT 
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        
        columns = [
            ColumnInfo(
                column_name=row[0],
                data_type=row[1],
                is_nullable=row[2] == "YES",
            )
            for row in self._cursor.fetchall()
        ]
        
        row_count = self.get_row_count(schema, table)
        
        return TableSchema(
            schema_name=schema,
            table_name=table,
            columns=columns,
            row_count=row_count,
        )
    
    def get_row_count(self, schema: str, table: str) -> int:
        """Get approximate row count for a table (using statistics for performance)."""
        if not self._conn:
            self.connect()
        
        # Use SVV_TABLE_INFO for faster count on large tables
        try:
            self._cursor.execute(f"""
                SELECT tbl_rows 
                FROM svv_table_info 
                WHERE "schema" = %s AND "table" = %s
            """, (schema, table))
            result = self._cursor.fetchone()
            if result:
                return int(result[0])
        except Exception:
            pass
        
        # Fallback to COUNT(*)
        self._cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        result = self._cursor.fetchone()
        return result[0] if result else 0
    
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        if not self._conn:
            self.connect()
        
        self._cursor.execute(query)
        columns = [desc[0] for desc in self._cursor.description]
        rows = self._cursor.fetchall()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def stream_query(
        self, 
        query: str, 
        batch_size: int = 1000
    ) -> Iterator[List[Dict[str, Any]]]:
        """Stream query results in batches."""
        if not self._conn:
            self.connect()
        
        # Use server-side cursor for large result sets
        cursor_name = f"sync_cursor_{id(self)}"
        
        try:
            # Declare cursor
            self._cursor.execute(f"DECLARE {cursor_name} CURSOR FOR {query}")
            
            while True:
                # Fetch batch
                self._cursor.execute(f"FETCH {batch_size} FROM {cursor_name}")
                rows = self._cursor.fetchall()
                
                if not rows:
                    break
                
                columns = [desc[0] for desc in self._cursor.description]
                batch = [dict(zip(columns, row)) for row in rows]
                yield batch
        finally:
            # Close cursor
            try:
                self._cursor.execute(f"CLOSE {cursor_name}")
            except Exception:
                pass


# Register adapter
SourceAdapterFactory.register("redshift", RedshiftAdapter)
