"""DuckDB source adapter for local development."""

from typing import Iterator, List, Dict, Any, Optional
import duckdb

from .base import SourceAdapter, SourceConfig, SourceAdapterFactory
from ...schemas.connection import TableInfo, ColumnInfo, TableSchema
from ...core.logging import get_logger

logger = get_logger(__name__)


class DuckDBAdapter(SourceAdapter):
    """DuckDB adapter for local development and testing."""
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
    
    def connect(self) -> bool:
        """Connect to DuckDB database."""
        try:
            path = self.config.duckdb_path or ":memory:"
            self._conn = duckdb.connect(path)
            logger.info("Connected to DuckDB", path=path)
            
            # Auto-initialize sample data for in-memory databases
            if path == ":memory:":
                self.init_sample_data()
            
            return True
        except Exception as e:
            logger.error("Failed to connect to DuckDB", error=str(e))
            raise
    
    def disconnect(self) -> None:
        """Close DuckDB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Disconnected from DuckDB")
    
    def test_connection(self) -> tuple[bool, str]:
        """Test DuckDB connection."""
        try:
            if not self._conn:
                self.connect()
            
            result = self._conn.execute("SELECT 1").fetchone()
            tables = self._conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
            ).fetchone()
            
            return True, f"Connected successfully. Found {tables[0]} tables."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def get_schemas(self) -> List[str]:
        """Get available schemas."""
        if not self._conn:
            self.connect()
        
        result = self._conn.execute("""
            SELECT DISTINCT table_schema 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema
        """).fetchall()
        
        return [row[0] for row in result]
    
    def get_tables(self, schema: str) -> List[TableInfo]:
        """Get tables in a schema."""
        if not self._conn:
            self.connect()
        
        result = self._conn.execute(f"""
            SELECT table_schema, table_name
            FROM information_schema.tables 
            WHERE table_schema = '{schema}'
            ORDER BY table_name
        """).fetchall()
        
        tables = []
        for row in result:
            tables.append(TableInfo(
                schema_name=row[0],
                table_name=row[1],
            ))
        
        return tables
    
    def get_table_schema(self, schema: str, table: str) -> TableSchema:
        """Get table schema information."""
        if not self._conn:
            self.connect()
        
        result = self._conn.execute(f"""
            SELECT 
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table}'
            ORDER BY ordinal_position
        """).fetchall()
        
        columns = [
            ColumnInfo(
                column_name=row[0],
                data_type=row[1],
                is_nullable=row[2] == "YES",
            )
            for row in result
        ]
        
        row_count = self.get_row_count(schema, table)
        
        return TableSchema(
            schema_name=schema,
            table_name=table,
            columns=columns,
            row_count=row_count,
        )
    
    def get_row_count(self, schema: str, table: str) -> int:
        """Get row count for a table."""
        if not self._conn:
            self.connect()
        
        result = self._conn.execute(
            f'SELECT COUNT(*) FROM "{schema}"."{table}"'
        ).fetchone()
        
        return result[0] if result else 0
    
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        if not self._conn:
            self.connect()
        
        result = self._conn.execute(query)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def stream_query(
        self, 
        query: str, 
        batch_size: int = 1000
    ) -> Iterator[List[Dict[str, Any]]]:
        """Stream query results in batches."""
        if not self._conn:
            self.connect()
        
        result = self._conn.execute(query)
        columns = [desc[0] for desc in result.description]
        
        while True:
            rows = result.fetchmany(batch_size)
            if not rows:
                break
            
            batch = [dict(zip(columns, row)) for row in rows]
            yield batch
    
    def init_sample_data(self):
        """Initialize sample customer data for testing."""
        if not self._conn:
            self.connect()
        
        # Create schema
        self._conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        
        # Create customers table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics.customers (
                id INTEGER PRIMARY KEY,
                external_id VARCHAR,
                email VARCHAR,
                phone VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                city VARCHAR,
                state VARCHAR,
                country VARCHAR,
                lifetime_value DOUBLE,
                total_orders INTEGER,
                last_order_date DATE,
                signup_date DATE,
                is_subscribed BOOLEAN,
                updated_at TIMESTAMP
            )
        """)
        
        # Insert sample data
        self._conn.execute("""
            INSERT INTO analytics.customers VALUES
            (1, 'EXT001', 'john.smith@email.com', '+14155551001', 'John', 'Smith', 'San Francisco', 'CA', 'US', 2500.50, 15, '2024-01-15', '2023-01-01', true, '2024-01-15 10:30:00'),
            (2, 'EXT002', 'sarah.j@email.com', '+14155551002', 'Sarah', 'Johnson', 'New York', 'NY', 'US', 5200.00, 32, '2024-02-20', '2022-06-15', true, '2024-02-20 14:45:00'),
            (3, 'EXT003', 'mike.w@email.com', '+14155551003', 'Michael', 'Williams', 'Chicago', 'IL', 'US', 890.25, 5, '2023-12-10', '2023-08-20', false, '2023-12-10 09:15:00'),
            (4, 'EXT004', 'emily.b@email.com', '+14155551004', 'Emily', 'Brown', 'Houston', 'TX', 'US', 3800.00, 22, '2024-03-01', '2022-11-05', true, '2024-03-01 16:20:00'),
            (5, 'EXT005', 'david.d@email.com', '+14155551005', 'David', 'Davis', 'Phoenix', 'AZ', 'US', 1200.75, 8, '2024-01-28', '2023-04-12', true, '2024-01-28 11:00:00'),
            (6, 'EXT006', 'jennifer.m@email.com', '+14155551006', 'Jennifer', 'Miller', 'Philadelphia', 'PA', 'US', 4500.00, 28, '2024-02-15', '2022-03-20', true, '2024-02-15 13:30:00'),
            (7, 'EXT007', 'robert.w@email.com', '+14155551007', 'Robert', 'Wilson', 'San Antonio', 'TX', 'US', 750.00, 3, '2023-11-20', '2023-09-01', false, '2023-11-20 08:45:00'),
            (8, 'EXT008', 'lisa.a@email.com', '+14155551008', 'Lisa', 'Anderson', 'San Diego', 'CA', 'US', 6200.50, 45, '2024-03-05', '2021-12-10', true, '2024-03-05 17:00:00'),
            (9, 'EXT009', 'james.t@email.com', '+14155551009', 'James', 'Taylor', 'Dallas', 'TX', 'US', 1850.25, 12, '2024-02-28', '2023-02-14', true, '2024-02-28 10:15:00'),
            (10, 'EXT010', 'amanda.t@email.com', '+14155551010', 'Amanda', 'Thomas', 'San Jose', 'CA', 'US', 980.00, 6, '2024-01-10', '2023-07-22', false, '2024-01-10 14:00:00')
            ON CONFLICT (id) DO NOTHING
        """)
        
        logger.info("Sample customer data initialized")


# Register adapter
SourceAdapterFactory.register("duckdb", DuckDBAdapter)
