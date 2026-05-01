"""Application configuration with cloud-agnostic settings."""

from functools import lru_cache
from typing import Optional, Literal, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ==========================================================================
    # Application
    # ==========================================================================
    app_name: str = "Alo ActivationOS"
    app_env: Literal["development", "staging", "production"] = "development"
    debug_mode: bool = Field(default=True)
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    
    # ==========================================================================
    # API
    # ==========================================================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    public_demo_url: str = "http://localhost/dashboard"
    admin_analytics_key: str = ""
    
    # ==========================================================================
    # Database - PostgreSQL (Cloud-agnostic)
    # Works with: AWS RDS, GCP Cloud SQL, Azure Database, local Docker
    # ==========================================================================
    database_url: str = Field(
        default="postgresql://activationos:activationos@localhost:5432/activationos",
        description="PostgreSQL connection URL"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Legacy support (can be removed later)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "activationos"
    postgres_password: str = "activationos"
    postgres_db: str = "activationos"
    
    @property
    def postgres_url(self) -> str:
        """Legacy property for backwards compatibility."""
        return self.database_url
    
    # ==========================================================================
    # Cache & Queue - Redis (Cloud-agnostic)
    # Works with: AWS ElastiCache, GCP Memorystore, Azure Cache, local Docker
    # ==========================================================================
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )
    redis_max_connections: int = 10
    cache_ttl_seconds: int = 300  # 5 minutes default
    
    # ==========================================================================
    # Object Storage - S3-Compatible (Cloud-agnostic)
    # Works with: AWS S3, GCP GCS (via S3 API), Azure Blob, MinIO
    # ==========================================================================
    storage_endpoint: str = Field(
        default="http://localhost:9000",
        description="S3-compatible endpoint URL"
    )
    storage_access_key: str = Field(default="minioadmin")
    storage_secret_key: str = Field(default="minioadmin")
    storage_bucket: str = Field(default="activationos")
    storage_region: str = Field(default="us-east-1")
    storage_use_ssl: bool = Field(default=False)
    
    # ==========================================================================
    # Data Warehouse Sources
    # ==========================================================================
    warehouse_mode: str = Field(default="duckdb", description="duckdb or redshift")

    # dbt / DuckDB transform store
    dbt_duckdb_path: str = Field(
        default="/Users/utkarshparekh/BridgeSync/platform/dbt/activationos_transform.duckdb",
        description="Path to dbt DuckDB file used for marts"
    )
    
    # DuckDB (Local development / Demo)
    duckdb_path: str = ":memory:"
    
    # Redshift (Production)
    redshift_host: Optional[str] = None
    redshift_port: int = 5439
    redshift_user: Optional[str] = None
    redshift_password: Optional[str] = None
    redshift_database: Optional[str] = None

    # ==========================================================================
    # C360 / Ask (Local-first: Redshift + Ollama)
    # ==========================================================================
    # Ollama (host process): http://127.0.0.1:11434
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="gpt-oss:20b")
    ollama_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    ollama_max_tokens: int = Field(default=1200, ge=64, le=8192)

    # Redshift read-only execution guardrails
    c360_redshift_ssl: bool = Field(default=False)
    c360_query_timeout_seconds: int = Field(default=30, ge=1, le=300)
    c360_max_rows: int = Field(default=200, ge=1, le=5000)

    # Allowlisted marts (schema-qualified). Keep tight; expand intentionally.
    c360_allowed_tables: List[str] = Field(
        default_factory=lambda: [
            # DBT C360 marts / snapshots (see alo-data-stack/is-redshift/warehouse/{models,snapshots}/c360)
            "gold.customer_dim",
            "gold.customer_address_dim",
            "gold.customer_identifier_dim",
            "gold.customer_loyalty_dim",
            "gold.customer_contact_prefs_dim",
            "gold.customer_geo_segment",
            "gold.order_line_fact",
            "gold.customer_rfm_fact",
            "gold.customer_unified_attr",
        ]
    )

    # PII handling
    c360_anon_salt: str = Field(default="c360_local_salt_change_me")
    c360_drop_cols: List[str] = Field(
        default_factory=lambda: ["email", "phone", "email_address", "phone_number"]
    )
    c360_id_cols: List[str] = Field(default_factory=lambda: ["customer_id"])
    
    # BigQuery (Production - GCP)
    bigquery_project: Optional[str] = None
    bigquery_credentials_json: Optional[str] = None
    
    # Snowflake (Production)
    snowflake_account: Optional[str] = None
    snowflake_user: Optional[str] = None
    snowflake_password: Optional[str] = None
    snowflake_warehouse: Optional[str] = None
    snowflake_database: Optional[str] = None
    
    # ==========================================================================
    # Security
    # ==========================================================================
    encryption_key: str = Field(default="default-encryption-key-change-in-prod")
    
    # ==========================================================================
    # Airflow Integration (Optional)
    # ==========================================================================
    airflow_enabled: bool = False
    airflow_api_url: str = "http://localhost:8080/api/v1"
    airflow_username: str = "admin"
    airflow_password: str = "admin"
    
    # ==========================================================================
    # Sync Configuration
    # ==========================================================================
    max_retries: int = 3
    retry_delay_seconds: int = 60
    sync_batch_size: int = 1000
    
    # ==========================================================================
    # Computed Properties
    # ==========================================================================
    @property
    def debug(self) -> bool:
        return self.debug_mode
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"
    
    class Config:
        env_file = ("../.env", ".env")  # Check parent dir first, then current
        env_file_encoding = "utf-8"
        populate_by_name = True
        extra = "ignore"  # Ignore extra env vars


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Alias for convenience
settings = get_settings()
