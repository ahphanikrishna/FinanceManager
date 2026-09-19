from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from ..models import all_models as models
from .. import schemas

def get_attr(data, key):
    """Helper to safely get attributes from both Dicts and Objects (Pydantic/SQLAlchemy)"""
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)

def calculate_closing_balance(db: Session, data, user: models.User):
    # Extract data safely
    date_val = get_attr(data, "date")
    month_val = get_attr(data, "month")
    member = get_attr(data, "member") or get_attr(data, "owner") # Handle legacy 'owner' key if present
    account = get_attr(data, "account")

    # Determine Year and Month based on input type
    if date_val:
        # Input is a Transaction (has date)
        year = date_val.year
        month_num = date_val.month
        month = f"{year}-{month_num:02d}"
    elif month_val:
        # Input is a Balance Update (has month string)
        month = month_val
        year, month_num = map(int, month.split('-'))
    else:
        # Cannot calculate without date context
        return

    # 1. Get Opening Balance for this month
    query = db.query(models.Balance).filter(
        models.Balance.month == month,
        models.Balance.member == member,
        models.Balance.account == account
    ).first()

    opening_balance = query.opening_balance if query else 0.0
    
    # 2. Sum all transactions for this month
    # Note: Assuming amounts are signed (Income +, Expense -) in the DB
    existing_transactions = db.query(models.Transaction).filter(
        extract('year', models.Transaction.date) == year,
        extract('month', models.Transaction.date) == month_num,
        models.Transaction.member == member,
        models.Transaction.account == account,
        models.Transaction.user_id == user.id
    )

    # Closing = Opening + Net Change
    closing_balance = opening_balance + sum(tx.amount for tx in existing_transactions)

    if not query:
        db_balance = models.Balance(
            month=month,
            member=member,
            account=account,
            closing_balance=closing_balance,
            opening_balance=opening_balance,
            user_id=user.id
        )
        db.add(db_balance)
    else:
        query.closing_balance = closing_balance
    
    db.commit()

    # 3. Update the Opening Balance of the NEXT month
    save_opening_balance(db, schemas.BalanceUpdate(
        month=get_next_month(month),
        member=member,
        account=account,
        opening_balance=closing_balance
    ), user)

def get_next_month(month_str):
    year, month = map(int, month_str.split('-'))
    if month == 12:
        return f"{year + 1}-01"
    else:
        return f"{year}-{month + 1:02d}"
    
def save_opening_balance(db: Session, data: schemas.BalanceUpdate, user: models.User):
    existing = db.query(models.Balance).filter(
        models.Balance.member == data.member,
        models.Balance.account == data.account,
        models.Balance.month == data.month,
        models.Balance.user_id == user.id
    ).first()

    if existing:
        existing.opening_balance = data.opening_balance
        db.commit()
    else:
        new_balance = models.Balance(**data.model_dump(), user_id=user.id)
        db.add(new_balance)
        db.commit()

def remove_duplicates(db: Session):
    # Keep the record with the lowest ID for each unique combination
    keep_ids = db.query(func.min(models.Transaction.id)).group_by(
        models.Transaction.date,
        models.Transaction.description,
        models.Transaction.amount,
        models.Transaction.member,
        models.Transaction.account,
        models.Transaction.user_id
    ).all()
    
    keep_ids_list = [i[0] for i in keep_ids]

    deleted_count = db.query(models.Transaction).filter(
        ~models.Transaction.id.in_(keep_ids_list)
    ).delete(synchronize_session=False)

    db.commit()
    return deleted_count