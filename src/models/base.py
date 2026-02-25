"""
SQLAlchemy base configuration and database utilities.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
from typing import Optional
from pathlib import Path

from ..config.settings import get_settings

# Create declarative base
Base = declarative_base()

# Module-level engine and session factory
_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _engine

    if _engine is None:
        settings = get_settings()
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=settings.app_debug,
            connect_args={"check_same_thread": False}
        )

    return _engine


def get_session() -> Session:
    """Get a new database session."""
    global _SessionFactory

    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False
        )

    return _SessionFactory()


def init_database() -> None:
    """Initialize the database, creating all tables."""
    # Import all models to ensure they're registered with Base
    from . import user, chat  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)


class DatabaseSession:
    """Context manager for database sessions."""

    def __init__(self):
        self.session: Optional[Session] = None

    def __enter__(self) -> Session:
        self.session = get_session()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is not None:
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()
        return False
