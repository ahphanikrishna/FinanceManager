from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# Handle SQLite specific connect_args
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

# The core engine object
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
# The session factory
SessionLocal = sessionmaker(
	autocommit=False,
	autoflush=False,
	expire_on_commit=False,
	bind=engine,
)
# The declarative base for models
Base = declarative_base()