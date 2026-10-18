"""SQLAlchemy engine and session helpers.

Used when `DATABASE_URL` is provided to let the app interact with a
Postgres database via SQLAlchemy ORM or core. This module is intentionally
minimal — it's a shim to let you create tables and run migrations.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = None
SessionLocal = None

def init_engine(url=None):
    global engine, SessionLocal
    url = url or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL not set; cannot init SQLAlchemy engine")
    engine = create_engine(url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine

def get_engine():
    if engine is None:
        init_engine()
    return engine

def get_session():
    if SessionLocal is None:
        init_engine()
    return SessionLocal()
