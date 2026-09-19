import pandas as pd
import sqlite3
import os
import sys
from datetime import date, datetime


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def copy_data_from_sqlite_to_csv():
    # 1. Define the path to your SQLite database file
    db_file = "C:/Users/Phani/Documents/Python Scripts/projects/StatementManager/backend/bank_data_prod.db"
    excel_file = "D:/Projects/Python/FinanceManager/data/bank_data.xlsx"

    with sqlite3.connect(db_file) as conn:
            
            # 3. Write the SQL Query
            # You can query a whole table: "SELECT * FROM employees"
            # OR you can query specific columns: "SELECT name, salary FROM employees"

            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            # Extract just the names (it comes back as a list of single-element tuples)
            table_names = [table[0] for table in tables]

            excel_writer = pd.ExcelWriter(excel_file, engine='openpyxl')

            for table in table_names:
                print(f"Table: {table}")
                sql_query = f"SELECT * FROM {table}"
            
                print(f"\n⚙️ Reading data from SQLite...")
                
                # 4. Use pd.read_sql_query() to execute the query and load results into a DataFrame
                df = pd.read_sql_query(sql_query, conn)
                
                print(f"✅ Data successfully loaded into a Pandas DataFrame. Rows: {len(df)}")
                
                # 5. Export the DataFrame to an Excel file
                df.to_excel(excel_writer, sheet_name=table, index=False) # index=False prevents writing the Pandas internal index number

            excel_writer.close()
            print(f"\n✨ Success! Data has been saved to {excel_file}")


def _value(row, *names, default=None):
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return default


def _excel_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    if isinstance(value, (int, float)):
        return pd.to_datetime(value, unit="D", origin="1899-12-30").date()
    return pd.to_datetime(value, dayfirst=True).date()


def _database_url(db_file):
    if db_file and "://" in db_file:
        return db_file
    if db_file:
        return f"sqlite:///{os.path.abspath(db_file)}"

    from app.config import settings
    return settings.DATABASE_URL


def copy_csv_to_sqlite(excel_file, table_name=None, db_file=None):
    """Import an exported FinanceManager Excel workbook into a SQLite database.

    The historical function name is retained for compatibility. ``excel_file``
    may be an .xlsx file or a directory containing CSV files. When ``db_file``
    is omitted, the database selected by APP_ENV is used.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import Account, Balance, Category, Member, Transaction, User

    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"Input file not found: {excel_file}")

    engine = create_engine(_database_url(db_file), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    imported = {name: 0 for name in ("users", "categories", "members", "accounts", "transactions", "monthly_balances")}
    user_ids = {}

    try:
        if excel_file.lower().endswith((".xlsx", ".xls")):
            workbook = pd.ExcelFile(excel_file)
            sheets = {name: pd.read_excel(excel_file, sheet_name=name).to_dict("records") for name in workbook.sheet_names}
        else:
            if not table_name:
                raise ValueError("table_name is required when importing a CSV file")
            sheets = {table_name: pd.read_csv(excel_file).to_dict("records")}

        for row in sheets.get("users", []):
            username = str(_value(row, "username", default="")).strip()
            if not username:
                continue
            user = session.query(User).filter(User.username == username).first()
            if user is None:
                user_values = {
                    "username": username,
                    "hashed_password": _value(row, "hashed_password", default=""),
                }
                email = _value(row, "email")
                if email is not None:
                    user_values["email"] = email
                user = User(**user_values)
                session.add(user)
                session.flush()
                imported["users"] += 1
            user_ids[_value(row, "id")] = user.id

        for row in sheets.get("categories", []):
            user_id = user_ids.get(_value(row, "user_id"), _value(row, "user_id"))
            name = str(_value(row, "Category", default="")).strip()
            subcategory = str(_value(row, "subcategory", "Subcategory", default="General")).strip()
            category_type = str(_value(row, "type", default="Expenditure")).strip()
            if not name or not user_id:
                continue
            exists = session.query(Category).filter_by(
                Category=name, subcategory=subcategory, type=category_type, user_id=user_id
            ).first()
            if exists is None:
                session.add(Category(Category=name, subcategory=subcategory, type=category_type, user_id=user_id))
                imported["categories"] += 1

        for row in sheets.get("members", []):
            user_id = user_ids.get(_value(row, "user_id"), _value(row, "user_id"))
            name = str(_value(row, "name", default="")).strip()
            if not name or not user_id or session.query(Member).filter_by(name=name, user_id=user_id).first():
                continue
            session.add(Member(name=name, user_id=user_id))
            imported["members"] += 1

        for row in sheets.get("accounts", []):
            user_id = user_ids.get(_value(row, "user_id"), _value(row, "user_id"))
            account_name = str(_value(row, "account_name", default="")).strip()
            account_type = str(_value(row, "account_type", default="")).strip()
            if not account_name or not account_type or not user_id or session.query(Account).filter_by(
                account_name=account_name, account_type=account_type, user_id=user_id
            ).first():
                continue
            session.add(Account(account_name=account_name, account_type=account_type, user_id=user_id))
            imported["accounts"] += 1

        session.flush()
        for row in sheets.get("transactions", []):
            user_id = user_ids.get(_value(row, "user_id"), _value(row, "user_id"))
            transaction_date = _excel_date(_value(row, "date"))
            if not user_id or transaction_date is None:
                continue
            values = {
                "date": transaction_date,
                "member": _value(row, "member", default=""),
                "account": _value(row, "account", default=""),
                "account_type": _value(row, "account_type", default=""),
                "description": _value(row, "description", default=""),
                "type": _value(row, "type", default="Expenditure"),
                "amount": float(_value(row, "amount", default=0)),
                "category": _value(row, "category", default="Uncategorized"),
                "subcategory": _value(row, "subcategory", "Subcategory", default="Uncategorized"),
                "fill_type": _value(row, "fill_type", default="A"),
                "comments": _value(row, "comments", default=""),
                "user_id": user_id,
            }
            duplicate = session.query(Transaction).filter_by(
                date=values["date"], member=values["member"], description=values["description"],
                amount=values["amount"], account=values["account"], type=values["type"],
                category=values["category"], user_id=user_id,
            ).first()
            if duplicate is None:
                session.add(Transaction(**values))
                imported["transactions"] += 1

        for row in sheets.get("monthly_balances", []):
            user_id = user_ids.get(_value(row, "user_id"), _value(row, "user_id"))
            values = {
                "month": _value(row, "month"),
                "member": _value(row, "member"),
                "account_name": _value(row, "account_name"),
                "account_type": _value(row, "account_type"),
                "opening_balance": float(_value(row, "opening_balance", default=0)),
                "closing_balance": float(_value(row, "closing_balance", default=0)),
                "user_id": user_id,
            }
            if not all(values[key] for key in ("month", "member", "account_name", "account_type", "user_id")):
                continue
            duplicate = session.query(Balance).filter_by(
                month=values["month"], member=values["member"], account_name=values["account_name"],
                account_type=values["account_type"], user_id=user_id,
            ).first()
            if duplicate is None:
                session.add(Balance(**values))
                imported["monthly_balances"] += 1

        session.commit()
        print(f"Imported into {_database_url(db_file)}: {imported}")
        return imported
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import FinanceManager Excel data into the selected database.")
    parser.add_argument("excel_file", nargs="?", default=os.path.join(os.path.dirname(__file__), "bank_data.xlsx"))
    parser.add_argument("--db-file", help="Target SQLite file. Defaults to the database selected by APP_ENV.")
    args = parser.parse_args()
    copy_csv_to_sqlite(args.excel_file, db_file=args.db_file)