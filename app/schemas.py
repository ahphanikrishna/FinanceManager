from typing import Type, List, Optional, Any, Set
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.orm import DeclarativeMeta

class BaseSchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

def generate_schemas(
    db_model: Type[Any],
    skip_columns: Optional[dict] = None,
    optional_columns: Optional[dict] = None,
    defaults: Optional[dict] = None
):
    """
    Dynamically generates Base, Create, and Update Pydantic schemas from a SQLAlchemy model.
    
    :param db_model: The SQLAlchemy model class.
    :param skip_columns: Dict specifying columns to skip per schema type, e.g. {"base": [...], "create": [...], "update": [...]}.
                         Can also pass a flat list/set for backwards compatibility (applied to all).
    :param optional_columns: Dict specifying optional columns per schema type, e.g. {"create": [...]}.
    :param defaults: Dictionary of default values for columns in the Create schema.
    """
    # Handle backward compatibility if skip_columns or optional_columns are passed as lists/sets
    if isinstance(skip_columns, (list, set)):
        skip_columns = {"base": skip_columns, "create": skip_columns, "update": skip_columns}
    else:
        skip_columns = skip_columns or {}

    if isinstance(optional_columns, (list, set)):
        optional_columns = {"create": optional_columns, "update": optional_columns}
    else:
        optional_columns = optional_columns or {}

    skip_base = set(skip_columns.get("base", []))
    skip_create = set(skip_columns.get("create", []))
    skip_update = set(skip_columns.get("update", []))

    opt_base = set(optional_columns.get("base", []))
    opt_create = set(optional_columns.get("create", []))
    opt_update = set(optional_columns.get("update", []))

    defaults = defaults or {}

    base_fields = {}
    create_fields = {}
    update_fields = {}

    for column in db_model.__table__.columns:
        col_name = column.name

        # Determine Python type from SQLAlchemy column type
        try:
            python_type = column.type.python_type
        except NotImplementedError:
            python_type = str  # Fallback for complex types

        # Is it nullable in DB?
        is_nullable = column.nullable
        default_val = column.default.arg if column.default is not None else ...

        # Override default if provided in arguments
        if col_name in defaults:
            default_val = defaults[col_name]
            is_nullable = True

        # 1. Base / Response Schema Field
        if col_name not in skip_base:
            base_field_type = Optional[python_type] if (is_nullable or col_name in opt_base) else python_type
            base_fields[col_name] = (base_field_type, None if (is_nullable or col_name in opt_base) else ...)

        # 2. Create Schema Field
        if col_name not in skip_create:
            is_opt_create = col_name in opt_create or is_nullable or default_val is not ...
            create_field_type = Optional[python_type] if is_opt_create else python_type
            create_fields[col_name] = (create_field_type, None if is_opt_create and default_val is ... else default_val)

        # 3. Update Schema Field (all fields optional by default for partial updates)
        if col_name not in skip_update:
            update_fields[col_name] = (Optional[python_type], None)

    model_name = db_model.__name__

    # Dynamically create Pydantic models inheriting from BaseSchemaModel
    BaseSchema = create_model(f"{model_name}Schema", __base__=BaseSchemaModel, **base_fields)
    CreateSchema = create_model(f"{model_name}Create", __base__=BaseSchemaModel, **create_fields)
    UpdateSchema = create_model(f"{model_name}Update", __base__=BaseSchemaModel, **update_fields)

    return BaseSchema, CreateSchema, UpdateSchema

from .models import User, Transaction, Category, Member, Account, Balance

# ----------------------------------------------------------------------
# === SCHEMA GENERATION FOR ALL CORE MODELS ==========================
# ----------------------------------------------------------------------

# --- User Schemas ---
UserSchema, UserCreate, UserUpdate = generate_schemas(
    db_model=User,
    skip_columns={
        "base": ["password", "hashed_password"],
        "create": ["id", "hashed_password"],
        "update": ["id", "hashed_password"]
    },
    optional_columns={
        "create": ["hashed_password"]
    }
)

# --- Transaction Schemas ---
TransactionSchema, TransactionCreate, TransactionUpdate = generate_schemas(
    db_model=Transaction,
    skip_columns={
        "base": ["id", "created_at", "updated_at"],
        "create": ["id", "created_at", "updated_at"],
        "update": ["id"]
    },
    optional_columns={
        "create": ["transaction_type", "amount", "related_user_id", "related_category_id"]
    }
)

# --- Category Schemas ---
CategorySchema, CategoryCreate, CategoryUpdate = generate_schemas(
    db_model=Category,
    skip_columns={
        "base": ["id"],
        "create": ["id"],
        "update": ["id"]
    },
    optional_columns={
        "create": ["name", "description"]
    }
)

# --- Member Schemas ---
MemberSchema, MemberCreate, MemberUpdate = generate_schemas(
    db_model=Member,
    skip_columns={
        "base": ["id"],
        "create": ["id"],
        "update": ["id"]
    },
    optional_columns={
        "create": ["name", "email", "phone"]
    }
)

# --- Account Schemas ---
AccountSchema, AccountCreate, AccountUpdate = generate_schemas(
    db_model=Account,
    skip_columns={
        "base": ["id"],
        "create": ["id"],
        "update": ["id"]
    },
    optional_columns={
        "create": ["account_type", "name", "initial_balance"]
    }
)

# --- Balance Schemas ---
BalanceSchema, BalanceCreate, BalanceUpdate = generate_schemas(
    db_model=Balance,
    skip_columns={
        "base": ["id", "created_at", "updated_at"],
        "create": ["id", "created_at", "updated_at"],
        "update": ["id"]
    },
    optional_columns={
        "create": ["user_id", "account_id", "balance_amount"]
    }
)

