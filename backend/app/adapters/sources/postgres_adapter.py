"""Postgres source adapter.

Used both as a Postgres source for the Reverse ETL platform AND as the
local-warehouse driver that replaces Redshift in the CDP demo (data lives
in warehouse-postgres, seeded from cdp-main/data/demo via
cube/scripts/seed_warehouse_from_duckdb.py).
"""

from typing import Iterator, List, Dict, Any, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    psycopg2 = None
    RealDictCursor = None
    POSTGRES_AVAILABLE = False

from .base import SourceAdapter, SourceConfig, SourceAdapterFactory
from ...schemas.connection import TableInfo, ColumnInfo, TableSchema
from ...core.logging import get_logger

logger = get_logger(__name__)


class PostgresAdapter(SourceAdapter):
    """Postgres source adapter (also serves the local CDP warehouse)."""

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._conn = None
        self._cursor = None

    def connect(self) -> bool:
        if not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 not installed. Install with: pip install psycopg2-binary")

        try:
            self._conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port or 5432,
                dbname=self.config.database,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=30,
            )
            self._conn.set_session(readonly=True, autocommit=True)
            self._cursor = self._conn.cursor()
            logger.info("Connected to Postgres", host=self.config.host, database=self.config.database)
            return True
        except Exception as e:
            logger.error("Failed to connect to Postgres", error=str(e))
            raise

    def disconnect(self) -> None:
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Disconnected from Postgres")

    def test_connection(self) -> tuple[bool, str]:
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
        if not self._conn:
            self.connect()

        self._cursor.execute("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema
        """)
        return [row[0] for row in self._cursor.fetchall()]

    def get_tables(self, schema: str) -> List[TableInfo]:
        if not self._conn:
            self.connect()

        self._cursor.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
            """,
            (schema,),
        )
        return [TableInfo(schema_name=row[0], table_name=row[1]) for row in self._cursor.fetchall()]

    def get_table_schema(self, schema: str, table: str) -> TableSchema:
        if not self._conn:
            self.connect()

        self._cursor.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        columns = [
            ColumnInfo(
                column_name=row[0],
                data_type=row[1],
                is_nullable=row[2] == "YES",
            )
            for row in self._cursor.fetchall()
        ]
        return TableSchema(
            schema_name=schema,
            table_name=table,
            columns=columns,
            row_count=self.get_row_count(schema, table),
        )

    def get_row_count(self, schema: str, table: str) -> int:
        """Approximate count via pg_stat_user_tables; fall back to exact COUNT(*)."""
        if not self._conn:
            self.connect()

        try:
            self._cursor.execute(
                """
                SELECT n_live_tup
                FROM pg_stat_user_tables
                WHERE schemaname = %s AND relname = %s
                """,
                (schema, table),
            )
            result = self._cursor.fetchone()
            if result and result[0] is not None and result[0] > 0:
                return int(result[0])
        except Exception:
            pass

        self._cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        result = self._cursor.fetchone()
        return result[0] if result else 0

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        if not self._conn:
            self.connect()

        self._cursor.execute(query)
        columns = [desc[0] for desc in self._cursor.description]
        return [dict(zip(columns, row)) for row in self._cursor.fetchall()]

    def stream_query(
        self,
        query: str,
        batch_size: int = 1000,
    ) -> Iterator[List[Dict[str, Any]]]:
        """Server-side cursor for memory-bounded streaming over large tables."""
        if not self._conn:
            self.connect()

        # psycopg2 server-side cursor: named cursor + itersize for batched fetch.
        # Read-only autocommit session means we open a fresh transaction here.
        with self._conn.cursor(name=f"sync_cursor_{id(self)}") as ss_cursor:
            ss_cursor.itersize = batch_size
            ss_cursor.execute(query)
            columns = [desc[0] for desc in ss_cursor.description]

            batch: List[Dict[str, Any]] = []
            for row in ss_cursor:
                batch.append(dict(zip(columns, row)))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch


SourceAdapterFactory.register("postgres", PostgresAdapter)
