"""Whole-database backup and restore.

The user's full dataset (members, accounts, categories, monthly balances,
onboarding state, and every transaction) is exported as a versioned JSON
document. Sending that document to their own Gmail mailbox lets them
restore the same data on any other device.
"""
import json
from datetime import date, datetime

from app.models import Account, Balance, Category, Member, Onboarding, Transaction

SCHEMA_VERSION = 1
BACKUP_SUBJECT_PREFIX = "Finance Tracker backup"


def export_backup(session, user_id):
    """Snapshot every data row owned by user_id as a JSON-safe dict."""
    user_id = int(user_id)
    members = session.query(Member).filter_by(user_id=user_id).order_by(Member.id).all()
    accounts = session.query(Account).filter_by(user_id=user_id).order_by(Account.id).all()
    categories = (
        session.query(Category).filter_by(user_id=user_id).order_by(Category.id).all()
    )
    balances = (
        session.query(Balance).filter_by(user_id=user_id).order_by(Balance.id).all()
    )
    onboarding = session.query(Onboarding).filter_by(user_id=user_id).first()
    transactions = (
        session.query(Transaction)
        .filter_by(user_id=user_id)
        .order_by(Transaction.id)
        .all()
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "members": [{"name": member.name} for member in members],
        "accounts": [
            {"account_name": account.account_name, "account_type": account.account_type}
            for account in accounts
        ],
        "categories": [
            {
                "category": category.Category,
                "subcategory": category.subcategory,
                "type": category.type,
            }
            for category in categories
        ],
        "balances": [
            {
                "month": balance.month,
                "member": balance.member,
                "account_name": balance.account_name,
                "account_type": balance.account_type,
                "opening_balance": balance.opening_balance,
                "closing_balance": balance.closing_balance,
            }
            for balance in balances
        ],
        "onboarding": {
            "current_step": onboarding.current_step if onboarding else 0,
            "monthly_budget": onboarding.monthly_budget if onboarding else None,
            "completed_at": (
                onboarding.completed_at.isoformat()
                if onboarding and onboarding.completed_at
                else None
            ),
        },
        "transactions": [
            {
                "member": tx.member,
                "account": tx.account,
                "account_type": tx.account_type,
                "date": tx.date.isoformat() if tx.date else None,
                "description": tx.description,
                "type": tx.type,
                "amount": tx.amount,
                "category": tx.category,
                "subcategory": tx.subcategory,
                "fill_type": tx.fill_type,
                "comments": tx.comments,
            }
            for tx in transactions
        ],
    }


def export_backup_json(session, user_id):
    return json.dumps(export_backup(session, user_id), indent=2)


def import_backup(session, user_id, payload):
    """Replace the user's data with an exported backup. Returns row counts.

    Raises ValueError for payloads that are not Finance Tracker backups.
    """
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Not a valid Finance Tracker backup file.")
    user_id = int(user_id)

    # Restore = replace: wipe the user's data, then re-insert the snapshot.
    session.query(Transaction).filter_by(user_id=user_id).delete()
    session.query(Balance).filter_by(user_id=user_id).delete()
    session.query(Category).filter_by(user_id=user_id).delete()
    session.query(Account).filter_by(user_id=user_id).delete()
    session.query(Member).filter_by(user_id=user_id).delete()
    onboarding = session.query(Onboarding).filter_by(user_id=user_id).first()
    if onboarding is not None:
        session.delete(onboarding)
    session.flush()

    for entry in payload.get("members", []):
        session.add(Member(user_id=user_id, name=entry.get("name")))
    for entry in payload.get("accounts", []):
        session.add(
            Account(
                user_id=user_id,
                account_name=entry.get("account_name"),
                account_type=entry.get("account_type"),
            )
        )
    for entry in payload.get("categories", []):
        session.add(
            Category(
                user_id=user_id,
                Category=entry.get("category"),
                subcategory=entry.get("subcategory"),
                type=entry.get("type"),
            )
        )
    for entry in payload.get("balances", []):
        session.add(
            Balance(
                user_id=user_id,
                month=entry.get("month"),
                member=entry.get("member"),
                account_name=entry.get("account_name"),
                account_type=entry.get("account_type"),
                opening_balance=entry.get("opening_balance") or 0.0,
                closing_balance=entry.get("closing_balance") or 0.0,
            )
        )

    obs = payload.get("onboarding") or {}
    completed_raw = obs.get("completed_at")
    session.add(
        Onboarding(
            user_id=user_id,
            current_step=obs.get("current_step") or 0,
            monthly_budget=obs.get("monthly_budget"),
            completed_at=datetime.fromisoformat(completed_raw) if completed_raw else None,
        )
    )

    for entry in payload.get("transactions", []):
        raw_date = entry.get("date")
        session.add(
            Transaction(
                user_id=user_id,
                member=entry.get("member"),
                account=entry.get("account"),
                account_type=entry.get("account_type"),
                date=date.fromisoformat(raw_date) if raw_date else None,
                description=entry.get("description"),
                type=entry.get("type"),
                amount=entry.get("amount"),
                category=entry.get("category") or "Uncategorized",
                subcategory=entry.get("subcategory") or "Uncategorized",
                fill_type=entry.get("fill_type") or "M",
                comments=entry.get("comments") or "",
            )
        )

    return {
        "members": len(payload.get("members", [])),
        "accounts": len(payload.get("accounts", [])),
        "categories": len(payload.get("categories", [])),
        "balances": len(payload.get("balances", [])),
        "transactions": len(payload.get("transactions", [])),
    }
