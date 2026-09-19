import os
import tempfile
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import Account, Category, Member, Transaction
from app.repository import DatabaseRepository


transactions_view_bp = Blueprint("transactions_view", __name__)


PARSER_IMPORTS = {
    "SBI": ("sbi_parser", "parse_sbi_excel"),
    "HDFC": ("hdfc_parser", "parse_hdfc_excel"),
    "AXIS": ("axis_parser", "parse_axis_pdf"),
    "HDFC CC": ("hdfc_cc_parser", "parse_hdfc_cc_pdf"),
}


def _default_month():
    # Start on the previous month: it is the last fully settled period.
    previous = date.today().replace(day=1) - timedelta(days=1)
    return previous.strftime("%Y-%m")


def _selected_month():
    requested = request.args.get("month", "")
    try:
        return datetime.strptime(requested, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return _default_month()


def _month_bounds(month):
    month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    return month_start, month_end


def _user_records(session, model):
    return session.query(model).filter(model.user_id == current_user.id).order_by(model.id).all()


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


def _parser_for(provider):
    module_name, function_name = PARSER_IMPORTS[provider]
    module = __import__(f"app.services.parsers.{module_name}", fromlist=[function_name])
    return getattr(module, function_name)


@transactions_view_bp.route("/transactions")
@login_required
def transactions_page():
    selected_month = _selected_month()
    month_start, month_end = _month_bounds(selected_month)
    selected_member = request.args.get("member", "")
    selected_account = request.args.get("account", "")
    selected_type = request.args.get("type", "")
    selected_category = request.args.get("category", "")
    session = DatabaseRepository().get_session()
    try:
        transaction_query = (
            session.query(Transaction)
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.date >= month_start,
                Transaction.date < month_end,
            )
        )
        if selected_member:
            transaction_query = transaction_query.filter(Transaction.member.ilike(f"%{selected_member}%"))
        if selected_account:
            transaction_query = transaction_query.filter(Transaction.account.ilike(f"%{selected_account}%"))
        if selected_type:
            transaction_query = transaction_query.filter(Transaction.type.ilike(f"%{selected_type}%"))
        if selected_category:
            transaction_query = transaction_query.filter(Transaction.category.ilike(f"%{selected_category}%"))
        transactions = transaction_query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        categories = _user_records(session, Category)
        category_subcategories = {}
        for category in categories:
            category_subcategories.setdefault(category.Category, set()).add(category.subcategory)
        return render_template(
            "transactions.html",
            transactions=transactions,
            accounts=_user_records(session, Account),
            members=_user_records(session, Member),
            categories=categories,
            category_subcategories={
                name: sorted(values) for name, values in category_subcategories.items()
            },
            selected_month=selected_month,
            selected_member=selected_member,
            selected_account=selected_account,
            selected_type=selected_type,
            selected_category=selected_category,
            user_id=current_user.id,
        )
    finally:
        session.close()


@transactions_view_bp.route("/transactions/manual", methods=["POST"])
@login_required
def create_manual_transaction():
    session = DatabaseRepository().get_session()
    try:
        account = session.query(Account).filter_by(
            id=request.form.get("account_id", type=int), user_id=current_user.id
        ).first()
        member = session.query(Member).filter_by(
            id=request.form.get("member_id", type=int), user_id=current_user.id
        ).first()
        if account is None or member is None:
            flash("Select a valid account and member.", "error")
            return redirect(url_for("transactions_view.transactions_page"))

        transaction_type = request.form.get("type", "Expenditure")
        amount = float(request.form.get("amount", "0"))
        if transaction_type in ("Expenditure", "Investment"):
            amount = -abs(amount)
        elif transaction_type == "Income":
            amount = abs(amount)

        session.add(Transaction(
            date=_parse_date(request.form.get("date")),
            member=member.name,
            account=account.account_name,
            account_type=account.account_type,
            description=request.form.get("description", "").strip(),
            type=transaction_type,
            amount=amount,
            category=request.form.get("category", "Uncategorized").strip(),
            subcategory=request.form.get("subcategory", "Uncategorized").strip(),
            fill_type="Manual",
            comments=request.form.get("comments", "").strip(),
            user_id=current_user.id,
        ))
        session.commit()
        flash("Transaction added.", "success")
    except (ValueError, SQLAlchemyError):
        session.rollback()
        flash("Could not add the transaction. Check the submitted values.", "error")
    finally:
        session.close()
    return redirect(url_for("transactions_view.transactions_page", month=request.form.get("date", "")[:7]))


@transactions_view_bp.route("/transactions/upload", methods=["POST"])
@login_required
def upload_transactions():
    provider = request.form.get("provider", "")
    uploaded_file = request.files.get("file")
    account_id = request.form.get("account_id", type=int)
    member_id = request.form.get("member_id", type=int)
    if provider not in PARSER_IMPORTS or not uploaded_file or not uploaded_file.filename:
        flash("Select a bank parser, account, member, and file.", "error")
        return redirect(url_for("transactions_view.transactions_page"))

    session = DatabaseRepository().get_session()
    temporary_path = None
    imported_months = set()
    try:
        account = session.query(Account).filter_by(id=account_id, user_id=current_user.id).first()
        member = session.query(Member).filter_by(id=member_id, user_id=current_user.id).first()
        if account is None or member is None:
            flash("Select a valid account and member.", "error")
            return redirect(url_for("transactions_view.transactions_page"))

        suffix = os.path.splitext(uploaded_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            uploaded_file.save(temporary_file)
            temporary_path = temporary_file.name

        parser = _parser_for(provider)
        parsed_transactions = parser(temporary_path, password=request.form.get("password") or None) or []
        imported = 0
        for item in parsed_transactions:
            transaction_date = _parse_date(item["date"])
            imported_months.add(transaction_date.strftime("%Y-%m"))
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
                user_id=current_user.id,
            )
            session.add(transaction)
            try:
                session.commit()
                imported += 1
            except IntegrityError:
                session.rollback()

        flash(f"Imported {imported} of {len(parsed_transactions)} transactions.", "success")
    except (ValueError, OSError, SQLAlchemyError, ImportError) as error:
        session.rollback()
        flash(f"Could not import the file: {error}", "error")
    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
        session.close()
    redirect_args = {"category": "Uncategorized"}
    if imported_months:
        redirect_args["month"] = sorted(imported_months)[0]
    return redirect(url_for("transactions_view.transactions_page", **redirect_args))


@transactions_view_bp.route("/transactions/<int:transaction_id>/edit", methods=["POST"])
@login_required
def update_transaction(transaction_id):
    session = DatabaseRepository().get_session()
    try:
        transaction = session.query(Transaction).filter_by(
            id=transaction_id, user_id=current_user.id
        ).first()
        if transaction is None:
            flash("Transaction not found.", "error")
        else:
            transaction.category = request.form.get("category", "Uncategorized").strip()
            transaction.subcategory = request.form.get("subcategory", "Uncategorized").strip()
            transaction.comments = request.form.get("comments", "").strip()
            session.commit()
            flash("Transaction updated.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash("Could not update the transaction.", "error")
    finally:
        session.close()
    return redirect(url_for("transactions_view.transactions_page", month=request.form.get("month", "")))


@transactions_view_bp.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    session = DatabaseRepository().get_session()
    month = request.form.get("month", "")
    try:
        transaction = session.query(Transaction).filter_by(
            id=transaction_id, user_id=current_user.id
        ).first()
        if transaction is None:
            flash("Transaction not found.", "error")
        else:
            session.delete(transaction)
            session.commit()
            flash("Transaction deleted.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash("Could not delete the transaction.", "error")
    finally:
        session.close()
    return redirect(url_for("transactions_view.transactions_page", month=month))
