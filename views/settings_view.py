from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.models import Account, Category, Member, User
from app.repository import DatabaseRepository
from app.services import gmail_service, statement_import


settings_bp = Blueprint("settings", __name__)

_ENTITY_CONFIG = {
    "accounts": (Account, ("account_name", "account_type")),
    "categories": (Category, ("Category", "subcategory", "type")),
    "members": (Member, ("name",)),
}


def _get_entities(session, model):
    return session.query(model).filter(model.user_id == current_user.id).order_by(model.id).all()


@settings_bp.route("/settings")
@login_required
def settings():
    repository = DatabaseRepository()
    session = repository.get_session()
    try:
        active_tab = request.args.get("tab", "members")
        if active_tab not in _ENTITY_CONFIG and active_tab != "gmail":
            active_tab = "members"
        categories = _get_entities(session, Category)
        category_types = ("Expenditure", "Income", "Investment", "Transfer")
        return render_template(
            "settings.html",
            accounts=_get_entities(session, Account),
            categories=categories,
            categories_by_type={
                category_type: [
                    category for category in categories if category.type == category_type
                ]
                for category_type in category_types
            },
            category_options=sorted(
                [
                    {
                        "name": category.Category,
                        "type": category.type,
                        "subcategory": category.subcategory,
                    }
                    for category in categories
                ],
                key=lambda option: (option["name"] or "", option["type"] or ""),
            ),
            members=_get_entities(session, Member),
            active_tab=active_tab,
            gmail=_gmail_state(session),
        )
    finally:
        session.close()


def _gmail_state(session):
    configured, reason = gmail_service.is_configured()
    return {
        "configured": configured,
        "reason": reason,
        "account_email": gmail_service.account_email() if configured else None,
        "address": current_user.gmail_address,
        "last_sync": current_user.last_gmail_sync_at,
        "month": date.today().strftime("%Y-%m"),
    }


@settings_bp.route("/settings/gmail", methods=["POST"])
@login_required
def save_gmail_address():
    address = request.form.get("gmail_address", "").strip().lower() or None
    if address and not gmail_service.VALID_EMAIL_RE.match(address):
        flash("That does not look like a valid email address.", "error")
        return redirect(url_for("settings.settings", tab="gmail"))

    session = DatabaseRepository().get_session()
    try:
        user = session.get(User, current_user.id)
        user.gmail_address = address
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        flash("Could not save the Gmail address.", "error")
    finally:
        session.close()
    return redirect(url_for("settings.settings", tab="gmail"))


@settings_bp.route("/settings/gmail/test", methods=["POST"])
@login_required
def test_gmail_email():
    address = current_user.gmail_address
    if not address:
        flash("Save your Gmail address before sending a test email.", "error")
        return redirect(url_for("settings.settings", tab="gmail"))
    configured, reason = gmail_service.is_configured()
    if not configured:
        flash(f"Gmail is not configured: {reason}", "error")
    else:
        try:
            gmail_service.send_email(
                address,
                "Finance Tracker test email",
                "This test email confirms your Finance Tracker Gmail connection works.",
            )
            flash(f"Test email sent to {address}.", "success")
        except Exception as error:
            flash(f"Could not send the test email: {error}", "error")
    return redirect(url_for("settings.settings", tab="gmail"))


@settings_bp.route("/settings/gmail/fetch", methods=["POST"])
@login_required
def fetch_gmail_statements():
    month = request.form.get("month", "")
    try:
        month = datetime.strptime(month, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        month = date.today().strftime("%Y-%m")

    session = DatabaseRepository().get_session()
    try:
        account = session.query(Account).filter_by(
            id=request.form.get("account_id", type=int), user_id=current_user.id
        ).first()
        member = session.query(Member).filter_by(
            id=request.form.get("member_id", type=int), user_id=current_user.id
        ).first()
        if account is None or member is None:
            flash("Pick an account and member for the imported statements.", "error")
            return redirect(url_for("settings.settings", tab="gmail"))

        sync = gmail_service.run_sync(current_user.id, month)
        if not sync.get("ok"):
            flash(f"Gmail sync stopped: {sync.get('reason', 'unknown reason')}", "error")
            return redirect(url_for("settings.settings", tab="gmail"))

        reports = statement_import.import_statements_for_month(
            session, current_user.id, sync.get("files", []), account, member
        )
        total_imported = sum(report.get("imported", 0) for report in reports)
        total_skipped = sum(report.get("skipped", 0) for report in reports)
        user = session.get(User, current_user.id)
        user.last_gmail_sync_at = datetime.now()
        session.commit()

        if sync.get("count", 0) == 0:
            flash(f"No statement attachments found for {month}.", "info")
        else:
            flash(
                f"Downloaded {sync['count']} statement file(s); imported {total_imported} "
                f"transaction(s) and skipped {total_skipped} duplicate(s).",
                "success",
            )
    except SQLAlchemyError:
        session.rollback()
        flash("Gmail sync failed while saving transactions.", "error")
    finally:
        session.close()
    return redirect(url_for("settings.settings", tab="gmail"))


@settings_bp.route("/settings/<entity>", methods=["POST"])
@login_required
def create_entity(entity):
    config = _ENTITY_CONFIG.get(entity)
    if config is None:
        return "Not found", 404

    model, fields = config
    values = {field: request.form.get(field, "").strip() for field in fields}
    if entity == "categories" and values["Category"] == "__new__":
        values["Category"] = request.form.get("Category_new", "").strip()
    if entity == "categories" and values["type"] not in ("Expenditure", "Transfer"):
        values["subcategory"] = values["Category"]
    if any(not value for value in values.values()):
        flash("All fields are required.", "error")
        return redirect(url_for("settings.settings", tab=entity))

    session = DatabaseRepository().get_session()
    try:
        session.add(model(user_id=current_user.id, **values))
        session.commit()
        flash(f"{entity.title()[:-1]} created.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash(f"Could not create {entity[:-1]}.", "error")
    finally:
        session.close()
    return redirect(url_for("settings.settings", tab=entity))


@settings_bp.route("/settings/<entity>/<int:entity_id>", methods=["POST"])
@login_required
def update_entity(entity, entity_id):
    config = _ENTITY_CONFIG.get(entity)
    if config is None:
        return "Not found", 404

    model, fields = config
    values = {field: request.form.get(field, "").strip() for field in fields}
    if any(not value for value in values.values()):
        flash("All fields are required.", "error")
        return redirect(url_for("settings.settings", tab=entity))

    session = DatabaseRepository().get_session()
    try:
        record = session.query(model).filter_by(id=entity_id, user_id=current_user.id).first()
        if record is None:
            flash(f"{entity.title()[:-1]} not found.", "error")
        else:
            for field, value in values.items():
                setattr(record, field, value)
            session.commit()
            flash(f"{entity.title()[:-1]} updated.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash(f"Could not update {entity[:-1]}.", "error")
    finally:
        session.close()
    return redirect(url_for("settings.settings", tab=entity))


@settings_bp.route("/settings/<entity>/<int:entity_id>/delete", methods=["POST"])
@login_required
def delete_entity(entity, entity_id):
    config = _ENTITY_CONFIG.get(entity)
    if config is None:
        return "Not found", 404

    model, _ = config
    session = DatabaseRepository().get_session()
    try:
        record = session.query(model).filter_by(id=entity_id, user_id=current_user.id).first()
        if record is None:
            flash(f"{entity.title()[:-1]} not found.", "error")
        else:
            session.delete(record)
            session.commit()
            flash(f"{entity.title()[:-1]} deleted.", "success")
    except SQLAlchemyError:
        session.rollback()
        flash(f"Could not delete {entity[:-1]}.", "error")
    finally:
        session.close()
    return redirect(url_for("settings.settings", tab=entity))
