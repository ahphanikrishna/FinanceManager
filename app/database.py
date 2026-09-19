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


def ensure_user_columns(target_engine=engine):
    """Additive migration for pre-existing databases.

    SQLite's create_all() does not add new columns to existing tables, so
    add the Gmail sync columns to users manually when missing.
    """
    from sqlalchemy import text

    with target_engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        ).fetchone()
        if table_exists is None:
            return
        existing_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
        if "gmail_address" not in existing_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN gmail_address VARCHAR"))
        if "last_gmail_sync_at" not in existing_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_gmail_sync_at DATETIME"))