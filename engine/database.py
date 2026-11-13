"""Neon PostgreSQL database setup for DietCode's billing ledger."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()


def _database_url() -> str:
    """Read and normalize the required Neon PostgreSQL connection string."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Add your Neon PostgreSQL connection "
            "string to the project .env file."
        )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )
    if not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL connection string from Neon."
        )
    return database_url


DATABASE_URL = _database_url()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialize_database() -> None:
    """Create all declared tables in Neon for the current environment."""
    try:
        from .models import billing  # noqa: F401
    except ImportError:
        from models import billing  # noqa: F401
    Base.metadata.create_all(bind=engine)
