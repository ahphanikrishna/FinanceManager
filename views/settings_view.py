from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.models import Account, Category, Member
from app.repository import DatabaseRepository


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
        if active_tab not in _ENTITY_CONFIG:
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
        )
    finally:
        session.close()


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
