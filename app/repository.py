from app.database import SessionLocal, Base, engine
from typing import Any, TypeVar, Type

# Define a type for the session object for clearer function signatures
Session = TypeVar("Session") # Type hint placeholder

class DatabaseRepository:
    """
    A centralized repository layer for all database operations.
    This class handles the boilerplate of opening sessions and interacting
    with the ORM, keeping business logic clean and testable.
    """
    def __init__(self, engine=engine, session_local=SessionLocal):
        self.engine = engine
        self.SessionLocal = session_local

    def initialize_db(self) -> None:
        """
        Initializes the database schema by creating all defined tables.
        This method must be called once at application startup.
        """
        print("--- Initializing database schema ---")
        Base.metadata.create_all(self.engine)
        print("--- Database schema initialized successfully ---")

    def get_session(self) -> Session:
        """
        Returns a new, isolated database session.
        The caller is responsible for committing or rolling back the transaction
        and closing the session.
        """
        return self.SessionLocal()

    def get_all(self, model: Type[Base]) -> list:
        """
        Generic retrieval function: fetches all records of a given model.
        """
        with self.SessionLocal() as session:
            records = session.query(model).all()
            return records

    def get_by_id(self, model: Type[Base], primary_key: any) -> Type[Base] | None:
        """
        Generic retrieval function: fetches a single record by its primary key.
        """
        with self.SessionLocal() as session:
            # Assumes the primary key field name is 'id'
            return session.query(model).filter(model.id == primary_key).first()

    def get_by_field(self, model: Type[Base], field_name: str, value: any) -> Type[Base] | None:
        """
        Generic retrieval function: fetches a single record by a specified field.
        """
        with self.SessionLocal() as session:
            field = getattr(model, field_name, None)
            if field is None:
                raise AttributeError(f"{model.__name__} has no attribute '{field_name}'")
            return session.query(model).filter(field == value).first()

    def add_record(self, model: Type[Base], data: dict) -> Type[Base]:
        """
        Generic creation function: adds a new record and returns the created object.
        """
        with self.SessionLocal() as session:
            # Logic here needs to map 'data' keys to model attributes
            # For simplicity, we assume the model constructor/init can handle the dict
            instance = model(**data)
            session.add(instance)
            session.commit()
            return instance

    def add_multiple_records(self, model: Type[Base], data_list: list[dict]) -> list[Type[Base]]:
        """
        Generic creation function: adds multiple new records and returns the created objects.
        """
        with self.SessionLocal() as session:
            instances = [model(**data) for data in data_list]
            session.add_all(instances)
            session.commit()
            return instances

    def update_record(self, model_instance: Type[Base], data: dict) -> Type[Base]:
        """
        Generic update function: updates an existing record.
        """
        with self.SessionLocal() as session:
            # Assume model_instance is already loaded in the session
            for key, value in data.items():
                setattr(model_instance, key, value)
            session.commit()
            return model_instance

    def delete_record(self, model: Type[Base], primary_key: any) -> bool:
        """Deletes a record by its primary key."""

        session = self.get_session()
        record = self.get_by_id(model, primary_key)
        if record:
            try:
                # SQLAlchemy requires delete() call on the instance
                session.delete(record)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"Error deleting record: {e}")
                return False
        return False


def init_db_and_repo(app):
    """Initializes database schema and the central repository instance."""
    with app.app_context():
        # Initialize the global repository instance with the engine
        db_repository = DatabaseRepository(engine)
        
        # Store the repository instance on the app object for global access
        app.db_repository = db_repository
        
        # Centralize database setup via the repository method
        db_repository.initialize_db()
        
        print("Database schema initialized and Repository ready.")

# Usage Example (This would go into run.py or your main service file)
# from app.database import Base
# from app.models import User
# 
# # 1. Initialize the repository object
# repo = DatabaseRepository(session_local=SessionLocal)
# 
# # 2. Usage:
# # new_user = repo.add_record(User, {"username": "new_user", "email": "new@example.com"})
# # users = repo.get_all(User)
# # user_profile = repo.get_by_id(User, 1)