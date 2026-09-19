
import datetime
import re
from sqlalchemy.orm import relationship, validates
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint
from flask_login import UserMixin
from .database import Base

class User(UserMixin, Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    @validates("email")
    def validate_email(self, key, address):
        """Validate email format before inserting/updating."""
        EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        if not EMAIL_REGEX.match(address):
            raise ValueError(f"Invalid email address: {address}")
        return address.lower()  # normalize to lowercase
    
    # One user can have many transactions
    transactions = relationship("Transaction", back_populates="owner_user")
    categories = relationship("Category", back_populates="owner_user")
    members = relationship("Member", back_populates="owner_user")
    accounts = relationship("Account", back_populates="owner_user")
    monthly_balances = relationship("Balance", back_populates="owner_user")

class Transaction(Base):  # <--- MUST be "Transaction"
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    member = Column(String)
    account = Column(String)
    account_type = Column(String)
    date = Column(Date)
    description = Column(String)
    type = Column(String)
    amount = Column(Float)
    category = Column(String, default="Uncategorized")
    subcategory = Column(String, default="Uncategorized")
    fill_type = Column(String, default="M") # Manual/Automatic
    comments = Column(String, default="")

    # THE KEY FOR MULTI-USER:
    user_id = Column(Integer, ForeignKey("users.id"))
    owner_user = relationship("User", back_populates="transactions")

    __table_args__ = (
        UniqueConstraint('date', 'member', 'description', 'amount', 'account', 'type', 'category', 'user_id', name='_tx_uc'),
    )


# Categories table
class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    Category = Column(String) # e.g., "Salary", "Groceries", "Rent"
    subcategory = Column(String, default="General") # e.g., "Food", "Transport"
    type = Column(String) # "Income" or "Expenditure"

    # THE KEY FOR MULTI-USER:
    user_id = Column(Integer, ForeignKey("users.id"))
    owner_user = relationship("User", back_populates="categories")

    __table_args__ = (
        UniqueConstraint('type', 'Category', 'subcategory', 'type', 'user_id', name='_category_uc'),
    )

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)  # e.g., "PHANI", "NAGA"

    # THE KEY FOR MULTI-USER:
    user_id = Column(Integer, ForeignKey("users.id"))
    owner_user = relationship("User", back_populates="members")

    __table_args__ = (
        UniqueConstraint('name', 'user_id', name='_member_uc'),
    )

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String)  # e.g., "SBI", "HDFC"
    account_type = Column(String)  # e.g., "Savings", "Current", "Credit Card"

    # THE KEY FOR MULTI-USER:
    user_id = Column(Integer, ForeignKey("users.id"))
    owner_user = relationship("User", back_populates="accounts")

    __table_args__ = (
        UniqueConstraint('account_name', 'account_type', 'user_id', name='_account_uc'),
    )

# models.py
class Balance(Base):
    __tablename__ = "monthly_balances"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(String, nullable=False, index=True)
    member = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    account_type = Column(String, nullable=False)
    opening_balance = Column(Float, default=0.0)
    closing_balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # THE KEY FOR MULTI-USER:
    user_id = Column(Integer, ForeignKey("users.id"))
    owner_user = relationship("User", back_populates="monthly_balances")

    __table_args__ = (UniqueConstraint('month', 'account_name', 'account_type', 'member', 'user_id', name='_month_account_member_uc'),)