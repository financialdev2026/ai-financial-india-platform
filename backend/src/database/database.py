"""
=========================================================
Database Configuration

Central SQLAlchemy engine and session.

=========================================================
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from src.config.config import DATABASE_URL

# =====================================================
# Engine
# =====================================================

engine = create_engine(
    DATABASE_URL,
    echo=False
)

# =====================================================
# Session
# =====================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# =====================================================
# Base
# =====================================================

Base = declarative_base()


# =====================================================
# Dependency
# =====================================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()