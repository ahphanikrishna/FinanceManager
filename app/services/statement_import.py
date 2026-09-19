"""Imports downloaded statement files into the transactions table.

Wraps the bank parsers from app/services/parsers with a filename-based
guess, so Gmail-downloaded files can be imported with one call.
"""
import importlib
import os
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import Transaction

_PARSER_MODULES = {
    "sbi": ("app.services.parsers.sbi_parser", ["parse_sbi_excel", "parse_sbi_pdf"]),
    "hdfc": ("app.services.parsers.hdfc_parser", ["parse_hdfc_excel", "parse_hdfc_pdf"]),
    "axis": ("app.services.parsers.axis_parser", ["parse_axis_excel", "parse_axis_pdf"]),
    "hdfc_cc": ("app.services.parsers.hdfc_cc_parser", ["parse_hdfc_cc_pdf"]),
}


def guess_parsers(filename):
    """Ordered candidate (module, function) parser pairs for a statement file."""
    name = os.path.basename(filename).lower()
    ext = os.path.splitext(name)[1]
    families = []
    if "sbi" in name:
        families.append("sbi")
    if "cc" in name or "credit card" in name or "creditcard" in name:
        families.append("hdfc_cc")
    if "hdfc" in name:
        families.append("hdfc")
    if "axis" in name:
        families.append("axis")
    if not families:
        if ext in (".xlsx", ".xls"):
            families = ["sbi", "hdfc", "axis"]
        elif ext == ".pdf":
            families = ["sbi", "hdfc", "hdfc_cc", "axis"]
        else:
            return []
    candidates = []
    for family in families:
        module_name, function_names = _PARSER_MODULES[family]
        for function_name in function_names:
            candidates.append((module_name, function_name))
    return candidates


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(value), pattern).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported transaction date: {value}")


def import_statement_file(session: Session, user_id, file_path, account, member, password=None):
    """Try candidate parsers in order and import the first one that yields rows.

    account/member are Account/Member model instances (for the user).
    Returns {"file", "parser", "imported", "skipped"}.
    """
    report = {
        "file": os.path.basename(file_path),
        "parser": None,
        "imported": 0,
        "skipped": 0,
        "error": None,
    }
    for module_name, function_name in guess_parsers(file_path):
        module = importlib.import_module(module_name)
        parser = getattr(module, function_name)
        try:
            parsed = parser(file_path, password=password) or []
        except Exception:
            continue
        if not parsed:
            continue

        report["parser"] = function_name
        for item in parsed:
            try:
                transaction_date = _parse_date(item["date"])
            except Exception:
                report["skipped"] += 1
                continue
            transaction = Transaction(
                date=transaction_date,
                member=member.name,
                account=account.account_name,
                account_type=account.account_type,
                description=str(item.get("description", "")).strip(),
                type=item.get("type", "Expenditure"),
                amount=float(item.get("amount", 0)),
                category="Uncategorized",
                subcategory="Uncategorized",
                fill_type="Automatic",
                comments="",
                user_id=user_id,
            )
            session.add(transaction)
            try:
                session.commit()
                report["imported"] += 1
            except IntegrityError:
                session.rollback()
                report["skipped"] += 1
        break
    return report


def import_statements_for_month(session: Session, user_id, files, account, member, password=None):
    """Import several downloaded files; per-file reports."""
    reports = []
    for file_path in files:
        try:
            reports.append(import_statement_file(session, user_id, file_path, account, member, password=password))
        except (ValueError, OSError, SQLAlchemyError) as error:
            reports.append({
                "file": os.path.basename(file_path),
                "parser": None,
                "imported": 0,
                "skipped": 0,
                "error": str(error),
            })
    return reports
