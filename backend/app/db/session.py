"""Database session management - Cloud-agnostic."""

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from ..core.config import get_settings

settings = get_settings()


def get_database_url() -> str:
    """
    Get database URL with fallback for local development.
    
    Priority:
    1. DATABASE_URL environment variable (cloud deployments)
    2. Constructed PostgreSQL URL from individual settings
    3. SQLite fallback for quick local testing
    """
    # Primary: Use DATABASE_URL if set and contains postgresql
    if settings.database_url and "postgresql" in settings.database_url:
        try:
            # Test if we can connect
            test_engine = create_engine(settings.database_url, pool_pre_ping=True)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return settings.database_url
        except Exception:
            pass
    
    # Fallback: Construct from individual settings
    try:
        postgres_url = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
        # Test if we can connect
        test_engine = create_engine(postgres_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return postgres_url
    except Exception:
        pass
    
    # Final fallback: SQLite for quick local development
    # Avoid noisy stdout in scripts/imports; the app can still run with SQLite locally.
    return "sqlite:///./activationos.db"


# Get the database URL
DATABASE_URL = get_database_url()

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
